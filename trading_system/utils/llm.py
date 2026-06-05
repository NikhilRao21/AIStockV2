import os
import time
import requests
import logging
from threading import Lock

from trading_system import config

logger = logging.getLogger(__name__)

_rate_limit_lock = Lock()
_last_request_started_at = 0.0

def _wait_for_rate_limit():
    global _last_request_started_at

    interval = float(os.environ.get("AI_REQUEST_INTERVAL_SECONDS", config.AI_REQUEST_INTERVAL_SECONDS))
    if interval <= 0:
        return

    with _rate_limit_lock:
        elapsed = time.monotonic() - _last_request_started_at
        wait_seconds = interval - elapsed
        if wait_seconds > 0:
            logger.info("Waiting %.1f seconds before next LLM request", wait_seconds)
            time.sleep(wait_seconds)
        _last_request_started_at = time.monotonic()

def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str | None:
    for attempt in range(3):
        try:
            _wait_for_rate_limit()
            logger.info("Calling LLM")
            r = requests.post(
                f"{os.environ['AI_BASE_URL']}/chat/completions",
                headers={
                    "Authorization": "Bearer " + os.environ["AI_API_KEY"],
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.environ["AI_MODEL"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": int(os.environ.get("AI_MAX_TOKENS", 2000))
                },
                timeout=60
            )
            if r.status_code == 429 and attempt == 0:
                time.sleep(60)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed (attempt {attempt+1}): {e}")
    return None
