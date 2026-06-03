import sqlite3
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = "trading_system.db"

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
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def insert_recommendation(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            keys = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            cursor.execute(f"INSERT INTO recommendations ({keys}) VALUES ({placeholders})", tuple(data.values()))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert recommendation: {e}")
        return -1

def insert_trade(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            keys = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            cursor.execute(f"INSERT INTO trades ({keys}) VALUES ({placeholders})", tuple(data.values()))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert trade: {e}")
        return -1

def insert_portfolio_snapshot(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            keys = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            cursor.execute(f"INSERT INTO portfolio_snapshots ({keys}) VALUES ({placeholders})", tuple(data.values()))
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
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            cursor.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", tuple(data.values()) + (trade_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update trade: {e}")

def insert_review(data: dict) -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            keys = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            cursor.execute(f"INSERT INTO reviews ({keys}) VALUES ({placeholders})", tuple(data.values()))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert review: {e}")
        return -1
