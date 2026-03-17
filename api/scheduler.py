"""
In-memory cache and APScheduler background job for the Venus OEV Analytics API.

The cache is a plain dict populated by pipeline.build_cache() on startup and
refreshed every 6 hours.  All FastAPI route handlers read from get_cache().
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import pipeline

logger = logging.getLogger(__name__)

# Module-level cache — populated by refresh(), read by get_cache()
_cache: dict = {}
_api_key: str = ""


def get_cache() -> dict:
    return _cache


def refresh() -> None:
    global _cache
    logger.info("Refreshing cache from Dune Analytics...")
    try:
        _cache = pipeline.build_cache(_api_key)
        logger.info("Cache refresh complete. last_refreshed=%s", _cache.get("last_refreshed"))
    except Exception:
        logger.exception("Cache refresh failed — retaining previous cache if available")


def start_scheduler(api_key: str) -> None:
    global _api_key
    _api_key = api_key

    # Warm the cache synchronously before accepting traffic
    refresh()

    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh, trigger=IntervalTrigger(hours=48), id="cache_refresh")
    scheduler.start()
    logger.info("Scheduler started — cache will refresh every 48 hours")
