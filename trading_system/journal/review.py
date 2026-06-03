import logging
from trading_system.utils.llm import call_llm
from trading_system.journal import db

logger = logging.getLogger(__name__)

def generate_review(trade_id: int):
    # Mock review generation
    # real implementation would fetch trade, recommendation, etc.
    try:
        data = {
            "trade_id": trade_id,
            "created_at": "2023-01-01T12:00:00",
            "what_happened": "Stock went up",
            "what_was_correct": "Bull thesis",
            "what_was_wrong": "Nothing",
            "risks_missed": "None",
            "sizing_appropriate": 1,
            "would_take_again": 1,
            "lessons_learned": "Hold on tight",
            "thesis_accuracy": 0.9
        }
        db.insert_review(data)
    except Exception as e:
        logger.error(f"Failed to generate review: {e}")

