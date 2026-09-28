import json
import logging
from datetime import datetime, timedelta, timezone

from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from trading_system import config, report
from trading_system.data import market
from trading_system.journal import db
from trading_system.utils.llm import call_llm, call_llm_json, fast_model

logger = logging.getLogger(__name__)

REVIEW_FIELDS = ["what_happened", "what_was_correct", "what_was_wrong", "risks_missed",
                 "sizing_appropriate", "would_take_again", "lessons_learned", "thesis_accuracy"]

REVIEW_SYSTEM_PROMPT = (
    "You are a quantitative portfolio manager doing a post-mortem on a closed swing trade. "
    "Judge the decision process, not just the outcome: a good decision can lose money and a bad one can win. "
    "Return exactly one JSON object with these keys and nothing else:\n"
    '{"what_happened": "string", "what_was_correct": "string", "what_was_wrong": "string", '
    '"risks_missed": "string", "sizing_appropriate": 0 or 1, "would_take_again": 0 or 1, '
    '"lessons_learned": "string", "thesis_accuracy": number from 0 to 1}'
)

SUMMARY_SYSTEM_PROMPT = (
    "You maintain the trading playbook for an automated swing-trading system. Rewrite the playbook as at most "
    "10 short, specific, actionable rules (plain text, one per line, no markdown headings) that the system should "
    "follow when choosing and managing trades. Base rules on patterns that recur across multiple trades and on the "
    "performance statistics; drop rules the evidence no longer supports. Do not add rules from a single anecdote."
)


def _price_path(ticker: str, start: str, end: str) -> str:
    try:
        client = market.get_historical_client()
        # fill_time is UTC-aware (from Alpaca), close_time is naive local; normalize both to aware.
        start_dt = datetime.fromisoformat(start).astimezone() - timedelta(days=5)
        # The free data plan rejects SIP queries that reach into the most recent 15 minutes.
        end_dt = min(datetime.fromisoformat(end).astimezone() + timedelta(days=1),
                     datetime.now(timezone.utc) - timedelta(minutes=16))
        bars = client.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start_dt, end=end_dt,
        )).data.get(ticker, [])
        return "\n".join(f"{b.timestamp.date()} O{b.open} H{b.high} L{b.low} C{b.close} V{int(b.volume)}" for b in bars)
    except Exception as e:
        logger.warning("Could not load price path for %s: %s", ticker, e)
        return "No bar data available."


def review_trade(trade: dict) -> bool:
    trade_view = {k: v for k, v in trade.items() if v is not None and k not in ("id", "recommendation_id")}
    user_prompt = (
        f"Closed trade and the original recommendation:\n{json.dumps(trade_view, default=str)}\n\n"
        f"Daily price path around the holding period:\n{_price_path(trade['ticker'], trade['fill_time'], trade['close_time'])}"
    )
    res = call_llm_json(REVIEW_SYSTEM_PROMPT, user_prompt, model=fast_model())
    if not res or any(k not in res for k in REVIEW_FIELDS):
        logger.error("Invalid review for trade %s: %s", trade["id"], res)
        return False
    db.insert_review({"trade_id": trade["id"], "created_at": datetime.now(), **{k: res[k] for k in REVIEW_FIELDS}})
    logger.info("Review added for trade %s (%s)", trade["id"], trade["ticker"])
    return True


def update_playbook():
    reviews = db.get_recent_reviews(limit=30)
    if not reviews:
        logger.info("No reviews yet; playbook unchanged")
        return
    previous = ""
    try:
        with open(config.REFLECTION_PATH, "r", encoding="utf-8") as file:
            previous = file.read()
    except FileNotFoundError:
        pass

    compact = [
        {k: r.get(k) for k in ("ticker", "pnl_pct", "closed_by", "what_was_wrong", "risks_missed",
                               "lessons_learned", "would_take_again", "thesis_accuracy")}
        for r in reviews
    ]
    user_prompt = (
        f"Performance statistics: {json.dumps(report.compute_stats())}\n\n"
        f"Current playbook:\n{previous or '(empty)'}\n\n"
        f"Most recent trade reviews (newest first):\n{json.dumps(compact, default=str)}"
    )
    res = call_llm(SUMMARY_SYSTEM_PROMPT, user_prompt, model=fast_model())
    if res:
        with open(config.REFLECTION_PATH, "w", encoding="utf-8") as file:
            file.write(res.strip() + "\n")
        logger.info("Playbook updated")


def generate_review():
    trades = db.get_unreviewed_closed_trades()
    logger.info("Reviewing %d closed trades", len(trades))
    reviewed = sum(review_trade(t) for t in trades)
    if reviewed:
        update_playbook()
