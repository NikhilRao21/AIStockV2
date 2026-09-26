from trading_system.research.triage import triage_score, select_top_n, eligibility_reason


def _features(**overrides):
    f = {"last_close": 20.0, "bars_available": 80, "atr14": 0.8, "avg_dollar_volume_20d": 50_000_000,
         "relative_volume": 1.0, "above_sma50": True}
    f.update(overrides)
    return f


def _cand(pct=0.05, news=0, **feature_overrides):
    return {"symbol": "X", "price": 20.0, "percent_change": pct, "news_count": news, "features": _features(**feature_overrides)}


def test_score_zero_for_penny_stock():
    assert triage_score(_cand(last_close=0.50)) == 0.0


def test_illiquid_excluded():
    assert eligibility_reason(_cand(avg_dollar_volume_20d=100_000)) == "illiquid"


def test_extreme_move_excluded():
    assert eligibility_reason(_cand(pct=1.5)) == "day move too extreme"


def test_missing_history_excluded():
    assert eligibility_reason({"symbol": "X", "price": 20.0, "features": {}}) == "insufficient price history"


def test_higher_relative_volume_scores_higher():
    assert triage_score(_cand(relative_volume=4.0)) > triage_score(_cand(relative_volume=1.0))


def test_components_are_capped():
    assert triage_score(_cand(pct=0.39, news=50, relative_volume=1000)) <= 1.0


def test_top_n_returns_correct_count_and_drops_ineligible():
    candidates = [_cand(pct=i / 100) for i in range(10)] + [_cand(last_close=1.0)]
    top = select_top_n(candidates, 3)
    assert len(top) == 3
    assert top[0]["percent_change"] == 0.09
