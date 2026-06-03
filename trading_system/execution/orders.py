import logging
import uuid
from typing import Any

from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

logger = logging.getLogger(__name__)


def _coerce_positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def build_market_order(rec: dict, side: OrderSide) -> MarketOrderRequest:
    ticker = rec.get("ticker")
    if not ticker:
        raise ValueError("Recommendation is missing ticker")

    notional = _coerce_positive_float(rec.get("notional"))
    qty = _coerce_positive_float(rec.get("qty"))

    if notional is None and qty is None:
        price = _coerce_positive_float(rec.get("price_at_signal"))
        portfolio_value = _coerce_positive_float(rec.get("portfolio_value"))
        position_pct = _coerce_positive_float(rec.get("position_size_pct"))

        if price and portfolio_value and position_pct:
            notional = portfolio_value * position_pct

    if notional is None and qty is None:
        raise ValueError("Recommendation must include either notional, qty, or enough data to derive notional")

    order_kwargs = {
        "symbol": ticker,
        "side": side,
        "type": OrderType.MARKET,
        "time_in_force": TimeInForce.DAY,
    }

    if notional is not None:
        order_kwargs["notional"] = round(notional, 2)
    else:
        order_kwargs["qty"] = round(qty, 6)

    client_order_id = rec.get("client_order_id") or f"ais-{ticker.lower()}-{uuid.uuid4().hex[:12]}"
    order_kwargs["client_order_id"] = client_order_id

    return MarketOrderRequest(**order_kwargs)


def submit_order(trading_client, rec: dict):
    action = str(rec.get("action", "")).upper()
    if action not in {"BUY", "SELL"}:
        raise ValueError(f"Unsupported action for order submission: {action}")

    side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
    order_request = build_market_order(rec, side)
    logger.info("Submitting %s order for %s", action, rec.get("ticker"))
    return trading_client.submit_order(order_request)
