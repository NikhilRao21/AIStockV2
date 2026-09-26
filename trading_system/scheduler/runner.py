import threading
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

from alpaca.trading.requests import GetCalendarRequest

from trading_system import config
from trading_system.execution import alpaca_client
from trading_system.journal import review
from trading_system.monitor import position_monitor
from trading_system.scheduler import sweep
from trading_system.utils import shutdown

logger = logging.getLogger(__name__)

MARKET_TZ = ZoneInfo(config.MARKET_TIMEZONE)
POLL_SECONDS = 30


def is_trading_day(day: date) -> bool:
    """Ask Alpaca's calendar, which knows about holidays. Assume weekdays trade if the call fails."""
    try:
        calendar = alpaca_client.get_trading_client().get_calendar(GetCalendarRequest(start=day, end=day))
        return any(c.date == day for c in calendar)
    except Exception as e:
        logger.warning("Calendar lookup failed (%s); falling back to weekday check", e)
        return day.weekday() < 5


def build_jobs() -> list[tuple[str, str, callable]]:
    jobs = [(f"sweep:{name}", at, (lambda n=name: sweep.run_sweep(n))) for name, at in config.SWEEP_SCHEDULE.items()]
    jobs.append(("review", config.REVIEW_TIME, review.generate_review))
    return jobs


def due_jobs(jobs, now_et: datetime, last_run: dict[str, date]) -> list:
    """Jobs whose ET time has passed today and have not run today."""
    hhmm = now_et.strftime("%H:%M")
    today = now_et.date()
    return [job for job in jobs if job[1] <= hhmm and last_run.get(job[0]) != today]


def _run_safely(name: str, fn):
    try:
        logger.info("Running job %s", name)
        fn()
    except Exception:
        logger.exception("Job %s failed", name)


def monitor_loop():
    while not shutdown.requested():
        _run_safely("monitor", position_monitor.run_monitor)
        shutdown.wait(config.MONITOR_INTERVAL_SECONDS)


def start_scheduler():
    jobs = build_jobs()
    logger.info("Starting scheduler (times are %s): %s", config.MARKET_TIMEZONE, [(n, t) for n, t, _ in jobs])

    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

    # Jobs whose time already passed when the process starts are skipped for today, so a
    # restart at 2pm doesn't fire the open and midday sweeps back to back.
    now = datetime.now(MARKET_TZ)
    last_run = {name: now.date() for name, at, _ in jobs if at <= now.strftime("%H:%M")}
    trading_day_cache: dict[date, bool] = {}

    while not shutdown.requested():
        now = datetime.now(MARKET_TZ)
        for name, _, fn in due_jobs(jobs, now, last_run):
            last_run[name] = now.date()
            if now.date() not in trading_day_cache:
                trading_day_cache[now.date()] = is_trading_day(now.date())
            if trading_day_cache[now.date()]:
                _run_safely(name, fn)
            else:
                logger.info("Skipping %s: market holiday or weekend", name)
        shutdown.wait(POLL_SECONDS)
    monitor_thread.join(timeout=120)  # let an in-progress monitor pass finish closing positions
    logger.info("Scheduler stopped")
