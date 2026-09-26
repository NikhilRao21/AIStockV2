import os

from dotenv import load_dotenv

load_dotenv()  # config reads env at import time, before main() runs

# --- Paths (override with env vars so state can live outside the repo) ---
DB_PATH                 = os.environ.get("DB_PATH", "trading_system.db")
REFLECTION_PATH         = os.environ.get("REFLECTION_PATH", "summaryReflection.txt")

# --- Discovery ---
SCREENER_TOP_N          = 50      # top N for most-actives and each mover direction
MAX_CANDIDATES          = 200     # cap the pool before triage
DEEP_ANALYSIS_TOP_N     = 40      # triage selects this many for LLM analysis
MIN_STOCK_PRICE         = 5.00    # sub-$5 names are dominated by pumps, halts and wide spreads
MIN_AVG_DOLLAR_VOLUME   = 5_000_000  # 20-day average $ volume; keeps fills near the quoted price
MAX_ABS_DAY_MOVE        = 0.40    # skip names already up/down >40% today (chasing blow-off moves)
NEWS_RESULTS_PER_TICKER = 10      # articles to fetch per candidate
BARS_LOOKBACK_DAYS      = 120     # calendar days of daily bars (enough for SMA50 + ATR)

# --- Portfolio ---
MAX_OPEN_POSITIONS      = 20
MAX_POSITION_PCT        = 0.05    # max 5% of portfolio per position
MIN_CASH_RESERVE_PCT    = 0.20    # always keep 20% cash
MAX_ENTRIES_PER_SWEEP   = 10      # max new positions opened in a single sweep
MIN_ORDER_NOTIONAL      = 1.00    # Alpaca's minimum notional for fractional orders

# --- Volatility-based sizing and exits ---
RISK_PER_TRADE_PCT      = 0.01    # lose at most ~1% of equity if the stop is hit
ATR_PERIOD              = 14
ATR_STOP_MULT           = 2.0     # stop = entry - 2 * ATR
ATR_TARGET_MULT         = 4.0     # target = entry + 4 * ATR (2:1 reward/risk)
STOP_LOSS_PCT           = 0.07    # fallback stop when no ATR-based stop is on record
TAKE_PROFIT_PCT         = 0.20    # fallback target when no ATR-based target is on record
MAX_HOLDING_DAYS        = 10      # positions older than this are flagged for the LLM to re-justify

# --- Halt conditions ---
MAX_DAILY_LOSS_PCT      = 0.03    # halt new entries if equity down 3% vs yesterday's close
MAX_DRAWDOWN_PCT        = 0.15    # halt new entries if down 15% from peak

# --- Trading hours ---
# Orders are only sent while the market is open. Set ALLOW_TRADING_WHEN_CLOSED=1 to test off-hours
# (Alpaca queues DAY market orders until the next open).
ALLOW_TRADING_WHEN_CLOSED = os.environ.get("ALLOW_TRADING_WHEN_CLOSED") == "1"
MARKET_TIMEZONE         = "America/New_York"
SWEEP_SCHEDULE          = {       # ET times
    "open":     "09:45",
    "midday":   "12:30",
    "preclose": "15:00",
}
REVIEW_TIME             = "16:30"  # ET, after the close

# --- LLM ---
AI_FAST_MODEL           = os.environ.get("AI_FAST_MODEL")  # sentiment/thesis/review; falls back to AI_MODEL
AI_TEMPERATURE          = 0.2
AI_MAX_TOKENS           = int(os.environ.get("AI_MAX_TOKENS", 4000))
AI_TIMEOUT_SECONDS      = 120
MIN_CONFIDENCE_SCORE    = 0.55    # ignore recommendations below this

# --- Rate limiting (be conservative) ---
AI_REQUEST_INTERVAL_SECONDS = 5
MONITOR_INTERVAL_SECONDS = 1200   # 20 minutes
