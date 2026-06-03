from trading_system.research.triage import triage_score, select_top_n

def test_score_zero_for_penny_stock():
    cand = {"price": 0.50, "percent_change": 0.10, "volume": 10000, "avg_volume_30d": 1000, "news_count": 1}
    score = triage_score(cand)
    assert score == 0.0

def test_higher_volume_multiple_scores_higher():
    cand1 = {"price": 10.0, "percent_change": 0.10, "volume": 1000, "avg_volume_30d": 1000, "news_count": 0}
    cand2 = {"price": 10.0, "percent_change": 0.10, "volume": 5000, "avg_volume_30d": 1000, "news_count": 0}
    assert triage_score(cand2) > triage_score(cand1)

def test_top_n_returns_correct_count():
    candidates = [{"price": 10, "percent_change": i, "volume": 1000, "avg_volume_30d": 1000, "news_count": 0} for i in range(10)]
    top = select_top_n(candidates, 3)
    assert len(top) == 3
    assert top[0]["percent_change"] == 9
