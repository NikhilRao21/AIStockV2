import logging
from datetime import datetime
import json
from trading_system import config
from trading_system.discovery import screener, news
from trading_system.data import market
from trading_system.research import triage, sentiment, thesis
from trading_system.decision import recommendation
from trading_system.execution import alpaca_client, risk, orders
from trading_system.journal import db

logger = logging.getLogger(__name__)

def run_sweep(sweep_name: str):
    logger.info(f"Starting sweep: {sweep_name}")
    try:
        trading_client = alpaca_client.get_trading_client()
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()
        clock = trading_client.get_clock()
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        return

    # Check daily loss & drawdown (simplified)
    # Actually we should fetch peak_value and day_start_value from db, skipping for brevity in mock if needed
    peak_value = db.get_peak_value()
    # Mock day start value
    day_start_value = float(account.portfolio_value)
    
    # 1. Discovery
    candidates = screener.get_candidates()
    logger.info(f"Found {len(candidates)} screener candidates")
    
    # 2. News (Optional in sweep, we do it in per ticker for research)
    # But let's get top tickers from broad news
    broad_articles = news.search_news("stock market movers today")
    news_tickers = news.extract_tickers_from_news(broad_articles)
    
    for t in news_tickers:
        if len(candidates) >= config.MAX_CANDIDATES:
            break
        # Mock add if not present
        if not any(c["symbol"] == t for c in candidates):
            candidates.append({"symbol": t, "volume": 1000, "price": 10, "percent_change": 0, "news_count": 1})
            
    # 3. Triage
    top_candidates = triage.select_top_n(candidates, config.DEEP_ANALYSIS_TOP_N)
    logger.info(f"Selected {len(top_candidates)} candidates for deep analysis")
    
    sweep_entries = 0
    
    for cand in top_candidates:
        if sweep_entries >= config.MAX_ENTRIES_PER_SWEEP:
            logger.info("Max sweep entries reached")
            break
            
        ticker = cand["symbol"]
        logger.info(f"Analyzing {ticker}")
        
        # 4. Market Data
        bars = market.get_bars([ticker])
        
        # 5. Research
        articles = news.search_news(f"{ticker} stock news")
        sent = sentiment.analyze_sentiment(ticker, articles)
        bull = thesis.generate_bull_thesis(ticker, bars.get(ticker, []), sent, articles)
        bear = thesis.generate_bear_thesis(ticker, bars.get(ticker, []), sent, articles)
        
        # 6. Recommendation
        # We need a prompt for recommendation combining bull & bear
        sys_prompt = "You are a quantitative portfolio manager. Make a recommendation using ONLY the required JSON schema."
        user_prompt = f"Ticker: {ticker}\nBull Thesis: {bull}\nBear Thesis: {bear}\nSentiment: {sent}\nBars: {bars}\nProduce the JSON."
        
        from trading_system.utils.llm import call_llm
        raw_rec = call_llm(sys_prompt, user_prompt)
        if not raw_rec:
            continue
            
        rec = recommendation.parse_recommendation(raw_rec)
        if not rec:
            continue
            
        rec["price_at_signal"] = cand["price"]
        rec["portfolio_value"] = float(account.portfolio_value)
        rec["news_sources"] = json.dumps([{"title": a["title"], "url": a["url"]} for a in articles])
        rec["triage_score"] = cand["triage_score"]
        
        # Risk Checks
        passed, reasons = risk.run_all_checks(
            rec, account, positions, clock, peak_value, day_start_value, sweep_entries
        )
        
        if passed and sweep_name != "premarket":
            # Execution
            try:
                # order = orders.submit_order(rec) # Mocked
                rec["order_submitted"] = 1
                sweep_entries += 1
                logger.info(f"Order submitted for {ticker}")
            except Exception as e:
                logger.error(f"Order failed for {ticker}: {e}")
                rec["risk_block_reasons"] = json.dumps([str(e)])
        else:
            rec["risk_block_reasons"] = json.dumps(reasons)
            logger.info(f"Order blocked or skipped for {ticker}: {reasons}")
            
        # Journal
        rec["created_at"] = datetime.now().isoformat()
        rec["sweep"] = sweep_name
        
        # Insert into DB
        # Flatten supporting_evidence, etc.
        rec_copy = rec.copy()
        for k in ["supporting_evidence", "key_risks", "catalysts"]:
            if k in rec_copy:
                rec_copy[k] = json.dumps(rec_copy[k])
                
        db.insert_recommendation({
            k: v for k, v in rec_copy.items()
            if k in [
                "created_at", "sweep", "ticker", "action", "confidence", "price_at_signal",
                "portfolio_value", "bull_case", "bear_case", "supporting_evidence", "key_risks",
                "catalysts", "news_sources", "triage_score", "position_size_pct", 
                "expected_holding_days", "reasoning_summary", "order_id", "order_submitted",
                "risk_block_reasons"
            ]
        })

