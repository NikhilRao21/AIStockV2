"""Offline end-to-end sweep: Alpaca, news and the LLM are faked."""
import json
import os
from types import SimpleNamespace

import pytest

from trading_system import config
from trading_system.journal import db
from trading_system.scheduler import sweep


def _bars(start, n=80, step=1.0):
    return [SimpleNamespace(open=start + i * step, high=start + i * step + 1, low=start + i * step - 1,
                            close=start + i * step, volume=2_000_000) for i in range(n)]


class FakeClient:
    def __init__(self, positions):
        self.positions = positions
        self.submitted = []
        self.closed = []

    def get_account(self):
        return SimpleNamespace(portfolio_value="100000", cash="100000", equity="100000", last_equity="100000")

    def get_all_positions(self):
        return self.positions

    def get_clock(self):
        return SimpleNamespace(is_open=True)

    def submit_order(self, req):
        self.submitted.append(req)
        return SimpleNamespace(id="ord-1", status="accepted")

    def close_position(self, symbol):
        self.closed.append(symbol)
        return SimpleNamespace(id="ord-2", status="accepted")


def _rec(action):
    return json.dumps({
        "ticker": "X", "action": action, "confidence": 0.8, "bull_case": "b", "bear_case": "b",
        "supporting_evidence": ["e"], "key_risks": ["r"], "catalysts": ["c"], "position_size_pct": 0,
        "expected_holding_days": 5, "reasoning_summary": "s",
    })


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "REFLECTION_PATH", str(tmp_path / "missing.txt"))
    db.init_db()
    held = SimpleNamespace(symbol="OLD", current_price="50", change_today="0.01", avg_entry_price="45",
                           unrealized_plpc="0.11")
    client = FakeClient([held])
    monkeypatch.setattr(sweep.alpaca_client, "get_trading_client", lambda: client)
    monkeypatch.setattr(sweep.screener, "get_tradable_universe", lambda: {"NEWCO", "OLD", "PENNY"})
    monkeypatch.setattr(sweep.screener, "get_candidates", lambda: [
        {"symbol": "NEWCO", "volume": 5e6, "price": 0.0, "percent_change": 0.05, "news_count": 0},
        {"symbol": "PENNY", "volume": 5e6, "price": 0.0, "percent_change": 0.05, "news_count": 0},
    ])
    monkeypatch.setattr(sweep.market, "get_bars",
                        lambda symbols, days=0: {s: _bars(3, step=0) if s == "PENNY" else _bars(50) for s in symbols})
    monkeypatch.setattr(sweep.news, "search_news_alpaca", lambda *a, **k: [])
    monkeypatch.setattr(sweep.news, "search_news_langsearch", lambda *a, **k: [])
    monkeypatch.setattr(sweep.thesis, "call_llm", lambda *a, **k: "thesis")
    return client


def test_sweep_buys_new_name_and_sells_held(env, monkeypatch):
    monkeypatch.setattr(sweep, "call_llm", lambda sys, user, **k: _rec("SELL" if "You currently HOLD" in user else "BUY"))
    sweep.run_sweep("test")

    assert env.closed == ["OLD"]
    assert [o.symbol for o in env.submitted] == ["NEWCO"]  # PENNY filtered by triage
    order = env.submitted[0]
    assert 0 < order.notional <= 100000 * config.MAX_POSITION_PCT
    trade = db.get_open_trade("NEWCO")
    assert trade["order_id"] == "ord-1" and trade["atr_at_entry"] and trade["stop_price"] < 129


def test_buy_coerced_to_hold_for_held_position(env, monkeypatch):
    monkeypatch.setattr(sweep, "call_llm", lambda sys, user, **k: _rec("BUY" if "You currently HOLD" in user else "NO_ACTION"))
    sweep.run_sweep("test")
    assert env.closed == [] and env.submitted == []
