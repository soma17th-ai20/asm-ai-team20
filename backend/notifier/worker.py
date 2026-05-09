"""알림 큐 소비 워커.

Redis list `notification_queue`에서 {user_id, notice_id}를 BLPOP으로 읽어
공지·유저를 DB에서 조회한 뒤 이메일을 발송하고 notifications.status를
'sent'로 업데이트한다.

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
from db.connection import session_scope
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
    email = getattr(row, "email", None)
    return email or settings.DEV_RECIPIENT_EMAIL or None


def _fetch_payload(session, user_id: int, notice_id: int):
    user = session.execute(
        text("SELECT id, email FROM users WHERE id = :uid"),
        {"uid": user_id},
    ).fetchone()
    notice = session.execute(
        text(
            """
            SELECT id, title, url,
                   COALESCE(body, summary, '') AS content
            FROM notices
            WHERE id = :nid
            """
        ),
        {"nid": notice_id},
    ).fetchone()
    return user, notice


def _mark_sent(session, user_id: int, notice_id: int) -> None:
    session.execute(
        text(
            """
            UPDATE notifications
               SET status = 'sent', sent_at = now()
             WHERE user_id = :uid AND notice_id = :nid
            """
        ),
        {"uid": user_id, "nid": notice_id},
    )


def _mark_failed(session, user_id: int, notice_id: int) -> None:
    session.execute(
        text(
            """
            UPDATE notifications
               SET status = 'failed'
             WHERE user_id = :uid AND notice_id = :nid
            """
        ),
        {"uid": user_id, "nid": notice_id},
    )


def _build_email(notice) -> tuple[str, str]:
    subject = f"[학교공지] {notice.title}"
    snippet = (notice.content or "")[:300]
    body_lines = [
        "관심사 매칭으로 새 공지가 도착했습니다.",
        "",
        f"제목: {notice.title}",
    ]
    if notice.url:
        body_lines.append(f"원문: {notice.url}")
    body_lines += ["", "본문 일부:", snippet, "", f"공지 ID: {notice.id}"]
    return subject, "\n".join(body_lines)


def handle(client: redis.Redis, raw: bytes) -> None:
    try:
        msg = json.loads(raw)
        user_id = int(msg["user_id"])
        notice_id = int(msg["notice_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.error("malformed message %r: %s", raw, e)
        return

    try:
        with session_scope() as session:
            user, notice = _fetch_payload(session, user_id, notice_id)
    except SQLAlchemyError as e:
        logger.error("db lookup failed user=%s notice=%s err=%s", user_id, notice_id, e)
        return

    if not user or not notice:
        logger.warning(
            "missing row user=%s(found=%s) notice=%s(found=%s)",
            user_id, bool(user), notice_id, bool(notice),
        )
        return

    if not try_consume(client, user_id):
        logger.info("daily limit hit — skipped user=%s notice=%s", user_id, notice_id)
        return

    to_addr = _resolve_email(user)
    if not to_addr:
        logger.warning(
            "no email for user=%s — populate users.email or DEV_RECIPIENT_EMAIL",
            user_id,
        )
        return

    subject, body = _build_email(notice)
    ok = send_email(to_addr, subject, body)

    try:
        with session_scope() as session:
            (_mark_sent if ok else _mark_failed)(session, user_id, notice_id)
    except SQLAlchemyError as e:
        logger.error("notifications status update failed: %s", e)


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
