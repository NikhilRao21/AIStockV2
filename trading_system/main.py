import os
import sys
from dotenv import load_dotenv
from trading_system.utils import logger as app_logger
from trading_system.journal import db
from trading_system.scheduler import runner

def check_env():
    required = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL", "HC_SEARCH_API_KEY"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

def main():
    load_dotenv()
    app_logger.setup_logging()
    check_env()
    db.init_db()
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting AI Trading System")
    
    # Run a quick sweep for phase 1 validation
    if len(sys.argv) > 1 and sys.argv[1] == "--sweep-only":
        from trading_system.scheduler import sweep
        sweep.run_sweep("open")
        sys.exit(0)
        
    runner.start_scheduler()

if __name__ == "__main__":
    main()
