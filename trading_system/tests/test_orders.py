from alpaca.trading.enums import OrderSide, OrderType, TimeInForce

from trading_system.execution.orders import build_market_order, submit_order


class FakeOrder:
    def __init__(self, order_id="ord-123", status="filled", filled_avg_price="1.00"):
        self.id = order_id
        self.status = status
        self.filled_avg_price = filled_avg_price


class FakeTradingClient:
    def __init__(self):
        self.submitted_orders = []
        self.closed_positions = []

    def submit_order(self, order_request):
        self.submitted_orders.append(order_request)
        return FakeOrder()

    def close_position(self, symbol):
        self.closed_positions.append(symbol)
        return FakeOrder(order_id=f"close-{symbol}", filled_avg_price="1.00")


def test_build_market_order_buy_uses_notional_for_low_price_stock():
    rec = {
        "ticker": "PENNY",
        "price_at_signal": 1.00,
        "portfolio_value": 10_000,
        "position_size_pct": 0.05,
    }

    order = build_market_order(rec, OrderSide.BUY)

    assert order.symbol == "PENNY"
    assert order.side == OrderSide.BUY
    assert order.type == OrderType.MARKET
    assert order.time_in_force == TimeInForce.DAY
    assert order.notional == 500.0
    assert order.qty is None


def test_build_market_order_buy_derives_notional_without_price():
    rec = {
        "ticker": "VERU",
        "portfolio_value": 20_000,
        "position_size_pct": 0.04,
    }

    order = build_market_order(rec, OrderSide.BUY)

    assert order.symbol == "VERU"
    assert order.notional == 800.0
    assert order.qty is None


def test_submit_order_buy_places_market_order():
    client = FakeTradingClient()
    rec = {
        "ticker": "PENNY",
        "action": "BUY",
        "qty": 10,
    }

    order = submit_order(client, rec)

    assert len(client.submitted_orders) == 1
    sent = client.submitted_orders[0]
    assert sent.symbol == "PENNY"
    assert sent.side == OrderSide.BUY
    assert sent.qty == 10.0
    assert order.id == "ord-123"


def test_submit_order_sell_places_market_order():
    client = FakeTradingClient()
    rec = {
        "ticker": "PENNY",
        "action": "SELL",
        "qty": 10,
    }

    order = submit_order(client, rec)

    assert len(client.submitted_orders) == 1
    sent = client.submitted_orders[0]
    assert sent.symbol == "PENNY"
    assert sent.side == OrderSide.SELL
    assert sent.qty == 10.0
    assert order.id == "ord-123"


def test_close_position_can_be_used_for_sell_flow():
    client = FakeTradingClient()
    order = client.close_position("PENNY")

    assert client.closed_positions == ["PENNY"]
    assert order.id == "close-PENNY"
