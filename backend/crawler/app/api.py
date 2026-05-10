from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import CrawlReport, StoredNotice
from .service import NoticeCrawlService, build_service
from service.ingestion import embed_pending

router = APIRouter(prefix="/api", tags=["crawler"])


def _make_repo():
    from db.repository import PostgresNoticeRepository
    return PostgresNoticeRepository()


class SiteOut(BaseModel):
    id: str
    name: str
    url: str
    category: str
    enabled: bool


class NoticesOut(BaseModel):
    total: int
    items: list[StoredNotice]


class CrawlResponse(BaseModel):
    reports: list[CrawlReport]
    embedded: int


def get_service() -> NoticeCrawlService:
    return build_service(repository=_make_repo())


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/sources", response_model=list[SiteOut])
def list_sources() -> list[SiteOut]:
    # TEST-ONLY HTTP ADAPTER.
    # 서버 통합 시 이 라우트는 삭제 가능하고, 대신 app.service.NoticeCrawlService를 직접 호출하면 된다.
    service = get_service()
    return [
        SiteOut(id=s.id, name=s.name, url=s.url, category=s.category, enabled=s.enabled)
        for s in service.list_sources()
    ]


@router.get("/notices", response_model=NoticesOut)
def list_notices(
    source: Optional[str] = Query(default=None, description="source_id 필터"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NoticesOut:
    service = get_service()
    items = service.list_notices(source_id=source, limit=limit, offset=offset)
    total = service.count_notices(source_id=source)
    return NoticesOut(total=total, items=items)


@router.post("/crawl", response_model=CrawlResponse)
def trigger_crawl(source: Optional[str] = Query(default=None)) -> CrawlResponse:
    service = get_service()
    cfg = service.config
    if source:
        try:
            cfg.site(source)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    reports = service.crawl_all(source)
    embedded = embed_pending()
    return CrawlResponse(reports=reports, embedded=embedded)
