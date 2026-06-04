import json
import logging
from datetime import datetime

from trading_system import config
from trading_system.data import market
from trading_system.decision import recommendation
from trading_system.discovery import news, screener
from trading_system.execution import alpaca_client, orders, risk
from trading_system.journal import db
from trading_system.research import sentiment, triage, thesis

logger = logging.getLogger(__name__)


def _get_order_attr(order, name, default=None):
    return getattr(order, name, default) if order is not None else default


def _build_trade_row(rec: dict, order, action: str) -> dict:
    notional = rec.get("notional")
    if notional is None:
        portfolio_value = rec.get("portfolio_value")
        position_pct = rec.get("position_size_pct")
        if portfolio_value is not None and position_pct is not None:
            notional = float(portfolio_value) * float(position_pct)

    return {
        "recommendation_id": rec.get("recommendation_id"),
        "ticker": rec.get("ticker"),
        "side": action,
        "notional": float(notional) if notional is not None else None,
        "fill_price": float(_get_order_attr(order, "filled_avg_price")) if _get_order_attr(order, "filled_avg_price") not in (None, "") else None,
        "fill_time": datetime.now().isoformat(),
        "closed_by": None,
        "outcome": str(_get_order_attr(order, "status", "")).upper() or None,
    }


def run_sweep(sweep_name: str):
    logger.info("Starting sweep: %s", sweep_name)
    try:
        logger.info("Initializing Alpaca trading client")
        trading_client = alpaca_client.get_trading_client()
        logger.info("Fetching Alpaca account")
        account = trading_client.get_account()
        logger.info("Fetching Alpaca positions")
        positions = trading_client.get_all_positions()
        positionString = ";".join(["{} shares of {}".format(p.qty, p.symbol) for p in positions])
        logger.info("Fetching Alpaca clock")
        clock = trading_client.get_clock()
        logger.info("Reached Alpaca")

    except Exception as e:
        logger.exception("Failed to initialize Alpaca clients during sweep startup")
        return

    peak_value = db.get_peak_value()
    day_start_value = float(account.portfolio_value)
    logger.info("Portfolio value at day start: %s", day_start_value)


    candidates = screener.get_candidates()
    logger.info("Found %s screener candidates", len(candidates))

    broad_articles = news.search_news_langsearch("stock market movers today")
    news_tickers = news.extract_tickers_from_news(broad_articles)
    logger.info("Found %s tickers from the news", news_tickers.__len__)
    
    for ticker in news_tickers:
        if len(candidates) >= config.MAX_CANDIDATES:
            break
        if not any(c["symbol"] == ticker for c in candidates):
            candidates.append({
                "symbol": ticker,
                "volume": 1000,
                "price": 10,
                "percent_change": 0,
                "news_count": 1,
            })

    top_candidates = triage.select_top_n(candidates, config.DEEP_ANALYSIS_TOP_N)
    logger.info("Selected %s candidates for deep analysis", len(top_candidates))

    sweep_entries = 0
    count = 0

    for cand in top_candidates:
        count += 1
        if sweep_entries >= config.MAX_ENTRIES_PER_SWEEP:
            logger.info("Max sweep entries reached")
            break

        ticker = cand["symbol"]
        logger.info("Analyzing %s. This is number %d of %d", ticker, count, config.DEEP_ANALYSIS_TOP_N)

        bars = market.get_bars([ticker])
        articles = news.search_news_alpaca(ticker)
        logger.info("Found %s news articles for %s", len(articles), ticker)
        sent = sentiment.analyze_sentiment(ticker, articles)
        logger.info("Analyzed Sentiment for %s", ticker)
        bull = thesis.generate_bull_thesis(ticker, bars.get(ticker, []), sent, articles)
        logger.info("Analyzed Bull Thesis for %s", ticker)
        bear = thesis.generate_bear_thesis(ticker, bars.get(ticker, []), sent, articles)
        logger.info("Analyzed Bear Thesis for %s", ticker)

        sys_prompt = (
            "You are a quantitative portfolio manager. Return exactly one valid JSON object and nothing else. "
            "Do not use markdown fences, code blocks, bullet points, headings, or commentary. "
            "Use double quotes for all keys and string values. Do not include trailing commas. "
            "Do not include any extra keys beyond the required schema."
        )
        user_prompt = (
            f"Ticker: {ticker}\n"
            f"Bull Thesis: {bull}\n"
            f"Bear Thesis: {bear}\n"
            f"Sentiment: {sent}\n"
            f"Bars: {bars}\n"
            f"Positions (if empty, no positions): {positionString}\n"
            "Return one JSON object matching this schema exactly:\n"
            "{\n"
            '  "ticker": "string",\n'
            '  "action": "BUY|SELL|HOLD|NO_ACTION",\n'
            '  "confidence": 0.0,\n'
            '  "bull_case": "string",\n'
            '  "bear_case": "string",\n'
            '  "supporting_evidence": ["string"],\n'
            '  "key_risks": ["string"],\n'
            '  "catalysts": ["string"],\n'
            '  "position_size_pct": 0.0,\n'
            '  "expected_holding_days": 1,\n'
            '  "reasoning_summary": "string"\n'
            "}\n"
            "Schema rules:\n"
            "- Output one JSON object only.\n"
            "- No markdown fences, no prose, no code blocks.\n"
            "- Use double quotes for every key and string value.\n"
            "- Do not include any keys besides the schema above.\n"
            "- `action` must be one of BUY, SELL, HOLD, NO_ACTION.\n"
            "- `confidence` must be a number from 0 to 1.\n"
            "- `supporting_evidence`, `key_risks`, and `catalysts` must be arrays of strings.\n"
            "- `position_size_pct` must be a decimal fraction like 0.04 for 4%.\n"
            "- `expected_holding_days` must be an integer.\n"
            "action must be one of BUY, SELL, HOLD, NO_ACTION. You can only sell or hold a position if you currently hold it. DO NOT SELL POSITIONS YOU DO NOT HOLD. "
            "Use confidence like this: 0.90+ only for unusually strong, multi-factor setups with clear evidence across price, volume, news, and thesis; "
            "0.70 to 0.89 for solid setups with several aligned signals; 0.55 to 0.69 for acceptable but not high-conviction ideas; "
            "below 0.55 only when the best action is NO_ACTION or HOLD. "
            "If you cannot comply exactly, still return a single valid JSON object with all required keys."
            f"The ticker value must be {ticker}."
        )

        from trading_system.utils.llm import call_llm

        raw_rec = call_llm(sys_prompt, user_prompt)
        logger.info("Generated Recommendation for %s.", ticker)

        if not raw_rec:
            logger.warning("LLM did not return a recommendation for %s", ticker)
            continue

        rec = recommendation.parse_recommendation(raw_rec, ticker=ticker)
        if not rec:
            logger.warning("LLM did not return a recommendation for %s", ticker)
            continue

        rec["price_at_signal"] = cand["price"]
        rec["portfolio_value"] = float(account.portfolio_value)
        rec["news_sources"] = json.dumps([{"title": a["title"], "url": a["url"]} for a in articles])
        rec["triage_score"] = cand["triage_score"]
        rec["created_at"] = datetime.now().isoformat()
        rec["sweep"] = sweep_name

        passed, reasons = risk.run_all_checks(
            rec, account, positions, clock, peak_value, day_start_value, sweep_entries
        )
        action = str(rec.get("action", "")).upper()

        logger.info("%s passed all checks. Executing Order of type: %s", ticker, action)


        order = None
        if passed and sweep_name != "premarket":
            try:
                if action == "BUY":
                    order = orders.submit_order(trading_client, rec)
                    rec["order_submitted"] = 1
                    rec["order_id"] = str(_get_order_attr(order, "id"))
                elif action == "SELL":
                    order = trading_client.close_position(ticker)
                    rec["order_submitted"] = 1
                    rec["order_id"] = str(_get_order_attr(order, "id"))
                else:
                    rec["order_submitted"] = 0

                if rec.get("order_submitted"):
                    sweep_entries += 1
                    logger.info("Order %s submitted for %s", action, ticker)
            except Exception as e:
                logger.exception("Order %s failed for %s: %s", action, ticker, e)
                rec["order_submitted"] = 0
                rec["risk_block_reasons"] = json.dumps([str(e)])
        else:
            rec["order_submitted"] = 0
            rec["risk_block_reasons"] = json.dumps(reasons)
            logger.info("Order blocked or skipped for %s: %s", ticker, reasons)

        rec_copy = rec.copy()
        for key in ["supporting_evidence", "key_risks", "catalysts"]:
            if key in rec_copy and not isinstance(rec_copy[key], str):
                rec_copy[key] = json.dumps(rec_copy[key])

        recommendation_id = db.insert_recommendation({
            k: v for k, v in rec_copy.items()
            if k in [
                "created_at", "sweep", "ticker", "action", "confidence", "price_at_signal",
                "portfolio_value", "bull_case", "bear_case", "supporting_evidence", "key_risks",
                "catalysts", "news_sources", "triage_score", "position_size_pct",
                "expected_holding_days", "reasoning_summary", "order_id", "order_submitted",
                "risk_block_reasons",
            ]
        })

        if order is not None and rec.get("order_submitted"):
            trade_row = _build_trade_row({**rec, "recommendation_id": recommendation_id}, order, str(rec.get("action", "")).upper())
            db.insert_trade(trade_row)

    logger.info("Finished sweeping %s. Total orders submitted: %d", sweep_name, sweep_entries)
