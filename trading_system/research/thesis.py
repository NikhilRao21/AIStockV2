from trading_system.utils.llm import call_llm

def generate_bull_thesis(ticker: str, bars, sentiment: dict, articles: list[dict]) -> str:
    sys_prompt = "You are a bullish analyst. Formulate a strong bull thesis. Argue for the upside potential. Be concise."
    user_prompt = f"Ticker: {ticker}\nSentiment: {sentiment}\nFormulate bull thesis."
    res = call_llm(sys_prompt, user_prompt)
    return res or "No bull thesis generated."

def generate_bear_thesis(ticker: str, bars, sentiment: dict, articles: list[dict]) -> str:
    sys_prompt = "You are a bearish short-seller. Argue vehemently AGAINST the position regardless of the data. Focus on downside risks, dilution, macro headwinds."
    user_prompt = f"Ticker: {ticker}\nSentiment: {sentiment}\nFormulate bear thesis."
    res = call_llm(sys_prompt, user_prompt)
    return res or "No bear thesis generated."
