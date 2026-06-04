import pytest
from trading_system.execution.risk import (
    check_confidence, check_position_size, check_cash_reserve,
    check_open_positions, check_entries_this_sweep, check_daily_loss,
    check_drawdown, check_market_open, check_duplicate_position, run_all_checks
)
from trading_system import config

class MockAccount:
    def __init__(self, portfolio_value, cash):
        self.portfolio_value = portfolio_value
        self.cash = cash

class MockPosition:
    def __init__(self, symbol):
        self.symbol = symbol

class MockClock:
    def __init__(self, is_open):
        self.is_open = is_open

def test_blocks_oversized_position():
    rec = {"position_size_pct": 0.10}
    passed, _ = check_position_size(rec, 10000)
    assert passed
    assert rec["position_size_pct"] == config.MAX_POSITION_PCT

def test_allows_valid_position():
    rec = {"position_size_pct": 0.04}
    passed, _ = check_position_size(rec, 10000)
    assert passed

def test_blocks_insufficient_cash():
    # portfolio_value = 10000, cash = 1000. Required reserve is 20% = 2000.
    passed, _ = check_cash_reserve(500, 1000, 10000)
    assert not passed

def test_blocks_too_many_positions():
    positions = [MockPosition(f"SYM{i}") for i in range(config.MAX_OPEN_POSITIONS)]
    passed, _ = check_open_positions(positions)
    assert not passed

def test_blocks_low_confidence():
    rec = {"confidence": 0.50}
    passed, _ = check_confidence(rec)
    assert not passed

def test_daily_loss_halt():
    # max daily loss 3%. day_start = 10000, current = 9500 (5% loss)
    passed, _ = check_daily_loss(9500, 10000)
    assert not passed

def test_drawdown_halt():
    # max drawdown 15%. peak = 10000, current = 8000 (20% drawdown)
    passed, _ = check_drawdown(8000, 10000)
    assert not passed

def test_blocks_duplicate_position():
    positions = [MockPosition("NVDA")]
    passed, _ = check_duplicate_position("NVDA", positions)
    assert not passed

def test_run_all_checks_blocks_synthetic():
    rec = {"ticker": "AAPL", "position_size_pct": 0.99, "confidence": 0.9}
    account = MockAccount(10000, 10000)
    clock = MockClock(True)
    positions = []
    passed, reasons = run_all_checks(rec, account, positions, clock, 10000, 10000, 0)
    assert not passed
    assert any("Insufficient cash reserve" in r for r in reasons)
