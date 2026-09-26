import sqlite3
import json
import logging
from datetime import datetime

from trading_system import config

logger = logging.getLogger(__name__)

DB_PATH = config.DB_PATH

# Columns added after the original schema; applied with ALTER TABLE on existing databases.
MIGRATIONS = {
    "recommendations": {
        "features": "TEXT",
        "sentiment_score": "REAL",
        "raw_response": "TEXT",
        "notional": "REAL",
    },
    "trades": {
        "order_id": "TEXT",
        "atr_at_entry": "REAL",
        "stop_price": "REAL",
        "take_profit_price": "REAL",
        "high_water_price": "REAL",
    },
}


def _normalize_sqlite_value(value):
    """
    Convert Python values into SQLite-friendly scalars.

    Lists and dicts are stored as JSON so callers can pass structured data
    without having to serialize it first.
    """
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def _normalize_data(data: dict) -> dict:
    return {key: _normalize_sqlite_value(value) for key, value in data.items()}

def init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at            TEXT NOT NULL,
                sweep                 TEXT NOT NULL,
                ticker                TEXT NOT NULL,
                action                TEXT NOT NULL,
                confidence            REAL,
                price_at_signal       REAL,
                portfolio_value       REAL,
                bull_case             TEXT,
                bear_case             TEXT,
                supporting_evidence   TEXT,
                key_risks             TEXT,
                catalysts             TEXT,
                news_sources          TEXT,
                triage_score          REAL,
                position_size_pct     REAL,
                expected_holding_days INTEGER,
                reasoning_summary     TEXT,
                order_id              TEXT,
                order_submitted       INTEGER DEFAULT 0,
                risk_block_reasons    TEXT
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id     INTEGER REFERENCES recommendations(id),
                ticker                TEXT NOT NULL,
                side                  TEXT NOT NULL,
                notional              REAL,
                fill_price            REAL,
                fill_time             TEXT,
                close_price           REAL,
                close_time            TEXT,
                closed_by             TEXT,
                pnl                   REAL,
                pnl_pct               REAL,
                outcome               TEXT
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at      TEXT NOT NULL,
                portfolio_value  REAL NOT NULL,
                cash             REAL NOT NULL,
                equity           REAL NOT NULL,
                peak_value       REAL NOT NULL,
                open_positions   INTEGER,
                daily_pnl        REAL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id            INTEGER REFERENCES trades(id),
                created_at          TEXT NOT NULL,
                what_happened       TEXT,
                what_was_correct    TEXT,
                what_was_wrong      TEXT,
                risks_missed        TEXT,
                sizing_appropriate  INTEGER,
                would_take_again    INTEGER,
                lessons_learned     TEXT,
                thesis_accuracy     REAL
            )
            """)
            for table, columns in MIGRATIONS.items():
                existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
                for column, column_type in columns.items():
                    if column not in existing:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def insert_recommendation(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            normalized = _normalize_data(data)
            keys = ', '.join(normalized.keys())
            placeholders = ', '.join(['?'] * len(normalized))
            cursor.execute(
                f"INSERT INTO recommendations ({keys}) VALUES ({placeholders})",
                tuple(normalized.values()),
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert recommendation: {e}")
        return -1

def insert_trade(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            normalized = _normalize_data(data)
            keys = ', '.join(normalized.keys())
            placeholders = ', '.join(['?'] * len(normalized))
            cursor.execute(
                f"INSERT INTO trades ({keys}) VALUES ({placeholders})",
                tuple(normalized.values()),
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert trade: {e}")
        return -1

def insert_portfolio_snapshot(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            normalized = _normalize_data(data)
            keys = ', '.join(normalized.keys())
            placeholders = ', '.join(['?'] * len(normalized))
            cursor.execute(
                f"INSERT INTO portfolio_snapshots ({keys}) VALUES ({placeholders})",
                tuple(normalized.values()),
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert portfolio snapshot: {e}")
        return -1

def get_peak_value() -> float:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(peak_value) FROM portfolio_snapshots")
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0.0
    except Exception as e:
        logger.error(f"Failed to get peak value: {e}")
        return 0.0

def get_recommendation(rec_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get recommendation: {e}")
        return None

def update_trade(trade_id: int, data: dict):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            normalized = _normalize_data(data)
            set_clause = ', '.join([f"{k} = ?" for k in normalized.keys()])
            cursor.execute(
                f"UPDATE trades SET {set_clause} WHERE id = ?",
                tuple(normalized.values()) + (trade_id,),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update trade: {e}")

def insert_review(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            normalized = _normalize_data(data)
            keys = ', '.join(normalized.keys())
            placeholders = ', '.join(['?'] * len(normalized))
            cursor.execute(
                f"INSERT INTO reviews ({keys}) VALUES ({placeholders})",
                tuple(normalized.values()),
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert review: {e}")
        return -1


def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(query, params).fetchall()]
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return []


def get_open_trades() -> list[dict]:
    """BUY trades that have not been closed yet, newest first."""
    return _fetch_all("SELECT * FROM trades WHERE side = 'BUY' AND close_time IS NULL ORDER BY id DESC")


def get_open_trade(ticker: str) -> dict | None:
    rows = _fetch_all(
        "SELECT * FROM trades WHERE side = 'BUY' AND close_time IS NULL AND ticker = ? ORDER BY id DESC LIMIT 1",
        (ticker,),
    )
    return rows[0] if rows else None


def get_tickers_opened_on(day: str) -> set[str]:
    """Tickers with a BUY trade whose fill_time starts with the given YYYY-MM-DD date."""
    rows = _fetch_all("SELECT DISTINCT ticker FROM trades WHERE side = 'BUY' AND fill_time LIKE ?", (day + "%",))
    return {row["ticker"] for row in rows}


def get_unreviewed_closed_trades() -> list[dict]:
    return _fetch_all("""
        SELECT t.*, r.confidence, r.bull_case, r.bear_case, r.supporting_evidence, r.key_risks,
               r.catalysts, r.reasoning_summary, r.expected_holding_days, r.features, r.sentiment_score
        FROM trades t
        LEFT JOIN recommendations r ON r.id = t.recommendation_id
        LEFT JOIN reviews v ON v.trade_id = t.id
        WHERE t.side = 'BUY' AND t.pnl_pct IS NOT NULL AND v.id IS NULL
        ORDER BY t.id
    """)


def get_closed_trades() -> list[dict]:
    return _fetch_all("SELECT * FROM trades WHERE side = 'BUY' AND pnl_pct IS NOT NULL ORDER BY close_time")


def get_portfolio_snapshots() -> list[dict]:
    return _fetch_all("SELECT * FROM portfolio_snapshots ORDER BY recorded_at")


def get_recent_reviews(limit: int = 20) -> list[dict]:
    return _fetch_all("""
        SELECT v.*, t.ticker, t.pnl_pct, t.closed_by
        FROM reviews v JOIN trades t ON t.id = v.trade_id
        ORDER BY v.id DESC LIMIT ?
    """, (limit,))
