"""PostgreSQL 기반 NoticeRepository 구현.

크롤러의 NoticeCrawlService에 그대로 주입할 수 있도록 SQLite 구현체와
동일한 인터페이스(Protocol)를 만족시킨다. 추가로 임베딩 파이프라인이
쓰는 보조 메서드를 노출한다.
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import text

from crawler.app.models import RawNotice, StoredNotice

from .connection import session_scope

logger = logging.getLogger(__name__)


def _row_to_stored(row) -> StoredNotice:
    return StoredNotice(
        id=row.id,
        source_id=row.source_id,
        title=row.title,
        url=row.url,
        posted_at=row.posted_at,
        summary=row.summary,
        body=row.body,
        hash=row.hash,
        fetched_at=row.fetched_at.isoformat(timespec="seconds")
        if row.fetched_at is not None
        else "",
    )


class PostgresNoticeRepository:
    """크롤러 service.NoticeRepository 프로토콜 준수."""

    def insert_many(self, notices: list[RawNotice]) -> tuple[int, int]:
        if not notices:
            return 0, 0

        rows = [
            {
                "source_id": n.source_id,
                "title": n.title.strip(),
                "url": str(n.url),
                "posted_at": n.posted_at,
                "summary": n.summary,
                "body": n.body,
                "hash": n.content_hash(),
            }
            for n in notices
        ]

        # ON CONFLICT (hash) DO NOTHING — 충돌한 row는 RETURNING으로 안 돌아온다.
        # 그래서 inserted = returned 개수, duplicates = 전체 - inserted.
        sql = text(
            """
            INSERT INTO notices (source_id, title, url, posted_at, summary, body, hash, fetched_at)
            VALUES (:source_id, :title, :url, :posted_at, :summary, :body, :hash, now())
            ON CONFLICT (hash) DO NOTHING
            RETURNING id
            """
        )

        inserted = 0
        with session_scope() as s:
            for row in rows:
                result = s.execute(sql, row).first()
                if result is not None:
                    inserted += 1
        duplicates = len(rows) - inserted
        return inserted, duplicates

    def list_notices(
        self,
        source_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StoredNotice]:
        params = {"limit": limit, "offset": offset}
        if source_id:
            sql = text(
                """
                SELECT id, source_id, title, url, posted_at, summary, body, hash, fetched_at
                FROM notices
                WHERE source_id = :source_id
                ORDER BY fetched_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """
            )
            params["source_id"] = source_id
        else:
            sql = text(
                """
                SELECT id, source_id, title, url, posted_at, summary, body, hash, fetched_at
                FROM notices
                ORDER BY fetched_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """
            )
        with session_scope() as s:
            rows = s.execute(sql, params).fetchall()
        return [_row_to_stored(r) for r in rows]

    def count(self, source_id: Optional[str] = None) -> int:
        with session_scope() as s:
            if source_id:
                row = s.execute(
                    text("SELECT COUNT(*) AS c FROM notices WHERE source_id = :sid"),
                    {"sid": source_id},
                ).first()
            else:
                row = s.execute(text("SELECT COUNT(*) AS c FROM notices")).first()
        return int(row.c) if row else 0

    def delete_all(self) -> None:
        with session_scope() as s:
            s.execute(text("TRUNCATE notices RESTART IDENTITY CASCADE"))

    # -- 임베딩 파이프라인 보조 메서드 -------------------------------------------------

    def list_pending_embeddings(self, limit: int = 100) -> list[StoredNotice]:
        """notice_embeddings에 아직 들어가지 않은 공지를 fetched_at 오름차순으로 반환."""
        sql = text(
            """
            SELECT n.id, n.source_id, n.title, n.url, n.posted_at, n.summary, n.body, n.hash, n.fetched_at
            FROM notices n
            LEFT JOIN notice_embeddings ne ON ne.notice_id = n.id
            WHERE ne.notice_id IS NULL
            ORDER BY n.fetched_at ASC, n.id ASC
            LIMIT :limit
            """
        )
        with session_scope() as s:
            rows = s.execute(sql, {"limit": limit}).fetchall()
        return [_row_to_stored(r) for r in rows]

    def save_embeddings(
        self,
        items: Sequence[tuple[int, list[float], str]],
    ) -> int:
        """(notice_id, embedding, model) 묶음을 upsert. 같은 notice는 model까지 갱신."""
        if not items:
            return 0
        sql = text(
            """
            INSERT INTO notice_embeddings (notice_id, embedding, model)
            VALUES (:notice_id, CAST(:embedding AS vector), :model)
            ON CONFLICT (notice_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                model     = EXCLUDED.model,
                created_at = now()
            """
        )
        saved = 0
        with session_scope() as s:
            for notice_id, vec, model in items:
                s.execute(
                    sql,
                    {
                        "notice_id": notice_id,
                        # pgvector text 입력 포맷: '[0.1,0.2,...]'
                        "embedding": "[" + ",".join(f"{x:.7f}" for x in vec) + "]",
                        "model": model,
                    },
                )
                saved += 1
        return saved
