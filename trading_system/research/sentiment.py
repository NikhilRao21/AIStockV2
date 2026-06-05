import json
import logging
from trading_system.utils.llm import call_llm

logger = logging.getLogger(__name__)

def analyze_sentiment(ticker: str, articles: list[dict]) -> dict:
    default_res = {"score": 0.0, "themes": [], "summary": "No news"}
    if not articles:
        return default_res
        
    sys_prompt = "You are a sentiment analyzer. Reply ONLY in JSON format: {\"score\": 0.5, \"themes\": [\"growth\"], \"summary\": \"positive\"}. Score must be float -1.0 to 1.0."
    user_prompt = f"Analyze sentiment for {ticker} based on these articles: {json.dumps(articles)}"
    
    raw = call_llm(sys_prompt, user_prompt, model="openai/gpt-5.4-nano")
    if raw:
        try:
            # simple strip
            clean = raw.strip()
            if clean.startswith("```json"): clean = clean[7:]
            elif clean.startswith("```"): clean = clean[3:]
            if clean.endswith("```"): clean = clean[:-3]
            res = json.loads(clean)
            res["score"] = max(-1.0, min(1.0, float(res.get("score", 0.0))))
            return res
        except Exception as e:
            logger.error(f"Failed to parse sentiment for {ticker}: {e}")
            
    return default_res
