from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router

# TEST-ONLY FastAPI ENTRYPOINT.
# 서버 통합 시 이 파일은 삭제 가능하고, 대신 app.service.NoticeCrawlService를
# 기존 백엔드 라우트나 잡 스케줄러에서 직접 호출하면 된다.
app = FastAPI(
    title="학교 공지 AI 알림 — 스크래퍼 모듈",
    version="0.1.0",
    description="공지/채용 사이트 크롤러. 다른 팀원의 백엔드/AI 파이프라인에 REST API로 붙는다.",
)

# 데모 프론트(Vite dev: 5173, preview: 4173)와 같은 호스트의 다른 포트에서 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "service": "crawler",
        "docs": "/docs",
        "endpoints": ["/api/health", "/api/sources", "/api/notices", "/api/crawl"],
    }
