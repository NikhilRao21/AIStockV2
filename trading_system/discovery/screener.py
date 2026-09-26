import os
import logging
from datetime import date
from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import MostActivesRequest, MarketMoversRequest
from alpaca.data.enums import MarketType, MostActivesBy
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.trading.requests import GetAssetsRequest
from trading_system import config
from trading_system.execution import alpaca_client

logger = logging.getLogger(__name__)

def _enum_value(enum_cls, value):
    for name in (value, value.upper()):
        if hasattr(enum_cls, name):
            return getattr(enum_cls, name)
    try:
        return enum_cls(value)
    except ValueError:
        return value

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

def get_historical_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])


_universe_cache: tuple[date, set[str]] | None = None


def get_tradable_universe() -> set[str]:
    """Active, tradable, fractionable US equities on a listed exchange (no OTC). Cached per day."""
    global _universe_cache
    today = date.today()
    if _universe_cache and _universe_cache[0] == today:
        return _universe_cache[1]
    try:
        assets = alpaca_client.get_trading_client().get_all_assets(
            GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
        )
        symbols = {
            a.symbol for a in assets
            if a.tradable and a.fractionable and "OTC" not in str(a.exchange).upper()
        }
        _universe_cache = (today, symbols)
        logger.info("Loaded %d tradable symbols", len(symbols))
        return symbols
    except Exception as e:
        logger.error(f"Failed to load tradable universe: {e}")
        return _universe_cache[1] if _universe_cache else set()


def get_candidates() -> list[dict]:
    try:
        client = get_screener_client()
        candidates = {}

        actives_req = MostActivesRequest(
            top=config.SCREENER_TOP_N,
            by=_enum_value(MostActivesBy, "volume"),
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
                    "percent_change": _coerce_number(_get_attr(gainer, "percent_change", 2, 0.0)) / 100.0,
                    "news_count": 0
                }
            else:
                candidates[symbol]["percent_change"] = _coerce_number(_get_attr(gainer, "percent_change", 2, 0.0)) / 100.0

        for loser in movers.losers:
            symbol = _get_attr(loser, "symbol", 0)
            if not symbol:
                continue
            if symbol not in candidates:
                candidates[symbol] = {
                    "symbol": symbol,
                    "volume": 0,
                    "price": _coerce_number(_get_attr(loser, "price", 1, 0.0)),
                    "percent_change": _coerce_number(_get_attr(loser, "percent_change", 2, 0.0)) / 100.0,
                    "news_count": 0
                }
            else:
                candidates[symbol]["percent_change"] = _coerce_number(_get_attr(loser, "percent_change", 2, 0.0)) / 100.0

        universe = get_tradable_universe()
        if universe:
            candidates = {s: c for s, c in candidates.items() if s in universe}
        return list(candidates.values())
    except Exception as e:
        logger.error(f"Failed to fetch candidates from screener: {e}")
        return []
