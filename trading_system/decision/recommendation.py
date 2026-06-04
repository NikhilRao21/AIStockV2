import json
import logging
import ast
import re

logger = logging.getLogger(__name__)

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "ticker",
        "action",
        "confidence",
        "bull_case",
        "bear_case",
        "supporting_evidence",
        "key_risks",
        "catalysts",
        "position_size_pct",
        "expected_holding_days",
        "reasoning_summary",
    ],
    "properties": {
        "ticker": {"type": "string"},
        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD", "NO_ACTION"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "bull_case": {"type": "string"},
        "bear_case": {"type": "string"},
        "supporting_evidence": {"type": "array", "items": {"type": "string"}},
        "key_risks": {"type": "array", "items": {"type": "string"}},
        "catalysts": {"type": "array", "items": {"type": "string"}},
        "position_size_pct": {"type": "number"},
        "expected_holding_days": {"type": "integer"},
        "reasoning_summary": {"type": "string"},
    },
}


def _normalize_position_size_pct(value):
    """
    Normalize recommendation sizing into a fractional pct.

    Accepts values like:
    - 0.05  -> 0.05
    - 5     -> 0.05
    - 2.5   -> 0.025
    """
    try:
        size_pct = float(value)
    except (TypeError, ValueError):
        return value

    if size_pct > 1:
        logger.warning("Normalizing position_size_pct from %s to %s", size_pct, size_pct / 100.0)
        size_pct = size_pct / 100.0

    return size_pct


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    return text


def _repair_json_text(text: str) -> str:
    repaired = text.strip()
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired


def _parse_json_like(text: str):
    candidates = [_extract_json_object(text)]
    for candidate in list(candidates):
        repaired = _repair_json_text(candidate)
        if repaired not in candidates:
            candidates.append(repaired)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    for candidate in candidates:
        try:
            return ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            pass

    raise json.JSONDecodeError("Unable to parse recommendation JSON", text, 0)

def parse_recommendation(raw_json: str, ticker: str | None = None) -> dict | None:
    try:
        data = _parse_json_like(raw_json)
        if not isinstance(data, dict):
            logger.error("Recommendation must decode to a JSON object")
            return None

        if ticker and not data.get("ticker"):
            data["ticker"] = ticker

        allowed_keys = set(RECOMMENDATION_SCHEMA["properties"].keys())
        extra_keys = sorted(set(data.keys()) - allowed_keys)
        if extra_keys:
            logger.error("Unexpected keys in recommendation: %s", ", ".join(extra_keys))
            return None

        for key in RECOMMENDATION_SCHEMA["required"]:
            if key not in data:
                logger.error(f"Missing required key in recommendation: {key}")
                return None

        if data["action"] not in RECOMMENDATION_SCHEMA["properties"]["action"]["enum"]:
            logger.error(f"Invalid action in recommendation: {data['action']}")
            return None

        conf = data.get("confidence", 0)
        if not (0.0 <= float(conf) <= 1.0):
            logger.error(f"Confidence out of range: {conf}")
            return None

        for key in ("supporting_evidence", "key_risks", "catalysts"):
            if not isinstance(data.get(key), list) or not all(isinstance(item, str) for item in data[key]):
                logger.error("Field %s must be an array of strings", key)
                return None

        if not isinstance(data.get("expected_holding_days"), int):
            try:
                data["expected_holding_days"] = int(data["expected_holding_days"])
            except (TypeError, ValueError):
                logger.error("expected_holding_days must be an integer")
                return None

        data["position_size_pct"] = _normalize_position_size_pct(data.get("position_size_pct"))

        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recommendation JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing recommendation: {e}")
        return None
