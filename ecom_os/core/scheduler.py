"""Planificateur (APScheduler) : pipeline quotidien du Director si AUTO MODE actif."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .. import config
from ..db import session_scope
from .logs import get_logger
from .state import get_setting

_scheduler: BackgroundScheduler | None = None
JOB_ID = "daily_pipeline"


def _job():
    from ..agents.director import run_daily_pipeline
    with session_scope() as s:
        if get_setting(s, "emergency_stop"):
            get_logger().info("Pipeline planifié ignoré : STOP ALL actif")
            return
        if not get_setting(s, "auto_mode"):
            get_logger().info("Pipeline planifié ignoré : AUTO MODE désactivé")
            return
        run_daily_pipeline(s, trigger="planificateur")


def start(hour: int = 7):
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    _scheduler.add_job(_job, CronTrigger(hour=hour, minute=0, timezone=config.TIMEZONE), id=JOB_ID,
                       replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=3600)
    _scheduler.start()
    get_logger().info("Planificateur démarré (pipeline quotidien à %sh, %s)", hour, config.TIMEZONE)
    return _scheduler


def shutdown():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def status() -> dict:
    if not _scheduler or not _scheduler.running:
        return {"running": False, "next_run": None}
    job = _scheduler.get_job(JOB_ID)
    return {"running": True, "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None}
