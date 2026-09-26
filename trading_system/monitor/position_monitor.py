import logging
from datetime import datetime
from trading_system import config
from trading_system.execution import alpaca_client
from trading_system.journal import db

logger = logging.getLogger(__name__)

UNFILLED_STATUSES = {"canceled", "cancelled", "rejected", "expired"}


def _status(order) -> str:
    return str(getattr(order, "status", "")).split(".")[-1].lower()


def record_close(ticker: str, close_price: float, closed_by: str, entry_price: float | None = None):
    """Mark the open journal trade for ticker as closed and compute realized P&L (estimated at close_price)."""
    trade = db.get_open_trade(ticker)
    if not trade:
        logger.warning("No open journal trade found for %s", ticker)
        return
    entry = trade.get("fill_price") or entry_price
    update = {"close_price": close_price, "close_time": datetime.now().isoformat(), "closed_by": closed_by}
    if entry and close_price:
        pnl_pct = close_price / entry - 1.0
        update["pnl_pct"] = pnl_pct
        update["pnl"] = (trade.get("notional") or 0.0) * pnl_pct
        update["outcome"] = "WIN" if pnl_pct > 0 else "LOSS"
    db.update_trade(trade["id"], update)


def exit_levels(entry: float, atr: float | None, high_water: float | None) -> tuple[float, float, bool]:
    """
    Return (stop, target, is_trailing). With an ATR on record the stop trails the highest price seen
    by ATR_STOP_MULT * ATR (a chandelier stop) and never sits below the initial stop.
    Without one, fall back to fixed percentages.
    """
    if not atr:
        return entry * (1 - config.STOP_LOSS_PCT), entry * (1 + config.TAKE_PROFIT_PCT), False
    initial_stop = entry - config.ATR_STOP_MULT * atr
    trailing_stop = (high_water or entry) - config.ATR_STOP_MULT * atr
    return max(initial_stop, trailing_stop), entry + config.ATR_TARGET_MULT * atr, trailing_stop > initial_stop


def reconcile_trades(trading_client, positions: list):
    """Fill in actual fill prices and close out journal trades whose orders never filled or whose position is gone."""
    held = {p.symbol for p in positions}
    for trade in db.get_open_trades():
        order_id = trade.get("order_id")
        if not order_id:
            continue
        try:
            order = trading_client.get_order_by_id(order_id)
        except Exception as e:
            logger.warning("Could not fetch order %s for %s: %s", order_id, trade["ticker"], e)
            continue
        status = _status(order)
        if status in UNFILLED_STATUSES and not getattr(order, "filled_avg_price", None):
            db.update_trade(trade["id"], {"close_time": datetime.now().isoformat(), "closed_by": "unfilled", "outcome": status.upper()})
            continue
        if getattr(order, "filled_avg_price", None) and trade.get("fill_price") is None:
            filled_at = getattr(order, "filled_at", None)
            db.update_trade(trade["id"], {
                "fill_price": float(order.filled_avg_price),
                "fill_time": filled_at.isoformat() if filled_at else trade.get("fill_time"),
                "outcome": status.upper(),
            })
        if status == "filled" and trade["ticker"] not in held:
            logger.info("%s no longer held; marking journal trade closed externally", trade["ticker"])
            db.update_trade(trade["id"], {"close_time": datetime.now().isoformat(), "closed_by": "external"})


def run_monitor():
    logger.info("Running position monitor")
    try:
        trading_client = alpaca_client.get_trading_client()
        clock = trading_client.get_clock()
        if not clock.is_open and not config.ALLOW_TRADING_WHEN_CLOSED:
            logger.debug("Market closed; monitor idle")
            return
        positions = trading_client.get_all_positions()
        account = trading_client.get_account()
        logger.info(f"Monitor: Portfolio Value: {account.portfolio_value}, positions: {len(positions)}")

        reconcile_trades(trading_client, positions)

        for pos in positions:
            entry = float(pos.avg_entry_price)
            price = float(pos.current_price)
            trade = db.get_open_trade(pos.symbol) or {}
            atr = trade.get("atr_at_entry")
            high_water = max(trade.get("high_water_price") or entry, price)
            if trade and high_water != trade.get("high_water_price"):
                db.update_trade(trade["id"], {"high_water_price": high_water})

            stop, target, trailing = exit_levels(entry, atr, high_water)
            logger.debug(f"Position {pos.symbol}: price {price} entry {entry} stop {stop:.2f} target {target:.2f}")

            close_reason = None
            if price <= stop:
                close_reason = "trailing_stop" if trailing else "stop_loss"
            elif price >= target:
                close_reason = "take_profit"

            if close_reason:
                logger.info(f"Closing {pos.symbol} due to {close_reason} (price {price}, stop {stop:.2f}, target {target:.2f})")
                try:
                    trading_client.close_position(pos.symbol)
                    record_close(pos.symbol, price, close_reason, entry_price=entry)
                except Exception as e:
                    logger.error(f"Failed to close {pos.symbol}: {e}")

        equity = float(account.equity)
        db.insert_portfolio_snapshot({
            "recorded_at": datetime.now().isoformat(),
            "portfolio_value": float(account.portfolio_value),
            "cash": float(account.cash),
            "equity": equity,
            "peak_value": max(float(account.portfolio_value), db.get_peak_value()),
            "open_positions": len(positions),
            "daily_pnl": equity - float(account.last_equity or equity),
        })

    except Exception as e:
        logger.exception(f"Monitor loop failed: {e}")
