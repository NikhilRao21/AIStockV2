import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str | None:
    for attempt in range(2):
        try:
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
                timeout=30
            )
            if r.status_code == 429 and attempt == 0:
                time.sleep(60)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed (attempt {attempt+1}): {e}")
    return None
