import os
import sqlite3
import pytest
from trading_system.journal import db

@pytest.fixture(autouse=True)
def setup_db():
    db.DB_PATH = "test_trading_system.db"
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_db()
    yield
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)

def test_schema_created_on_init():
    with sqlite3.connect(db.DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "recommendations" in tables
        assert "trades" in tables

def test_insert_recommendation():
    rec = {
        "created_at": "2023-01-01T00:00:00",
        "sweep": "open",
        "ticker": "AAPL",
        "action": "BUY"
    }
    rec_id = db.insert_recommendation(rec)
    assert rec_id > 0
    fetched = db.get_recommendation(rec_id)
    assert fetched["ticker"] == "AAPL"

def test_insert_and_close_trade():
    trade = {
        "ticker": "AAPL",
        "side": "BUY",
        "notional": 1000,
        "fill_price": 150.0,
        "fill_time": "2023-01-01T00:00:00"
    }
    trade_id = db.insert_trade(trade)
    assert trade_id > 0
    db.update_trade(trade_id, {"close_price": 160.0, "pnl": 100.0, "outcome": "WIN"})
    
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        fetched = dict(cursor.fetchone())
        assert fetched["close_price"] == 160.0


def test_migrated_columns_exist():
    with sqlite3.connect(db.DB_PATH) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
    assert {"order_id", "atr_at_entry", "high_water_price"} <= cols


def test_open_and_closed_trade_queries():
    trade_id = db.insert_trade({"ticker": "AAPL", "side": "BUY", "notional": 100, "fill_time": "2026-09-25T10:00:00"})
    assert db.get_open_trade("AAPL")["id"] == trade_id
    assert db.get_tickers_opened_on("2026-09-25") == {"AAPL"}
    db.update_trade(trade_id, {"close_time": "2026-09-26T10:00:00", "pnl_pct": 0.05, "pnl": 5})
    assert db.get_open_trade("AAPL") is None
    assert [t["id"] for t in db.get_unreviewed_closed_trades()] == [trade_id]
    db.insert_review({"trade_id": trade_id, "created_at": "2026-09-26"})
    assert db.get_unreviewed_closed_trades() == []
