import os
import logging
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import datetime

logger = logging.getLogger(__name__)

def get_historical_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])

def get_bars(symbols: list[str], days: int = 60) -> dict:
    if not symbols:
        return {}
    try:
        client = get_historical_client()
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.datetime.now() - datetime.timedelta(days=days),
            end=datetime.datetime.now()
        )
        bars = client.get_stock_bars(request)
        
        # bars is a dict-like or iterable
        result = {}
        for symbol in symbols:
            if symbol in bars:
                result[symbol] = bars[symbol]
            else:
                result[symbol] = []
        return result
    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
        return {}
