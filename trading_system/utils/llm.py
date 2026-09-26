import ast
import json
import os
import re
import time
import requests
import logging
from threading import Lock

from trading_system import config

logger = logging.getLogger(__name__)

_rate_limit_lock = Lock()
_last_request_started_at = 0.0
_json_mode_supported = True

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def _wait_for_rate_limit():
    global _last_request_started_at

    interval = float(os.environ.get("AI_REQUEST_INTERVAL_SECONDS", config.AI_REQUEST_INTERVAL_SECONDS))
    if interval <= 0:
        return

    with _rate_limit_lock:
        elapsed = time.monotonic() - _last_request_started_at
        wait_seconds = interval - elapsed
        if wait_seconds > 0:
            logger.debug("Waiting %.1f seconds before next LLM request", wait_seconds)
            time.sleep(wait_seconds)
        _last_request_started_at = time.monotonic()


def fast_model() -> str | None:
    return config.AI_FAST_MODEL or os.environ.get("AI_MODEL")


def strip_reasoning(text: str) -> str:
    """Drop <think>...</think> blocks emitted by reasoning models (qwen3, deepseek-r1)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def call_llm(system_prompt: str, user_prompt: str, temperature: float = config.AI_TEMPERATURE,
             model: str | None = None, json_mode: bool = False) -> str | None:
    global _json_mode_supported
    if model is None:
        model = os.environ.get("AI_MODEL")

    for attempt in range(MAX_ATTEMPTS):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": config.AI_MAX_TOKENS,
        }
        use_json_mode = json_mode and _json_mode_supported
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            _wait_for_rate_limit()
            logger.debug("Calling LLM model=%s", model)
            r = requests.post(
                f"{os.environ['AI_BASE_URL'].rstrip('/')}/chat/completions",
                headers={
                    "Authorization": "Bearer " + os.environ["AI_API_KEY"],
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=config.AI_TIMEOUT_SECONDS,
            )
            if r.status_code == 400 and use_json_mode:
                logger.warning("Provider rejected response_format=json_object; disabling JSON mode")
                _json_mode_supported = False
                continue
            if r.status_code in RETRYABLE_STATUS:
                backoff = min(60, 5 * 2 ** attempt)
                logger.warning("LLM returned %s (attempt %d); retrying in %ds", r.status_code, attempt + 1, backoff)
                time.sleep(backoff)
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return strip_reasoning(content) if content else None
        except Exception as e:
            logger.error(f"LLM call failed (attempt {attempt+1}): {e}")
            time.sleep(min(30, 2 ** attempt))
    return None


def _extract_json_object(raw_text: str) -> str:
    text = strip_reasoning(raw_text)

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    return text


def _repair_json_text(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text.strip())


def parse_json_like(text: str):
    """Parse an LLM reply into a Python object, tolerating fences, <think> blocks and trailing commas."""
    candidates = [_extract_json_object(text)]
    repaired = _repair_json_text(candidates[0])
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

    raise json.JSONDecodeError("Unable to parse LLM JSON", text, 0)


def call_llm_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict | None:
    raw = call_llm(system_prompt, user_prompt, model=model, json_mode=True)
    if not raw:
        return None
    try:
        data = parse_json_like(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON: %s", e)
        return None
    return data if isinstance(data, dict) else None
