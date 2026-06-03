from trading_system.decision.recommendation import parse_recommendation

def test_valid_json_parses_correctly():
    raw = """
    {
      "ticker": "NVDA",
      "action": "BUY",
      "confidence": 0.78,
      "bull_case": "bull",
      "bear_case": "bear",
      "supporting_evidence": ["fact 1"],
      "key_risks": ["risk 1"],
      "catalysts": ["catalyst 1"],
      "position_size_pct": 0.04,
      "expected_holding_days": 5,
      "reasoning_summary": "summary"
    }
    """
    data = parse_recommendation(raw)
    assert data is not None
    assert data["ticker"] == "NVDA"

def test_missing_field_raises_error():
    raw = """
    {
      "ticker": "NVDA",
      "action": "BUY",
      "confidence": 0.78
    }
    """
    data = parse_recommendation(raw)
    assert data is None

def test_missing_ticker_uses_fallback():
    raw = """
    {
      "action": "BUY",
      "confidence": 0.78,
      "bull_case": "bull",
      "bear_case": "bear",
      "supporting_evidence": ["fact 1"],
      "key_risks": ["risk 1"],
      "catalysts": ["catalyst 1"],
      "position_size_pct": 0.04,
      "expected_holding_days": 5,
      "reasoning_summary": "summary"
    }
    """
    data = parse_recommendation(raw, ticker="NVDA")
    assert data is not None
    assert data["ticker"] == "NVDA"

def test_invalid_action_rejected():
    raw = """
    {
      "ticker": "NVDA",
      "action": "MAYBE",
      "confidence": 0.78,
      "bull_case": "bull",
      "bear_case": "bear",
      "supporting_evidence": ["fact 1"],
      "key_risks": ["risk 1"],
      "catalysts": ["catalyst 1"],
      "position_size_pct": 0.04,
      "expected_holding_days": 5,
      "reasoning_summary": "summary"
    }
    """
    data = parse_recommendation(raw)
    assert data is None

def test_confidence_out_of_range_rejected():
    raw = """
    {
      "ticker": "NVDA",
      "action": "BUY",
      "confidence": 1.5,
      "bull_case": "bull",
      "bear_case": "bear",
      "supporting_evidence": ["fact 1"],
      "key_risks": ["risk 1"],
      "catalysts": ["catalyst 1"],
      "position_size_pct": 0.04,
      "expected_holding_days": 5,
      "reasoning_summary": "summary"
    }
    """
    data = parse_recommendation(raw)
    assert data is None
