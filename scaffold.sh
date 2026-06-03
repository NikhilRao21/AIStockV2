mkdir -p trading_system/{discovery,data,research,decision,execution,monitor,journal,scheduler,utils,tests,logs}
touch trading_system/.env
touch trading_system/requirements.txt
touch trading_system/main.py
touch trading_system/config.py
touch trading_system/report.py
touch trading_system/discovery/__init__.py
touch trading_system/discovery/screener.py
touch trading_system/discovery/news.py
touch trading_system/data/__init__.py
touch trading_system/data/market.py
touch trading_system/research/__init__.py
touch trading_system/research/triage.py
touch trading_system/research/sentiment.py
touch trading_system/research/thesis.py
touch trading_system/decision/__init__.py
touch trading_system/decision/recommendation.py
touch trading_system/execution/__init__.py
touch trading_system/execution/alpaca_client.py
touch trading_system/execution/risk.py
touch trading_system/execution/orders.py
touch trading_system/monitor/__init__.py
touch trading_system/monitor/position_monitor.py
touch trading_system/journal/__init__.py
touch trading_system/journal/db.py
touch trading_system/journal/review.py
touch trading_system/scheduler/__init__.py
touch trading_system/scheduler/sweep.py
touch trading_system/scheduler/runner.py
touch trading_system/utils/__init__.py
touch trading_system/utils/llm.py
touch trading_system/utils/logger.py
touch trading_system/tests/__init__.py
touch trading_system/tests/test_risk.py
touch trading_system/tests/test_triage.py
touch trading_system/tests/test_db.py
touch trading_system/tests/test_recommendation.py

echo ".env" > .gitignore
echo "logs/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo "pytest_cache/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
echo "trading_system.db" >> .gitignore

cat << 'REQ' > trading_system/requirements.txt
alpaca-py
requests
schedule
python-dotenv
pytest
REQ

