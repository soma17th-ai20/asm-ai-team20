"""풀 ingestion 파이프라인을 주기적으로 트리거하는 스케줄러.

매 N분마다 service.ingestion.run_full_ingestion을 직접 호출한다 (HTTP 우회).
한 사이클: crawl → embed → 매칭(cosine+LLM) → notifications INSERT → Redis rpush.

HTTP가 아니라 로컬 import인 이유:
  - 풀 파이프라인이 LLM 호출 포함 수 분 걸릴 수 있어 HTTP 타임아웃 위험
  - /api/crawl(양현서)는 crawl-only contract 유지 (FE의 "지금 크롤링" 버튼 등)
  - 별도 머신 분리가 필요해지면 그때 HTTP 워커로 바꿈

run:
    python -m scheduler.main
"""
from __future__ import annotations

import logging
import signal

from apscheduler.schedulers.blocking import BlockingScheduler

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("scheduler")


def trigger_crawl() -> None:
    # import는 함수 안에서 — 스케줄러 부팅 시 DB/OpenAI 클라이언트 초기화를 미룸.
    from service.ingestion import run_full_ingestion

    try:
        report = run_full_ingestion()
    except Exception as e:  # noqa: BLE001 — 한 사이클 실패가 다음 사이클을 막지 않게
        logger.exception("ingestion failed: %s", e)
        return

    total_fetched = sum(r.fetched for r in report.crawl_reports)
    total_inserted = sum(r.inserted for r in report.crawl_reports)
    total_errors = sum(len(r.errors) for r in report.crawl_reports)
    logger.info(
        "ingestion ok: sources=%d fetched=%d inserted=%d embedded=%d errors=%d",
        len(report.crawl_reports), total_fetched, total_inserted,
        report.embedded, total_errors,
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
        "scheduler started: every %d min → run_full_ingestion (crawl+embed+enqueue)",
        settings.CRAWL_INTERVAL_MINUTES,
    )

    trigger_crawl()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sched.shutdown(wait=False))

    sched.start()


if __name__ == "__main__":
    main()
