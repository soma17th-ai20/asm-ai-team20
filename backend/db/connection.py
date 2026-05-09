"""SQLAlchemy 엔진/세션 + 스키마 부트스트랩.

DATABASE_URL은 config.settings에서 읽고, 첫 호출 시 schema.sql을 실행한다.
docker-compose의 init script가 동일 SQL을 부트 시점에 한 번 더 돌리므로
양쪽 모두 멱등 가능하도록 schema.sql은 IF NOT EXISTS만 쓴다.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema() -> None:
    """애플리케이션 초기화 시 한 번 호출. 도커가 이미 init한 경우에도 안전."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_engine().begin() as conn:
        conn.exec_driver_sql(sql)
    logger.info("DB schema initialized from %s", SCHEMA_PATH)
