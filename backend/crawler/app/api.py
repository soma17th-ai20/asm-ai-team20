from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from . import storage
from .config import load_config
from .models import CrawlReport, StoredNotice
from .runner import crawl_all

router = APIRouter(prefix="/api", tags=["crawler"])


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


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/sources", response_model=list[SiteOut])
def list_sources() -> list[SiteOut]:
    cfg = load_config()
    return [
        SiteOut(id=s.id, name=s.name, url=s.url, category=s.category, enabled=s.enabled)
        for s in cfg.sites
    ]


@router.get("/notices", response_model=NoticesOut)
def list_notices(
    source: Optional[str] = Query(default=None, description="source_id 필터"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NoticesOut:
    with storage.connect() as conn:
        items = storage.list_notices(conn, source_id=source, limit=limit, offset=offset)
        total = storage.count(conn, source_id=source)
    return NoticesOut(total=total, items=items)


@router.post("/crawl", response_model=CrawlResponse)
def trigger_crawl(source: Optional[str] = Query(default=None)) -> CrawlResponse:
    cfg = load_config()
    if source:
        try:
            cfg.site(source)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    reports = crawl_all(cfg, source)
    return CrawlResponse(reports=reports)
