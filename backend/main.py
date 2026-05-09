"""통합 백엔드 FastAPI 엔트리포인트.

  uvicorn main:app --reload --port 8000

크롤러 라우터(/api/sources, /api/notices, /api/crawl)와
유저 등록 라우터(/api/users)를 한 앱에서 서빙한다. 부팅 시 DB 스키마를 멱등 적용.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.users import router as users_router
from crawler.app.api import router as crawler_router
from db.connection import init_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="학교 공지 AI 알림 — 통합 백엔드",
    version="0.2.0",
    description="크롤러 + DB(Postgres+pgvector) + 유저 등록.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawler_router)
app.include_router(users_router)


@app.on_event("startup")
def _bootstrap_db() -> None:
    init_schema()


@app.get("/")
def root() -> dict:
    return {
        "service": "team20-backend",
        "docs": "/docs",
        "endpoints": [
            "/api/health",
            "/api/sources",
            "/api/notices",
            "/api/crawl",
            "/api/users",
        ],
    }
