import logging
from trading_system import config

logger = logging.getLogger(__name__)


def _normalize_position_size_pct(value):
    try:
        size_pct = float(value)
    except (TypeError, ValueError):
        return 0.0

    return size_pct / 100.0 if size_pct > 1.0 else size_pct


def size_position(entry_price: float, atr: float, equity: float, llm_size_pct=None) -> dict | None:
    """
    Volatility-based sizing: risk RISK_PER_TRADE_PCT of equity between entry and an ATR stop.

    The result is capped at MAX_POSITION_PCT, and the LLM's suggested size can only shrink it,
    never grow it. Returns notional plus the stop/target prices the monitor will enforce.
    """
    if not entry_price or not atr or entry_price <= 0 or atr <= 0 or equity <= 0:
        return None
    stop_distance = config.ATR_STOP_MULT * atr
    if stop_distance >= entry_price:
        return None
    risk_dollars = equity * config.RISK_PER_TRADE_PCT
    notional = risk_dollars / stop_distance * entry_price

    cap_pct = config.MAX_POSITION_PCT
    llm_pct = _normalize_position_size_pct(llm_size_pct)
    if llm_pct > 0:
        cap_pct = min(cap_pct, llm_pct)
    notional = min(notional, equity * cap_pct)

    return {
        "notional": round(notional, 2),
        "position_size_pct": notional / equity,
        "stop_price": round(entry_price - stop_distance, 2),
        "take_profit_price": round(entry_price + config.ATR_TARGET_MULT * atr, 2),
    }


def check_confidence(rec: dict) -> tuple[bool, str]:
    if rec.get("confidence", 0) < config.MIN_CONFIDENCE_SCORE:
        return False, f"Confidence {rec.get('confidence')} below minimum {config.MIN_CONFIDENCE_SCORE}"
    return True, ""


def check_min_notional(notional: float) -> tuple[bool, str]:
    if notional < config.MIN_ORDER_NOTIONAL:
        return False, f"Order notional {notional} below minimum {config.MIN_ORDER_NOTIONAL}"
    return True, ""


def check_cash_reserve(notional: float, cash: float, portfolio_value: float) -> tuple[bool, str]:
    if portfolio_value == 0:
        return False, "Portfolio value is 0"
    remaining_cash_pct = (cash - notional) / portfolio_value
    if remaining_cash_pct < config.MIN_CASH_RESERVE_PCT:
        return False, "Insufficient cash reserve"
    return True, ""


def check_open_positions(positions: list) -> tuple[bool, str]:
    if len(positions) >= config.MAX_OPEN_POSITIONS:
        return False, "Max open positions reached"
    return True, ""


def check_entries_this_sweep(sweep_entries: int) -> tuple[bool, str]:
    if sweep_entries >= config.MAX_ENTRIES_PER_SWEEP:
        return False, "Max entries per sweep reached"
    return True, ""


def check_daily_loss(equity: float, last_equity: float) -> tuple[bool, str]:
    """Compare against yesterday's closing equity (Alpaca's account.last_equity)."""
    if not last_equity:
        return True, ""
    loss_pct = (last_equity - equity) / last_equity
    if loss_pct >= config.MAX_DAILY_LOSS_PCT:
        return False, f"Daily loss {loss_pct:.2%} exceeds max {config.MAX_DAILY_LOSS_PCT:.2%}"
    return True, ""


def check_drawdown(portfolio_value: float, peak_value: float) -> tuple[bool, str]:
    if peak_value == 0:
        return True, ""
    drawdown_pct = (peak_value - portfolio_value) / peak_value
    if drawdown_pct >= config.MAX_DRAWDOWN_PCT:
        return False, f"Drawdown {drawdown_pct:.2%} exceeds max {config.MAX_DRAWDOWN_PCT:.2%}"
    return True, ""


def check_market_open(clock) -> tuple[bool, str]:
    if config.ALLOW_TRADING_WHEN_CLOSED:
        return True, ""
    if not clock.is_open:
        return False, "Market is closed"
    return True, ""


def check_duplicate_position(ticker: str, positions: list) -> tuple[bool, str]:
    if any(pos.symbol == ticker for pos in positions):
        return False, f"Already holding {ticker}"
    return True, ""


def check_holds_position(ticker: str, positions: list) -> tuple[bool, str]:
    if not any(pos.symbol == ticker for pos in positions):
        return False, f"Cannot sell {ticker}: no open position"
    return True, ""


def check_not_opened_today(ticker: str, opened_today: set[str]) -> tuple[bool, str]:
    # Same-day round trips count as day trades (PDT limits on accounts under $25k) and are churn for a swing strategy.
    # Stop-loss exits in the monitor are not subject to this.
    if ticker in opened_today:
        return False, f"{ticker} was opened today; discretionary same-day exits are not allowed"
    return True, ""


def run_all_checks(rec: dict, account, positions: list, clock, peak_value: float, sweep_entries: int,
                   opened_today: set[str] = frozenset()) -> tuple[bool, list[str]]:
    ticker = rec.get("ticker")
    action = str(rec.get("action", "")).upper()

    if action == "BUY":
        portfolio_value = float(account.portfolio_value)
        notional = float(rec.get("notional") or 0.0)
        checks = [
            check_confidence(rec),
            check_min_notional(notional),
            check_cash_reserve(notional, float(account.cash), portfolio_value),
            check_open_positions(positions),
            check_entries_this_sweep(sweep_entries),
            check_daily_loss(float(account.equity), float(account.last_equity or 0)),
            check_drawdown(portfolio_value, peak_value),
            check_market_open(clock),
            check_duplicate_position(ticker, positions),
        ]
    elif action == "SELL":
        # Exits reduce risk, so halt conditions and capacity limits do not apply.
        checks = [
            check_confidence(rec),
            check_holds_position(ticker, positions),
            check_not_opened_today(ticker, opened_today),
            check_market_open(clock),
        ]
    else:
        return False, [f"No order for action {action}"]

    reasons = [reason for passed, reason in checks if not passed]
    return len(reasons) == 0, reasons
