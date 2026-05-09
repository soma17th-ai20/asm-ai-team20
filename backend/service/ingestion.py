"""크롤 → 임베딩 → 저장 파이프라인.

호출 순서:
  1. NoticeCrawlService.crawl_all() 이 PostgresNoticeRepository를 통해
     notices 테이블에 신규 공지를 적재한다.
  2. list_pending_embeddings()로 아직 임베딩이 없는 공지를 모아서
     OpenAI API로 한 번에 임베딩한다.
  3. notice_embeddings에 (notice_id, embedding, model)로 저장한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from config import settings
from crawler.app.config import load_config
from crawler.app.models import CrawlReport, StoredNotice
from crawler.app.service import NoticeCrawlService

from db.connection import init_schema, session_scope
from db.repository import PostgresNoticeRepository
from service.embedding import embed_texts
from service.filter import push_notice_to_redis_queue

logger = logging.getLogger(__name__)


@dataclass
class IngestionReport:
    crawl_reports: list[CrawlReport]
    embedded: int
    embedding_model: str


def _embedding_input(n: StoredNotice) -> str:
    """제목 + 본문(없으면 요약)을 합쳐 임베딩 입력으로."""
    body = n.body or n.summary or ""
    return f"{n.title}\n\n{body}".strip()


def build_crawl_service(repository: Optional[PostgresNoticeRepository] = None) -> NoticeCrawlService:
    return NoticeCrawlService(
        config=load_config(),
        repository=repository or PostgresNoticeRepository(),
    )


def embed_pending(
    repository: Optional[PostgresNoticeRepository] = None,
    batch_size: int = 64,
    max_items: int = 500,
) -> int:
    """notice_embeddings에 빠진 공지를 채운다. 반환값은 임베딩한 row 수."""
    repo = repository or PostgresNoticeRepository()
    pending = repo.list_pending_embeddings(limit=max_items)
    if not pending:
        return 0

    total_saved = 0
    model = settings.EMBEDDING_MODEL
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        texts = [_embedding_input(n) for n in chunk]
        vectors = embed_texts(texts)
        items = [(n.id, vec, model) for n, vec in zip(chunk, vectors)]
        total_saved += repo.save_embeddings(items)
        logger.info("embedded %d notices (model=%s)", len(items), model)

        # ETL 글루: 임베딩 저장 직후 매칭 + Redis 큐 적재까지 한 번에.
        # 권기혁 service.filter가 cosine 1차 + LLM 2차로 알림 대상 유저를 골라
        # notifications 테이블 INSERT + Redis rpush 까지 처리한다.
        # 각 공지가 독립적이라 한 건 실패해도 다음 건은 계속 진행한다.
        for n, _ in zip(chunk, vectors):
            try:
                with session_scope() as s:
                    push_notice_to_redis_queue(s, n.id)
            except Exception as e:  # noqa: BLE001 — 매칭 실패가 임베딩 결과를 깨면 안 됨
                logger.warning("enqueue failed for notice_id=%s: %s", n.id, e)
    return total_saved


def run_full_ingestion(source: Optional[str] = None) -> IngestionReport:
    """1회성 풀 파이프라인. 스케줄러/CLI에서 호출."""
    init_schema()
    repo = PostgresNoticeRepository()
    crawl_service = build_crawl_service(repo)

    crawl_reports = crawl_service.crawl_all(source)
    embedded = embed_pending(repo)
    return IngestionReport(
        crawl_reports=crawl_reports,
        embedded=embedded,
        embedding_model=settings.EMBEDDING_MODEL,
    )
