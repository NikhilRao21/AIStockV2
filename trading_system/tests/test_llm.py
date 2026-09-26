from trading_system.utils.llm import parse_json_like, strip_reasoning


def test_strip_think_block():
    assert strip_reasoning("<think>hmm {x}</think>\nhello") == "hello"


def test_parse_json_after_think_block():
    assert parse_json_like('<think>maybe {"a": 2}</think>```json\n{"a": 1,}\n```') == {"a": 1}
