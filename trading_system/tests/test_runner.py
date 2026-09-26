from datetime import datetime, date

from trading_system.scheduler.runner import due_jobs

JOBS = [("sweep:open", "09:45", None), ("sweep:midday", "12:30", None)]


def test_job_due_after_its_time():
    now = datetime(2026, 9, 28, 9, 46)
    assert [j[0] for j in due_jobs(JOBS, now, {})] == ["sweep:open"]


def test_job_not_rerun_same_day():
    now = datetime(2026, 9, 28, 13, 0)
    assert [j[0] for j in due_jobs(JOBS, now, {"sweep:open": date(2026, 9, 28)})] == ["sweep:midday"]
