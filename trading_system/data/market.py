import os
import logging
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import datetime

from trading_system import config

logger = logging.getLogger(__name__)

BARS_BATCH_SIZE = 100


def get_historical_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])


def get_bars(symbols: list[str], days: int = config.BARS_LOOKBACK_DAYS) -> dict:
    """Daily bars for many symbols, fetched in batches. Symbols with no data map to []."""
    result = {symbol: [] for symbol in symbols}
    if not symbols:
        return result
    client = get_historical_client()
    start = datetime.datetime.now() - datetime.timedelta(days=days)
    for i in range(0, len(symbols), BARS_BATCH_SIZE):
        batch = symbols[i : i + BARS_BATCH_SIZE]
        try:
            bars = client.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=start,
            ))
            for symbol, symbol_bars in bars.data.items():
                result[symbol] = symbol_bars
        except Exception as e:
            logger.error(f"Failed to fetch market data for {len(batch)} symbols: {e}")
    return result


def _sma(values: list[float], n: int) -> float | None:
    return sum(values[-n:]) / n if len(values) >= n else None


def _rsi(closes: list[float], n: int = 14) -> float | None:
    if len(closes) <= n:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes[:-1], closes[1:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    # Wilder smoothing
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        avg_gain = (avg_gain * (n - 1) + g) / n
        avg_loss = (avg_loss * (n - 1) + l) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _atr(highs: list[float], lows: list[float], closes: list[float], n: int) -> float | None:
    if len(closes) <= n:
        return None
    true_ranges = [
        max(h - l, abs(h - prev_close), abs(l - prev_close))
        for h, l, prev_close in zip(highs[1:], lows[1:], closes[:-1])
    ]
    atr = sum(true_ranges[:n]) / n
    for tr in true_ranges[n:]:
        atr = (atr * (n - 1) + tr) / n
    return atr


def _pct_change(closes: list[float], n: int) -> float | None:
    if len(closes) <= n or closes[-1 - n] == 0:
        return None
    return closes[-1] / closes[-1 - n] - 1.0


def compute_features(bars) -> dict:
    """Summarize daily bars into the handful of numbers the LLM and risk engine need."""
    if not bars:
        return {}
    closes = [float(b.close) for b in bars]
    highs = [float(b.high) for b in bars]
    lows = [float(b.low) for b in bars]
    volumes = [float(b.volume) for b in bars]
    last = closes[-1]
    # Exclude the latest (possibly partial) bar from the volume baseline
    avg_volume_20d = _sma(volumes[:-1], 20)
    atr = _atr(highs, lows, closes, config.ATR_PERIOD)
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)

    def r(value, digits=4):
        return round(value, digits) if value is not None else None

    return {
        "last_close": r(last, 2),
        "return_1d": r(_pct_change(closes, 1)),
        "return_5d": r(_pct_change(closes, 5)),
        "return_20d": r(_pct_change(closes, 20)),
        "sma20": r(sma20, 2),
        "sma50": r(sma50, 2),
        "above_sma20": last > sma20 if sma20 else None,
        "above_sma50": last > sma50 if sma50 else None,
        "rsi14": r(_rsi(closes, 14), 1),
        "atr14": r(atr, 4),
        "atr_pct": r(atr / last, 4) if atr and last else None,
        "high_period": r(max(highs), 2),
        "low_period": r(min(lows), 2),
        "avg_volume_20d": round(avg_volume_20d) if avg_volume_20d else None,
        "relative_volume": r(volumes[-1] / avg_volume_20d, 2) if avg_volume_20d else None,
        "avg_dollar_volume_20d": round(avg_volume_20d * last) if avg_volume_20d else None,
        "bars_available": len(bars),
    }
