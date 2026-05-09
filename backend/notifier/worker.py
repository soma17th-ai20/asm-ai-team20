"""알림 큐 소비 워커.

Redis list `notification_queue`에서 {user_id, notice_id}를 BLPOP으로 읽어
공지·유저를 DB에서 조회한 뒤 이메일을 발송한다.

run:
    python -m notifier.worker
"""
from __future__ import annotations

import json
import logging
import signal
import sys

import redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from db import SessionLocal
from notifier.mailer import send_email
from notifier.ratelimit import try_consume

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("notifier")

QUEUE_KEY = "notification_queue"
_running = True


def _resolve_email(row) -> str | None:
    """users 테이블에 email 컬럼이 아직 없을 수 있음 → 폴백."""
    email = getattr(row, "email", None)
    return email or settings.DEV_RECIPIENT_EMAIL or None


def _fetch_payload(session, user_id: int, notice_id: int):
    user = session.execute(
        text("SELECT id, interest_text FROM users WHERE id = :uid"),
        {"uid": user_id},
    ).fetchone()
    notice = session.execute(
        text("SELECT notice_id, title, content FROM notice WHERE notice_id = :nid"),
        {"nid": notice_id},
    ).fetchone()
    return user, notice


def _build_email(notice, interest_text: str) -> tuple[str, str]:
    subject = f"[학교공지] {notice.title}"
    snippet = (notice.content or "")[:300]
    body = (
        f"관심사 매칭으로 새 공지가 도착했습니다.\n\n"
        f"제목: {notice.title}\n\n"
        f"본문 일부:\n{snippet}\n\n"
        f"---\n"
        f"매칭된 관심사: {interest_text}\n"
        f"공지 ID: {notice.notice_id}"
    )
    return subject, body


def handle(client: redis.Redis, raw: bytes) -> None:
    try:
        msg = json.loads(raw)
        user_id = int(msg["user_id"])
        notice_id = int(msg["notice_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.error("malformed message %r: %s", raw, e)
        return

    session = SessionLocal()
    try:
        user, notice = _fetch_payload(session, user_id, notice_id)
    except SQLAlchemyError as e:
        logger.error("db lookup failed user=%s notice=%s err=%s", user_id, notice_id, e)
        session.close()
        return
    finally:
        session.close()

    if not user or not notice:
        logger.warning("missing row user=%s(%s) notice=%s(%s)",
                       user_id, bool(user), notice_id, bool(notice))
        return

    if not try_consume(client, user_id):
        logger.info("daily limit hit — skipped user=%s notice=%s",
                    user_id, notice_id)
        return

    to_addr = _resolve_email(user)
    if not to_addr:
        logger.warning("no email for user=%s — set users.email or DEV_RECIPIENT_EMAIL",
                       user_id)
        return

    subject, body = _build_email(notice, user.interest_text or "")
    send_email(to_addr, subject, body)


def main() -> None:
    client = redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=0,
    )
    try:
        client.ping()
    except redis.RedisError as e:
        logger.error("redis unreachable: %s", e)
        sys.exit(1)

    def _stop(*_):
        global _running
        _running = False
        logger.info("shutdown requested")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _stop)

    logger.info("notifier worker started: BLPOP %s", QUEUE_KEY)
    while _running:
        try:
            popped = client.blpop(QUEUE_KEY, timeout=5)
        except redis.RedisError as e:
            logger.error("blpop error: %s", e)
            continue
        if popped is None:
            continue
        _, raw = popped
        handle(client, raw)


if __name__ == "__main__":
    main()
