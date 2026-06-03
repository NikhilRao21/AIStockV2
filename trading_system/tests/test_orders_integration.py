import os
import time

import pytest

from trading_system.execution.alpaca_client import get_trading_client
from trading_system.execution.orders import submit_order


pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    return os.environ.get("ALPACA_RUN_ORDER_INTEGRATION") == "1"


def _wait_for_fill(trading_client, order_id: str, timeout_seconds: int = 90):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        order = trading_client.get_order_by_id(order_id)
        status = str(getattr(order, "status", "")).lower()
        if status in {"filled", "partially_filled", "canceled", "rejected", "expired"}:
            return order
        time.sleep(2)
    raise TimeoutError(f"Order {order_id} did not reach a terminal state within {timeout_seconds}s")


@pytest.mark.skipif(not _integration_enabled(), reason="Enable ALPACA_RUN_ORDER_INTEGRATION=1 to run Alpaca paper order integration test")
def test_buy_then_sell_paper_order_round_trip():
    trading_client = get_trading_client()
    ticker = os.environ.get("ALPACA_TEST_TICKER", "SIRI")
    notional = float(os.environ.get("ALPACA_TEST_NOTIONAL", "10"))

    buy_rec = {
        "ticker": ticker,
        "action": "BUY",
        "notional": notional,
    }
    buy_order = submit_order(trading_client, buy_rec)
    buy_filled = _wait_for_fill(trading_client, buy_order.id)
    assert str(getattr(buy_filled, "status", "")).lower() in {"filled", "partially_filled"}

    sell_order = trading_client.close_position(ticker)
    sell_filled = _wait_for_fill(trading_client, sell_order.id)
    assert str(getattr(sell_filled, "status", "")).lower() in {"filled", "partially_filled"}

