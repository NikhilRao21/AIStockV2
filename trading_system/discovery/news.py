import os
import requests
import logging
import re

from trading_system import config

logger = logging.getLogger(__name__)

ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"

# Uppercase words that show up in headlines but are almost never meant as tickers,
# even when a listed symbol happens to match (e.g. AI, IPO, CEO).
TICKER_STOPWORDS = {
    "A", "AI", "AM", "ARE", "BE", "CEO", "CFO", "COO", "CTO", "EPS", "ETF", "EU", "EV", "FDA", "FED",
    "FOR", "GDP", "IPO", "IT", "NEW", "NOW", "NYSE", "ON", "ONE", "OR", "PM", "SEC", "SO", "TV", "UK",
    "US", "USA", "USD", "ALL", "ANY", "BIG", "CAN", "DD", "GO", "HAS", "LOW", "OUT", "RUN", "SEE", "TOP",
    "API", "CPI", "PPI", "FOMC", "YOY", "QOQ", "ESG", "IRS", "DOJ", "FTC", "OPEC", "NATO", "WHO", "NASDAQ",
}
EXPLICIT_TICKER = re.compile(r"(?:\$|\b(?:NYSE|NASDAQ|Nasdaq|AMEX|NYSEAMERICAN)\s*:\s*)([A-Z]{1,5}(?:\.[A-Z])?)\b")
BARE_TICKER = re.compile(r"\b[A-Z]{2,5}\b")


def _alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
        "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"],
        "accept": "application/json",
    }


def search_news_alpaca(symbols: str | list[str] | None = None, limit: int = config.NEWS_RESULTS_PER_TICKER) -> list[dict]:
    """Benzinga news via Alpaca. Each article carries the ticker symbols it is about."""
    try:
        params = {"limit": min(limit, 50), "sort": "desc", "include_content": "false"}
        if symbols:
            params["symbols"] = symbols if isinstance(symbols, str) else ",".join(symbols)
        r = requests.get(ALPACA_NEWS_URL, params=params, headers=_alpaca_headers(), timeout=10)
        r.raise_for_status()
        return [
            {
                "title": x.get("headline", ""),
                "url": x.get("url", ""),
                "description": x.get("summary", ""),
                "symbols": x.get("symbols", []),
                "created_at": x.get("created_at"),
            }
            for x in r.json().get("news", [])
        ]
    except Exception as e:
        logger.warning(f"Alpaca news search failed for '{symbols}': {e}")
        return []


def search_news_langsearch(query: str, freshness: str = "oneDay", count: int = 30) -> list[dict]:
    """Free web search (1000 queries/day on the free tier). Used only for broad discovery."""
    try:
        api_key = os.environ.get("LANGSEARCH_API_KEY", "")
        if not api_key:
            logger.warning("LANGSEARCH_API_KEY not set. Skipping web news search.")
            return []

        r = requests.post(
            "https://api.langsearch.com/v1/web-search",
            json={"query": query, "freshness": freshness, "summary": True, "count": count},
            headers={"Authorization": "Bearer " + api_key},
            timeout=20,
        )
        r.raise_for_status()
        results = r.json()["data"]["webPages"]["value"]
        return [
            {"title": x.get("name", ""), "url": x.get("url", ""), "description": x.get("summary") or x.get("snippet", "")}
            for x in results
        ]
    except Exception as e:
        logger.warning(f"LangSearch failed for '{query}': {e}")
        return []


def extract_tickers_from_news(articles: list[dict], valid_symbols: set[str]) -> dict[str, int]:
    """
    Map ticker -> number of articles mentioning it.

    Uses the article's tagged symbols when present (Alpaca), otherwise explicit mentions like
    "$NVDA" or "(NASDAQ: NVDA)", and finally bare uppercase words. Everything is validated
    against the tradable universe so words like "CEO" or "USA" are dropped.
    """
    counts: dict[str, int] = {}
    for article in articles:
        found = set(article.get("symbols") or [])
        if not found:
            text = article.get("title", "") + " " + article.get("description", "")
            found.update(EXPLICIT_TICKER.findall(text))
            found.update(w for w in BARE_TICKER.findall(text) if w not in TICKER_STOPWORDS)
        for symbol in found:
            if symbol in valid_symbols:
                counts[symbol] = counts.get(symbol, 0) + 1
    return counts
