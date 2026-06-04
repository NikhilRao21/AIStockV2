# --- Discovery ---
SCREENER_TOP_N          = 50      # top N for most-actives and each mover direction
MAX_CANDIDATES          = 70      # cap the pool before triage
DEEP_ANALYSIS_TOP_N     = 30      # triage selects this many for LLM analysis
MIN_STOCK_PRICE         = 1.00    # exclude stocks below $1 (penny stock dynamics differ)
NEWS_RESULTS_PER_TICKER = 5       # articles to fetch per candidate

# --- Portfolio ---
MAX_OPEN_POSITIONS      = 20
MAX_POSITION_PCT        = 0.05    # max 5% of portfolio per position
MIN_CASH_RESERVE_PCT    = 0.20    # always keep 20% cash
MAX_ENTRIES_PER_SWEEP   = 10       # max new positions opened in a single sweep

# --- Exit rules ---
STOP_LOSS_PCT           = 0.07    # close position if down 7%
TAKE_PROFIT_PCT         = 0.20    # close position if up 20%
MAX_HOLDING_DAYS        = 10      # flag for review if held longer

# --- Halt conditions ---
MAX_DAILY_LOSS_PCT      = 0.03    # halt all trading if portfolio down 3% today
MAX_DRAWDOWN_PCT        = 0.15    # halt all trading if down 15% from peak

# --- LLM ---
AI_TEMPERATURE          = 0.2
AI_MAX_TOKENS           = 20000
MIN_CONFIDENCE_SCORE    = 0.55    # ignore recommendations below this

# --- Rate limiting (be conservative) ---
AI_REQUEST_INTERVAL_SECONDS = 5
AI_REQUESTS_PER_MINUTE  = 200
SEARCH_REQUESTS_PER_MINUTE = 8
MONITOR_INTERVAL_SECONDS = 1200   # 20 minutes
