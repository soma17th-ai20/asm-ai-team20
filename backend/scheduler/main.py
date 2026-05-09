"""크롤러를 주기적으로 트리거하는 스케줄러.

run:
    python -m scheduler.main
"""
from __future__ import annotations

import logging
import signal

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("scheduler")


def trigger_crawl() -> None:
    url = f"{settings.CRAWLER_API_URL.rstrip('/')}/api/crawl"
    try:
        r = httpx.post(url, timeout=120)
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("crawl trigger failed: %s", e)
        return

    reports = r.json().get("reports", [])
    total_inserted = sum(rp.get("inserted", 0) for rp in reports)
    total_fetched = sum(rp.get("fetched", 0) for rp in reports)
    logger.info(
        "crawl ok: sources=%d fetched=%d inserted=%d",
        len(reports), total_fetched, total_inserted,
    )


def main() -> None:
    sched = BlockingScheduler(timezone="Asia/Seoul")
    sched.add_job(
        trigger_crawl,
        "interval",
        minutes=settings.CRAWL_INTERVAL_MINUTES,
        next_run_time=None,
        id="crawl",
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "scheduler started: every %d min → POST %s/api/crawl",
        settings.CRAWL_INTERVAL_MINUTES, settings.CRAWLER_API_URL,
    )

    trigger_crawl()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sched.shutdown(wait=False))

    sched.start()


if __name__ == "__main__":
    main()
