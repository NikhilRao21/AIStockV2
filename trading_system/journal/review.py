import json
import logging
from trading_system.utils.llm import call_llm
from trading_system.journal import db
from trading_system.discovery import screener
import pandas as pd
from pandas import DataFrame
from datetime import datetime
import requests
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)
DB_PATH = "trading_system.db"
import sqlite3


def generate_review():
    client = screener.get_historical_client()
    trades = None
    recommendations = None
    merged = None
    with sqlite3.connect(DB_PATH) as conn:
        trades = pd.read_sql_query("SELECT * FROM trades", conn)
        recommendations = pd.read_sql_query("SELECT * FROM recommendations", conn)
        merged = pd.merge(trades, recommendations, how="inner", left_on="recommendation_id", right_on="id")

    merged = merged[pd.to_datetime(merged["fill_time"]).dt.date == datetime.now().date()]
    headers = merged.columns.tolist()
    logger.info("Header: %s", headers)

    for row in merged.itertuples(index=True):
        try:
            # Fetch price bars for the ticker
            request_params = StockBarsRequest(
                symbol_or_symbols=row.ticker_x,
                timeframe=TimeFrame.Day,
                start=datetime(2026, 1, 1)
            )
            result = client.get_stock_bars(request_params)

            # Convert BarSet to a readable string for the prompt
            bars_df = result.df
            bars_df = result.df
            ticker_info = None
            if not bars_df.empty:
                # Reset multi-index if present (Alpaca returns symbol+timestamp index)
                if isinstance(bars_df.index, pd.MultiIndex):
                    bars_df = bars_df.reset_index(level=0, drop=True)
                # Only keep relevant columns, last 30 days
                cols = [c for c in ["open", "high", "low", "close", "volume", "vwap"] if c in bars_df.columns]
                ticker_info = bars_df[cols].tail(30).to_string()
            else:
                ticker_info = "No bar data available."

            sys_prompt = (
                "You are a quantitative portfolio manager. You will review certain trades."
                "Return exactly one valid JSON object and nothing else. "
                "Do not use markdown fences, code blocks, bullet points, headings, or commentary. "
                "Use double quotes for all keys and string values. Do not include trailing commas. "
                "Do not include any extra keys beyond the required schema."
            )
            user_prompt = (
                f"Input Data Schema: {headers}"
                f"Input Data: {row}"
                f"Ticker Info: {ticker_info}"
                "Return one JSON object matching this schema exactly:\n"
                "{\n"
                '  "what_happened": "string",\n'
                '  "what_was_correct": "string",\n'
                '  "what_was_wrong": "string",\n'
                '  "risks_missed": "string",\n'
                '  "bear_case": "string",\n'
                '  "sizing_appropriate": 0|1,\n'
                '  "would_take_again": 0|1,\n'
                '  "lessons_learned": "string",\n'
                '  "thesis_accuracy": float from 0 to 1\n'
                "}\n"
            )

            res = call_llm(sys_prompt, user_prompt, model="openai/gpt-5.4")
            clean = json.loads(res)

            data = {
                "trade_id": row.recommendation_id,
                "created_at": datetime.now(),           # Fixed: was missing ()
                "what_happened": clean["what_happened"],
                "what_was_correct": clean["what_was_correct"],
                "what_was_wrong": clean["what_was_wrong"],
                "risks_missed": clean["risks_missed"],
                "sizing_appropriate": clean["sizing_appropriate"],
                "would_take_again": clean["would_take_again"],
                "lessons_learned": clean["lessons_learned"],
                "thesis_accuracy": clean["thesis_accuracy"],
            }
            db.insert_review(data)
            logger.info("Review Added For: %s", row.ticker_x)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for trade {row.recommendation_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to generate review for trade {row.recommendation_id}: {e}")
            
            
    logger.info("Beginning Review Summary")
    with sqlite3.connect(DB_PATH) as conn:
        reviews = pd.read_sql_query("SELECT * FROM reviews", conn).to_string()
    sys_prompt = (
                "You are a quantitative portfolio manager. You will review reviews and generate a summary."
                "Return exactly one paragraph summarizing the reviews so far. "
                "Do not use markdown fences, code blocks, bullet points, headings, or commentary. "
                "Use double quotes for all keys and string values. Do not include trailing commas. "
                "Do not include any extra keys beyond the required schema."
            )
    user_prompt = (
        f"Reviews: {reviews}"
        "Generate ONE paragraph only. If there is no reviews, do not generate anything"
    )
    res = call_llm(sys_prompt, user_prompt, model="openai/gpt5.4")
    with open("summaryReflection.txt", "w") as file:
        file.write(res)
    