import os
import logging
from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.requests import MostActivesRequest, MarketMoversRequest
from alpaca.data.enums import MarketType
from trading_system import config

logger = logging.getLogger(__name__)

def get_screener_client() -> ScreenerClient:
    return ScreenerClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])

def get_candidates() -> list[dict]:
    try:
        client = get_screener_client()
        candidates = {}

        actives_req = MostActivesRequest(top=config.SCREENER_TOP_N, market_type=MarketType.STOCKS)
        actives = client.get_most_actives(actives_req)
        for act in actives:
            if act.symbol not in candidates:
                candidates[act.symbol] = {
                    "symbol": act.symbol,
                    "volume": act.volume,
                    "price": act.price,
                    "percent_change": 0.0,
                    "news_count": 0
                }

        movers_req = MarketMoversRequest(top=config.SCREENER_TOP_N, market_type=MarketType.STOCKS)
        movers = client.get_market_movers(movers_req)
        
        for gainer in movers.gainers:
            if gainer.symbol not in candidates:
                candidates[gainer.symbol] = {
                    "symbol": gainer.symbol,
                    "volume": 0,
                    "price": gainer.price,
                    "percent_change": gainer.percent_change,
                    "news_count": 0
                }
            else:
                candidates[gainer.symbol]["percent_change"] = gainer.percent_change

        for loser in movers.losers:
            if loser.symbol not in candidates:
                candidates[loser.symbol] = {
                    "symbol": loser.symbol,
                    "volume": 0,
                    "price": loser.price,
                    "percent_change": loser.percent_change,
                    "news_count": 0
                }
            else:
                candidates[loser.symbol]["percent_change"] = loser.percent_change

        return list(candidates.values())
    except Exception as e:
        logger.error(f"Failed to fetch candidates from screener: {e}")
        return []

