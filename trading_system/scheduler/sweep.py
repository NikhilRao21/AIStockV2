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
        trading_client = alpaca_client.get_trading_client()
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()
        clock = trading_client.get_clock()
    except Exception as e:
        logger.error("Failed to initialize clients: %s", e)
        return

    peak_value = db.get_peak_value()
    day_start_value = float(account.portfolio_value)

    candidates = screener.get_candidates()
    logger.info("Found %s screener candidates", len(candidates))

    broad_articles = news.search_news("stock market movers today")
    news_tickers = news.extract_tickers_from_news(broad_articles)

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

    for cand in top_candidates:
        if sweep_entries >= config.MAX_ENTRIES_PER_SWEEP:
            logger.info("Max sweep entries reached")
            break

        ticker = cand["symbol"]
        logger.info("Analyzing %s", ticker)

        bars = market.get_bars([ticker])
        articles = news.search_news(f"{ticker} stock news")
        sent = sentiment.analyze_sentiment(ticker, articles)
        bull = thesis.generate_bull_thesis(ticker, bars.get(ticker, []), sent, articles)
        bear = thesis.generate_bear_thesis(ticker, bars.get(ticker, []), sent, articles)

        sys_prompt = "You are a quantitative portfolio manager. Return only valid JSON, with no markdown or commentary."
        user_prompt = (
            f"Ticker: {ticker}\n"
            f"Bull Thesis: {bull}\n"
            f"Bear Thesis: {bear}\n"
            f"Sentiment: {sent}\n"
            f"Bars: {bars}\n"
            "Produce JSON with exactly these keys: ticker, action, confidence (a number from 0 to 1), bull_case, bear_case, "
            "supporting_evidence, key_risks, catalysts, position_size_pct, expected_holding_days, "
            "reasoning_summary. action must be one of BUY, SELL, HOLD, NO_ACTION. "
            f"The ticker value must be {ticker}."
        )

        from trading_system.utils.llm import call_llm

        raw_rec = call_llm(sys_prompt, user_prompt)
        if not raw_rec:
            continue

        rec = recommendation.parse_recommendation(raw_rec, ticker=ticker)
        if not rec:
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

        order = None
        if passed and sweep_name != "premarket":
            try:
                action = str(rec.get("action", "")).upper()
                if action == "BUY":
                    order = orders.submit_order(trading_client, rec)
                    rec["order_submitted"] = 1
                    rec["order_id"] = _get_order_attr(order, "id")
                elif action == "SELL":
                    order = trading_client.close_position(ticker)
                    rec["order_submitted"] = 1
                    rec["order_id"] = _get_order_attr(order, "id")
                else:
                    rec["order_submitted"] = 0

                if rec.get("order_submitted"):
                    sweep_entries += 1
                    logger.info("Order submitted for %s", ticker)
            except Exception as e:
                logger.error("Order failed for %s: %s", ticker, e)
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
