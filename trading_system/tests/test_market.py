from types import SimpleNamespace

from trading_system.data.market import compute_features, _rsi


def _bars(closes, volume=1_000_000):
    return [SimpleNamespace(open=c, high=c + 1, low=c - 1, close=c, volume=volume) for c in closes]


def test_features_on_uptrend():
    f = compute_features(_bars([float(x) for x in range(10, 70)]))
    assert f["last_close"] == 69.0
    assert f["above_sma20"] and f["above_sma50"]
    assert f["rsi14"] == 100.0
    # high-low = 2 and |h - prev close| = 2 every day
    assert f["atr14"] == 2.0
    assert f["relative_volume"] == 1.0
    assert f["return_1d"] == round(69 / 68 - 1, 4)


def test_features_empty():
    assert compute_features([]) == {}


def test_rsi_needs_history():
    assert _rsi([1.0, 2.0], 14) is None
