"""
APScheduler-based recurring report delivery.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
_scheduler.start()


def _build_trigger(frequency: str) -> CronTrigger:
    if frequency == "daily":
        return CronTrigger(hour=8, minute=0)
    elif frequency == "weekly":
        return CronTrigger(day_of_week="mon", hour=8, minute=0)
    elif frequency == "monthly":
        return CronTrigger(day=1, hour=8, minute=0)
    raise ValueError(f"Unknown frequency: {frequency}")


def _report_job(session_id: str):
    """Placeholder — in production, regenerate & email the report."""
    logger.info("Scheduled report triggered for session %s", session_id)


def schedule_report(session_id: str, frequency: str):
    job_id = f"report_{session_id}"
    # Remove existing schedule if any
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass

    trigger = _build_trigger(frequency)
    _scheduler.add_job(
        _report_job,
        trigger=trigger,
        args=[session_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info("Scheduled %s report for session %s", frequency, session_id)


def cancel_schedule(session_id: str):
    job_id = f"report_{session_id}"
    try:
        _scheduler.remove_job(job_id)
        logger.info("Cancelled schedule for session %s", session_id)
    except Exception:
        pass
