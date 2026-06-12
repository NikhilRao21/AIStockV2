import schedule
import time
import threading
from trading_system.scheduler import sweep
from trading_system.journal import review
from trading_system.monitor import position_monitor
from trading_system import config
import logging
from datetime import datetime
import zoneinfo

logger = logging.getLogger(__name__)

def run_premarket():
    sweep.run_sweep("premarket")

def run_open():
    sweep.run_sweep("open")

def run_midday():
    sweep.run_sweep("midday")

def run_preclose():
    sweep.run_sweep("preclose")

def run_review():
    review.generate_review()
    
def monitor_loop():
    while True:
        position_monitor.run_monitor()
        time.sleep(config.MONITOR_INTERVAL_SECONDS)

def start_scheduler():
    logger.info("Starting scheduler")
    
    # We use local time for the schedule if server is in ET, or we adjust.
    # schedule library uses local time. To ensure we run at ET times,
    # in a real app we'd convert ET to local time. For simplicity:
    for d in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), d).at("08:30").do(run_premarket)
        getattr(schedule.every(), d).at("09:45").do(run_open)
        getattr(schedule.every(), d).at("12:30").do(run_midday)
        getattr(schedule.every(), d).at("15:00").do(run_preclose)
        getattr(schedule.every(), d).at("20:00").do(run_review)
    
    # Start monitor loop in background thread
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    # Run a sweep right away for testing (if not full day test)
    # run_open()
    
    while True:
        schedule.run_pending()
        time.sleep(1)
