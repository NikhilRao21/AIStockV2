from trading_system.execution.risk import (
    check_confidence, check_cash_reserve, check_open_positions, check_daily_loss,
    check_drawdown, check_market_open, check_duplicate_position, run_all_checks, size_position,
)
from trading_system import config


class MockAccount:
    def __init__(self, portfolio_value, cash, equity=None, last_equity=None):
        self.portfolio_value = portfolio_value
        self.cash = cash
        self.equity = equity if equity is not None else portfolio_value
        self.last_equity = last_equity if last_equity is not None else self.equity


class MockPosition:
    def __init__(self, symbol):
        self.symbol = symbol


class MockClock:
    def __init__(self, is_open):
        self.is_open = is_open


def _buy(**overrides):
    rec = {"ticker": "AAPL", "action": "BUY", "confidence": 0.8, "notional": 400.0}
    rec.update(overrides)
    return rec


def test_size_position_risks_one_percent_at_the_stop():
    sized = size_position(entry_price=100.0, atr=2.0, equity=100_000)
    # stop distance = 2 * ATR = $4; risking $1,000 -> 250 shares -> $25,000, capped at 5% = $5,000
    assert sized["notional"] == 5_000.0
    assert sized["stop_price"] == 96.0
    assert sized["take_profit_price"] == 108.0


def test_size_position_shrinks_for_volatile_stocks():
    calm = size_position(entry_price=100.0, atr=1.0, equity=10_000)
    wild = size_position(entry_price=100.0, atr=20.0, equity=10_000)
    # $100 risk / $40 stop distance = 2.5 shares = $250
    assert wild["notional"] == 250.0
    assert wild["notional"] < calm["notional"]


def test_llm_can_only_shrink_size():
    assert size_position(100.0, 1.0, 10_000, llm_size_pct=0.01)["notional"] == 100.0
    assert size_position(100.0, 1.0, 10_000, llm_size_pct=0.50)["notional"] == 500.0


def test_size_position_rejects_missing_atr():
    assert size_position(100.0, None, 10_000) is None


def test_blocks_insufficient_cash():
    # portfolio_value = 10000, cash = 1000. Required reserve is 20% = 2000.
    passed, _ = check_cash_reserve(500, 1000, 10000)
    assert not passed


def test_blocks_too_many_positions():
    positions = [MockPosition(f"SYM{i}") for i in range(config.MAX_OPEN_POSITIONS)]
    passed, _ = check_open_positions(positions)
    assert not passed


def test_blocks_low_confidence():
    passed, _ = check_confidence({"confidence": 0.50})
    assert not passed


def test_daily_loss_halt_uses_last_equity():
    passed, _ = check_daily_loss(9500, 10000)
    assert not passed


def test_drawdown_halt():
    passed, _ = check_drawdown(8000, 10000)
    assert not passed


def test_market_closed_blocks_orders(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_TRADING_WHEN_CLOSED", False)
    assert not check_market_open(MockClock(False))[0]
    assert check_market_open(MockClock(True))[0]


def test_duplicate_position_blocked():
    passed, _ = check_duplicate_position("AAPL", [MockPosition("AAPL")])
    assert not passed


def test_buy_passes_when_everything_ok():
    passed, reasons = run_all_checks(_buy(), MockAccount(10000, 10000), [], MockClock(True), 10000, 0)
    assert passed, reasons


def test_buy_blocked_by_cash_reserve():
    passed, reasons = run_all_checks(_buy(notional=9000), MockAccount(10000, 10000), [], MockClock(True), 10000, 0)
    assert not passed
    assert "Insufficient cash reserve" in reasons


def test_buy_blocked_by_daily_loss():
    account = MockAccount(9600, 9600, equity=9600, last_equity=10000)
    passed, reasons = run_all_checks(_buy(), account, [], MockClock(True), 10000, 0)
    assert not passed
    assert any("Daily loss" in r for r in reasons)


def test_sell_allowed_despite_halts_and_low_cash():
    account = MockAccount(8000, 0, equity=8000, last_equity=10000)
    rec = {"ticker": "AAPL", "action": "SELL", "confidence": 0.7}
    positions = [MockPosition(f"SYM{i}") for i in range(config.MAX_OPEN_POSITIONS - 1)] + [MockPosition("AAPL")]
    passed, reasons = run_all_checks(rec, account, positions, MockClock(True), 10000, 99)
    assert passed, reasons


def test_sell_requires_position():
    rec = {"ticker": "AAPL", "action": "SELL", "confidence": 0.7}
    passed, reasons = run_all_checks(rec, MockAccount(10000, 10000), [], MockClock(True), 10000, 0)
    assert not passed


def test_sell_blocked_same_day():
    rec = {"ticker": "AAPL", "action": "SELL", "confidence": 0.7}
    passed, reasons = run_all_checks(rec, MockAccount(10000, 10000), [MockPosition("AAPL")], MockClock(True),
                                     10000, 0, opened_today={"AAPL"})
    assert not passed
