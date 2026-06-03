import os
import requests
import logging
import re

logger = logging.getLogger(__name__)

def search_news(query: str, freshness: str = "pd") -> list[dict]:
    try:
        api_key = os.environ.get("HC_SEARCH_API_KEY", "")
        if not api_key:
            logger.warning("HC_SEARCH_API_KEY not set. Skipping news search.")
            return []
            
        r = requests.get(
            "https://search.hackclub.com/res/v1/news/search",
            params={"q": query, "count": 5, "freshness": freshness},
            headers={"Authorization": "Bearer " + api_key},
            timeout=10
        )
        r.raise_for_status()
        results = r.json().get("news", {}).get("results", [])
        return [{"title": x["title"], "url": x["url"], "description": x.get("description", "")} for x in results]
    except Exception as e:
        logger.warning(f"News search failed for '{query}': {e}")
        return []

def extract_tickers_from_news(articles: list[dict]) -> set[str]:
    tickers = set()
    pattern = re.compile(r'\b[A-Z]{2,5}\b')
    for article in articles:
        text = article.get("title", "") + " " + article.get("description", "")
        matches = pattern.findall(text)
        tickers.update(matches)
    return tickers
