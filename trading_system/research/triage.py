import logging
from trading_system import config

logger = logging.getLogger(__name__)

MIN_BARS_FOR_ANALYSIS = 21  # need a 20-day volume baseline and an ATR


def _coerce_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)) and value:
        return _coerce_float(value[0], default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def eligibility_reason(candidate: dict) -> str | None:
    """Return why a candidate is excluded, or None if it may be analyzed."""
    features = candidate.get("features") or {}
    price = _coerce_float(features.get("last_close") or candidate.get("price"))
    if price < config.MIN_STOCK_PRICE:
        return f"price {price} below {config.MIN_STOCK_PRICE}"
    if features.get("bars_available", 0) < MIN_BARS_FOR_ANALYSIS or not features.get("atr14"):
        return "insufficient price history"
    if _coerce_float(features.get("avg_dollar_volume_20d")) < config.MIN_AVG_DOLLAR_VOLUME:
        return "illiquid"
    if abs(_coerce_float(candidate.get("percent_change"))) > config.MAX_ABS_DAY_MOVE:
        return "day move too extreme"
    return None


def triage_score(candidate: dict) -> float:
    """
    Cheap pre-LLM ranking in [0, 1]. Each component is capped so no single
    factor (e.g. a 300% squeeze or a mega-cap's raw volume) dominates.
    """
    if eligibility_reason(candidate):
        return 0.0
    features = candidate["features"]
    rel_volume = min(_coerce_float(features.get("relative_volume")), 5.0) / 5.0
    move = min(abs(_coerce_float(candidate.get("percent_change"))), 0.20) / 0.20
    news = min(_coerce_float(candidate.get("news_count", 0)), 5) / 5.0
    trend = 1.0 if features.get("above_sma50") else 0.0

    return rel_volume * 0.35 + move * 0.25 + news * 0.20 + trend * 0.20


def select_top_n(candidates: list[dict], n: int) -> list[dict]:
    for cand in candidates:
        cand["triage_score"] = triage_score(cand)

    eligible = [c for c in candidates if c["triage_score"] > 0]
    logger.info("%d of %d candidates passed triage filters", len(eligible), len(candidates))
    return sorted(eligible, key=lambda x: x["triage_score"], reverse=True)[:n]
