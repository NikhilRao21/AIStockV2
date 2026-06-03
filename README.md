# AIStockV2

AIStockV2 is a paper-trading stock system that discovers candidates from Alpaca market data, reads recent news, asks an LLM for analysis, runs deterministic risk checks, and records every recommendation in SQLite.

This project is designed to run unattended once it is configured, but it is still a trading system. Start with paper trading only, and treat every run as a test run until you have watched it behave for a while.

## What This Project Does

At a high level, the system:

1. Loads your API keys from a `.env` file.
2. Creates a local SQLite database called `trading_system.db`.
3. Starts a scheduler that runs four sweeps per trading day.
4. Runs a monitor loop every 20 minutes during market hours.
5. Uses Alpaca paper trading so no real money is used.

The code currently does not place real orders in the default sweep path. The order submission line is present, but it is commented out in `trading_system/scheduler/sweep.py`. That means the system is currently safest to use as a research and validation harness unless you enable order submission yourself.

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
HC_SEARCH_API_KEY=your_hackclub_search_key
```

### What each variable means

- `ALPACA_API_KEY`: your Alpaca paper trading API key
- `ALPACA_SECRET_KEY`: your Alpaca paper trading secret key
- `AI_API_KEY`: key for the LLM provider you want to use
- `AI_BASE_URL`: the provider’s chat-completions base URL, ending in `/v1`
- `AI_MODEL`: the model name the provider expects
- `HC_SEARCH_API_KEY`: key used for news search

The program will stop immediately if any required value is missing.

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

## How the Runtime Works

The scheduler in `trading_system/scheduler/runner.py` sets up four sweeps each day:

- 8:30 AM ET: pre-market
- 9:45 AM ET: open
- 12:30 PM ET: midday
- 3:00 PM ET: pre-close

It also starts a separate monitor loop that runs every 20 minutes.

The monitor loop:

- reads current positions from Alpaca
- checks stop-loss and take-profit thresholds
- records portfolio snapshots in SQLite

The sweep loop:

- pulls candidates from Alpaca’s screener
- adds news-derived tickers
- ranks candidates
- asks the LLM for thesis and recommendation text
- runs deterministic risk checks
- stores the result in the database

## Database File

The app stores local data in `trading_system.db` in the project root.

It includes tables for:

- recommendations
- trades
- portfolio snapshots
- post-trade reviews

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

The test suite covers the core risk, triage, database, and recommendation logic.

To test buying and selling, run the following code before executing the test suite

'''bash
export ALPACA_RUN_ORDER_INTEGRATION=1
export ALPACA_TEST_TICKER=SIRI
export ALPACA_TEST_NOTIONAL=10
'''

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

Confirm that `HC_SEARCH_API_KEY` is valid and that the provider is reachable from the machine running the app.

## A Quick Reality Check

This repository currently has the scaffolding for a trading system, but some execution behavior is still conservative or mocked in places. In particular, order submission in the main sweep is commented out. That means the safest way to deploy it right now is as a paper-trading research system first, then enable live order submission only after you fully understand the control flow.

## Recommended First Run

If this is your first time deploying it, do this in order:

1. Set up Alpaca paper trading.
2. Add your `.env` file.
3. Install dependencies.
4. Run `python -m trading_system.main --sweep-only`.
5. Inspect `trading_system.db`.
6. Run the full scheduler only after the one-shot sweep works cleanly.


