from trading_system.discovery.news import extract_tickers_from_news

UNIVERSE = {"NVDA", "AAPL", "AI", "IPO", "TSLA"}


def test_uses_tagged_symbols():
    articles = [{"title": "Chips rally", "description": "", "symbols": ["NVDA", "ZZZZ"]}]
    assert extract_tickers_from_news(articles, UNIVERSE) == {"NVDA": 1}


def test_filters_stopwords_and_unknown_words():
    articles = [{"title": "CEO says AI IPO boom lifts USA stocks", "description": "AAPL up"}]
    assert extract_tickers_from_news(articles, UNIVERSE) == {"AAPL": 1}


def test_explicit_mentions_bypass_stopwords():
    articles = [{"title": "C3 (NYSE: AI) jumps", "description": "also $TSLA"}]
    assert extract_tickers_from_news(articles, UNIVERSE) == {"AI": 1, "TSLA": 1}


def test_counts_articles():
    articles = [{"title": "NVDA up", "description": ""}, {"title": "NVDA again", "description": "NVDA"}]
    assert extract_tickers_from_news(articles, UNIVERSE) == {"NVDA": 2}
