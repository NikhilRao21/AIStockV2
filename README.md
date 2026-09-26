# AIStockV2

AIStockV2 is a paper-trading stock system that discovers candidates from Alpaca market data, reads recent news, asks an LLM for analysis, runs deterministic risk checks, and records every recommendation in SQLite.

This project is designed to run unattended once it is configured, but it is still a trading system. Start with paper trading only, and treat every run as a test run until you have watched it behave for a while.

## What This Project Does

At a high level, the system:

1. Loads your API keys from a `.env` file.
2. Creates a local SQLite database called `trading_system.db`.
3. Starts a scheduler that runs three sweeps per trading day (Eastern Time, skipping market holidays) and a post-close review.
4. Runs a monitor loop every 20 minutes while the market is open.
5. Uses Alpaca paper trading so no real money is used.

Sweeps **do submit paper orders** (fractional, notional market orders) when a recommendation passes the risk checks. Orders are only sent while the market is open unless `ALLOW_TRADING_WHEN_CLOSED=1`.

## How a Trade Is Decided

1. **Discovery**: Alpaca most-actives and top movers, plus tickers from Alpaca (Benzinga) news and LangSearch web news. Every ticker is validated against Alpaca's list of active, tradable, fractionable, non-OTC stocks.
2. **Features**: ~120 days of daily bars per candidate are summarized into returns, SMA20/50, RSI14, ATR14, relative volume and average dollar volume.
3. **Triage**: candidates under $5, with under $5M average daily dollar volume, missing history, or already moving more than 40% today are dropped. The rest are ranked by relative volume, size of move, news count and trend.
4. **Research**: sentiment, then a bull analyst and a bear analyst, each given the features and headlines (`AI_FAST_MODEL`).
5. **Decision**: a portfolio-manager prompt (`AI_MODEL`) sees both theses, the features, the proposed size and stop, and the learned playbook, and returns BUY / NO_ACTION (new names) or HOLD / SELL (held names). Held positions are re-evaluated every sweep.
6. **Sizing**: each position risks ~1% of equity between entry and a stop 2 x ATR below it, capped at 5% of the portfolio. The LLM can shrink the size but not grow it.
7. **Risk checks**: confidence, cash reserve, position count, entries per sweep, daily loss vs. yesterday's close, drawdown from peak, market open, no duplicate positions. Exits skip the capacity and halt checks, but discretionary same-day sells are blocked to avoid day trades.
8. **Exits** (monitor, every 20 minutes): a stop starting at entry - 2 x ATR that trails the highest price seen, and a target at entry + 4 x ATR. Positions without an ATR on record fall back to -7% / +20%.
9. **Learning**: after the close, each closed trade gets an LLM post-mortem, and those reviews plus performance stats are distilled into a short playbook (`summaryReflection.txt`) fed into future decisions.

## Important Safety Notes

- Use Alpaca paper trading only.
- Do not use real brokerage credentials in this project.
- Review every dependency and every API key before running on a server.
- This is not financial advice. You are responsible for whether you choose to trade.

## Project Layout

The main parts of the app are:

- `trading_system/main.py`: entry point
- `trading_system/config.py`: hard-coded risk and scheduling constants
- `trading_system/discovery/`: ticker discovery from Alpaca and news
- `trading_system/data/`: market data fetchers
- `trading_system/research/`: triage, sentiment, and thesis generation
- `trading_system/decision/`: final recommendation parsing
- `trading_system/execution/`: Alpaca client, risk checks, order helpers
- `trading_system/monitor/`: 20-minute position monitor
- `trading_system/journal/`: SQLite database and review storage
- `trading_system/scheduler/`: sweep orchestration and daily schedule
- `trading_system/tests/`: unit tests

## What You Need Before You Start

You need:

- A computer or server with Python 3.11 or newer
- An Alpaca account with paper trading enabled
- An AI provider key for a chat-completions compatible endpoint
- An `HC_SEARCH_API_KEY` for the news search step
- Basic internet access from the machine where the app will run

## Step-by-Step Deployment

### 1) Get the code onto your machine

Clone the repository and move into the project directory:

```bash
git clone <your-repo-url>
cd AIStockV2
```

If you are already inside the repository, you can skip this step.

### 2) Create a virtual environment

A virtual environment keeps this project’s Python packages separate from everything else on your machine.

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

After activation, your terminal usually shows `(.venv)` at the front of the prompt.

### 3) Install the dependencies

Install the Python packages listed for this project:

```bash
pip install -r trading_system/requirements.txt
```

If you are working from the repository root and want to confirm the file is there, use `trading_system/requirements.txt`.

### 4) Create your `.env` file

The app reads its secrets from environment variables. Copy the example file and fill in real values:

```bash
cp .env.example .env
```

Then edit `.env` and set these values:

```env
ALPACA_API_KEY=your_paper_api_key
ALPACA_SECRET_KEY=your_paper_secret_key
AI_API_KEY=your_ai_provider_key
AI_BASE_URL=https://your-provider.com/v1
AI_MODEL=qwen/qwen3-32b
AI_FAST_MODEL=deepseek/deepseek-v4-flash-0731
LANGSEARCH_API_KEY=your_langsearch_key
```

### What each variable means

- `ALPACA_API_KEY`: your Alpaca paper trading API key
- `ALPACA_SECRET_KEY`: your Alpaca paper trading secret key
- `AI_API_KEY`: key for the LLM provider you want to use
- `AI_BASE_URL`: the provider’s chat-completions base URL, ending in `/v1`
- `AI_MODEL`: the model used for the final trade decision
- `AI_FAST_MODEL` (optional): cheaper model for sentiment, theses and reviews; defaults to `AI_MODEL`
- `LANGSEARCH_API_KEY`: free key from langsearch.com, used for broad news discovery (free tier: 1,000 queries/day)
- `REFLECTION_PATH`, `DB_PATH` (optional): where the learned playbook and database live
- `ALLOW_TRADING_WHEN_CLOSED` (optional): set to `1` to send orders outside market hours when testing

The program will stop immediately if any required value is missing (the optional ones above are not required).

### 5) Make sure Alpaca is in paper-trading mode

The code creates the trading client with `paper=True`. That is intentional and should stay that way for deployment.

If you are generating API keys in Alpaca, make sure you are using the paper environment, not live trading credentials.

### 6) Start the app

From the repository root, run:

```bash
python -m trading_system.main
```

When it starts successfully, it will:

- load `.env`
- initialize logging
- create or update `trading_system.db`
- start the scheduled sweep loop
- start the background position monitor

### 7) Run a single sweep for testing

The entry point supports a one-shot sweep mode:

```bash
python -m trading_system.main --sweep-only
```

This is the easiest way to confirm that your keys, network access, and database are all working before leaving the system running.

Other one-shot modes:

```bash
python -m trading_system.main --monitor-only   # one monitor pass (stops, fill reconciliation, snapshot)
python -m trading_system.main --reflect        # review closed trades and update the playbook
python -m trading_system.main --report         # win rate, profit factor, drawdown, Sharpe, vs. SPY
```

## How the Runtime Works

The scheduler in `trading_system/scheduler/runner.py` runs on US Eastern Time regardless of the server's timezone, and skips weekends and market holidays using Alpaca's calendar:

- 9:45 AM ET: open sweep
- 12:30 PM ET: midday sweep
- 3:00 PM ET: pre-close sweep
- 4:30 PM ET: review of closed trades and playbook update

Times are configured in `SWEEP_SCHEDULE` / `REVIEW_TIME` in `config.py`. If the process starts after a job's time, that job waits until the next day. A failing job is logged and does not stop the scheduler.

The monitor loop runs every 20 minutes while the market is open. It:

- fills in actual fill prices for submitted orders and closes out orders that never filled
- enforces the ATR trailing stop and take-profit
- records realized P&L on the journal trade
- records portfolio snapshots in SQLite

## Database File

The app stores local data in `trading_system.db` in the project root.

It includes tables for:

- recommendations (including the features, sentiment score and raw LLM response behind each decision)
- trades (order id, fill, ATR, stop/target, high-water price, close reason and P&L)
- portfolio snapshots
- post-trade reviews

New columns are added automatically to an existing database on startup.

The learned playbook lives in `summaryReflection.txt`. It is gitignored so deployments never overwrite it.

If you delete the file, the app will recreate the schema on next startup, but you will lose the stored history.

## Running It on a Server

If you want this to run continuously, use a machine that stays online. A small cloud VM is usually the simplest option.

Typical server setup:

1. Create a Linux VM.
2. Install Python 3.11+.
3. Clone the repo.
4. Create a virtual environment.
5. Install dependencies.
6. Add your `.env` file.
7. Start the process with `python -m trading_system.main`.

For long-running deployments, many people wrap the command in a process manager such as `systemd`, `supervisord`, or a container runtime. The repository does not currently include one, so you will need to add your own if you want automatic restarts.

## Testing

Run the tests with:

```bash
pytest
```

The test suite covers risk and sizing, triage, features, news ticker extraction, exit levels, scheduling, the database, recommendation parsing, and an offline end-to-end sweep with Alpaca and the LLM faked.

To test buying and selling, run the following code before executing the test suite

```bash
export ALPACA_RUN_ORDER_INTEGRATION=1
export ALPACA_TEST_TICKER=SIRI
export ALPACA_TEST_NOTIONAL=10
```

## Troubleshooting

### “Missing required environment variables”

One or more values in `.env` are missing. Check that all six required variables are present and spelled exactly as expected.

### Alpaca connection errors

Confirm that:

- your Alpaca keys are for paper trading
- the machine has outbound internet access
- the Alpaca SDK installed correctly

### LLM request errors

Confirm that:

- `AI_BASE_URL` is correct and ends in `/v1`
- `AI_API_KEY` is valid
- `AI_MODEL` matches the provider’s model name

### News search errors

Confirm that `LANGSEARCH_API_KEY` is valid and under the free-tier daily limit. Alpaca news uses your Alpaca keys.

## A Quick Reality Check

The trading client is hard-coded to `paper=True`. Before trusting any results, let it run long enough to collect a meaningful number of closed trades (50+) and compare `--report` against simply holding SPY. LLM confidence scores are not calibrated probabilities, and a few weeks of paper results can easily be luck.

## Recommended First Run

If this is your first time deploying it, do this in order:

1. Set up Alpaca paper trading.
2. Add your `.env` file.
3. Install dependencies.
4. Run `python -m trading_system.main --sweep-only`.
5. Inspect `trading_system.db`.
6. Run the full scheduler only after the one-shot sweep works cleanly.


