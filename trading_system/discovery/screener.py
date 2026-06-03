import os
import logging
from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.requests import MostActivesRequest, MarketMoversRequest
from alpaca.data.enums import MarketType, MostActivesBy
from trading_system import config

logger = logging.getLogger(__name__)

def _coerce_number(value, default=0.0):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)) and value:
        return _coerce_number(value[0], default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _get_attr(item, name, index=None, default=None):
    if hasattr(item, name):
        return getattr(item, name)
    if index is not None:
        try:
            return item[index]
        except (IndexError, TypeError):
            return default
    return default

def get_screener_client() -> ScreenerClient:
    return ScreenerClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])

def get_candidates() -> list[dict]:
    try:
        client = get_screener_client()
        candidates = {}

        actives_req = MostActivesRequest(
            top=config.SCREENER_TOP_N,
            by=MostActivesBy.volume,
            market_type=MarketType.STOCKS,
        )
        actives = client.get_most_actives(actives_req)
        for act in actives:
            symbol = _get_attr(act, "symbol", 0)
            if not symbol:
                continue
            if symbol not in candidates:
                candidates[symbol] = {
                    "symbol": symbol,
                    "volume": _coerce_number(_get_attr(act, "volume", 1, 0)),
                    "price": _coerce_number(_get_attr(act, "price", 2, 0.0)),
                    "percent_change": 0.0,
                    "news_count": 0
                }

        movers_req = MarketMoversRequest(top=config.SCREENER_TOP_N, market_type=MarketType.STOCKS)
        movers = client.get_market_movers(movers_req)
        
        for gainer in movers.gainers:
            symbol = _get_attr(gainer, "symbol", 0)
            if not symbol:
                continue
            if symbol not in candidates:
                candidates[symbol] = {
                    "symbol": symbol,
                    "volume": 0,
                    "price": _coerce_number(_get_attr(gainer, "price", 1, 0.0)),
                    "percent_change": _coerce_number(_get_attr(gainer, "percent_change", 2, 0.0)),
                    "news_count": 0
                }
            else:
                candidates[symbol]["percent_change"] = _coerce_number(_get_attr(gainer, "percent_change", 2, 0.0))

        for loser in movers.losers:
            symbol = _get_attr(loser, "symbol", 0)
            if not symbol:
                continue
            if symbol not in candidates:
                candidates[symbol] = {
                    "symbol": symbol,
                    "volume": 0,
                    "price": _coerce_number(_get_attr(loser, "price", 1, 0.0)),
                    "percent_change": _coerce_number(_get_attr(loser, "percent_change", 2, 0.0)),
                    "news_count": 0
                }
            else:
                candidates[symbol]["percent_change"] = _coerce_number(_get_attr(loser, "percent_change", 2, 0.0))

        return list(candidates.values())
    except Exception as e:
        logger.error(f"Failed to fetch candidates from screener: {e}")
        return []
