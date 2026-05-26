"""APScheduler worker — weekly digest cron.

The scheduler is an asyncio-backed AsyncIOScheduler started at app lifespan.
The weekly digest fires every Monday at 07:00 UTC.
"""
from __future__ import annotations
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_weekly_digest() -> None:
    from digest import generate_and_send_digest
    try:
        await generate_and_send_digest()
    except Exception as exc:
        logger.error("weekly digest job failed: %s", exc)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _run_weekly_digest,
            trigger="cron",
            day_of_week="mon",
            hour=7,
            minute=0,
            id="weekly_digest",
            replace_existing=True,
        )
        logger.info("scheduler configured: weekly digest on Monday 07:00 UTC")
    return _scheduler


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
    _scheduler = None
