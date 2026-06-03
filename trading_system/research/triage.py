import logging
from trading_system import config

logger = logging.getLogger(__name__)

def _coerce_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)) and value:
        return _coerce_float(value[0], default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def triage_score(candidate: dict) -> float:
    pct = abs(_coerce_float(candidate.get("percent_change", 0)))
    volume = _coerce_float(candidate.get("volume", 0))
    avg_volume = max(_coerce_float(candidate.get("avg_volume_30d", 1), 1.0), 1.0)
    vol_mult = volume / avg_volume
    news = min(_coerce_float(candidate.get("news_count", 0)), 5) / 5.0
    price_ok = 1.0 if _coerce_float(candidate.get("price", 0)) >= config.MIN_STOCK_PRICE else 0.0

    return price_ok * (pct * 0.4 + vol_mult * 0.4 + news * 0.2)

def select_top_n(candidates: list[dict], n: int) -> list[dict]:
    # Set avg_volume_30d to 1 if not present to avoid division by zero above
    for cand in candidates:
        if "avg_volume_30d" not in cand:
            cand["avg_volume_30d"] = 1
            
        cand["triage_score"] = triage_score(cand)
        
    sorted_candidates = sorted(candidates, key=lambda x: x["triage_score"], reverse=True)
    return sorted_candidates[:n]
