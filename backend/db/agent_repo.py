"""ai_agent의 4개 함수에 대응하는 실 DB 구현.

ai_agent는 dummy_functions로 응답하지만, 외부 dispatcher가 이 모듈의
함수들을 호출해 실제 row를 다룬다. ai_agent 코드는 건드리지 않는다.

함수명은 ai_agent의 plan에 등장하는 이름과 의미적으로 1:1 매핑되며,
모두 user_id를 첫 번째 인자로 받는다.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from .connection import session_scope
from service.embedding import embed_text

logger = logging.getLogger(__name__)


def _ok(function_name: str, arguments: dict[str, Any], data: Any) -> dict[str, Any]:
    return {"ok": True, "function_name": function_name, "arguments": arguments, "data": data}


def _err(function_name: str, arguments: dict[str, Any], error: str) -> dict[str, Any]:
    return {"ok": False, "function_name": function_name, "arguments": arguments, "error": error}


def get_interest_keywords(user_id: int) -> dict[str, Any]:
    args = {"user_id": user_id}
    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT interest_text
                FROM user_interests
                WHERE user_id = :uid
                ORDER BY created_at ASC
                """
            ),
            {"uid": user_id},
        ).fetchall()
    return _ok("get_interest_keywords", args, [r.interest_text for r in rows])


def create_interest_keyword(user_id: int, keyword: str) -> dict[str, Any]:
    args = {"user_id": user_id, "keyword": keyword}
    keyword = (keyword or "").strip()
    if not keyword:
        return _err("create_interest_keyword", args, "empty keyword")

    embedding = embed_text(keyword)
    emb_literal = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"

    with session_scope() as s:
        # 유저 존재 확인.
        row = s.execute(text("SELECT 1 FROM users WHERE id = :uid"), {"uid": user_id}).first()
        if row is None:
            return _err("create_interest_keyword", args, f"user {user_id} not found")

        result = s.execute(
            text(
                """
                INSERT INTO user_interests (user_id, interest_text, embedding)
                VALUES (:uid, :it, CAST(:emb AS vector))
                ON CONFLICT (user_id, interest_text) DO NOTHING
                RETURNING id
                """
            ),
            {"uid": user_id, "it": keyword, "emb": emb_literal},
        ).first()
    interest_id = int(result.id) if result is not None else None
    return _ok(
        "create_interest_keyword",
        args,
        {"keyword": keyword, "interest_id": interest_id, "duplicate": interest_id is None},
    )


def delete_interest_keyword(user_id: int, keyword: str) -> dict[str, Any]:
    args = {"user_id": user_id, "keyword": keyword}
    keyword = (keyword or "").strip()
    if not keyword:
        return _err("delete_interest_keyword", args, "empty keyword")

    with session_scope() as s:
        result = s.execute(
            text(
                """
                DELETE FROM user_interests
                WHERE user_id = :uid AND interest_text = :it
                RETURNING id
                """
            ),
            {"uid": user_id, "it": keyword},
        ).first()
    deleted = result is not None
    return _ok(
        "delete_interest_keyword",
        args,
        {"keyword": keyword, "deleted": deleted},
    )


def get_recent_interest_notices(user_id: int, hours: int) -> dict[str, Any]:
    """유저에게 알림으로 갔거나 큐잉된 공지를 최근 N시간 내에서 조회.

    notifier worker가 통합되기 전이라도 filter.py가 큐 push할 때
    notifications 테이블에 'queued' row를 만들어두므로 여기서 보인다.
    """
    args = {"user_id": user_id, "hours": hours}
    if not isinstance(hours, int) or hours <= 0:
        return _err("get_recent_interest_notices", args, "hours must be a positive integer")

    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT n.id          AS notice_id,
                       n.title       AS title,
                       n.url         AS url,
                       n.source_id   AS source_id,
                       n.posted_at   AS posted_at,
                       nt.queued_at  AS queued_at,
                       nt.sent_at    AS sent_at,
                       nt.status     AS status
                FROM notifications nt
                JOIN notices n ON n.id = nt.notice_id
                WHERE nt.user_id = :uid
                  AND nt.queued_at >= now() - (:hours || ' hours')::interval
                ORDER BY nt.queued_at DESC
                LIMIT 100
                """
            ),
            {"uid": user_id, "hours": hours},
        ).fetchall()

    items = [
        {
            "notice_id": r.notice_id,
            "title": r.title,
            "url": r.url,
            "source_id": r.source_id,
            "posted_at": r.posted_at,
            "queued_at": r.queued_at.isoformat(timespec="seconds") if r.queued_at else None,
            "sent_at": r.sent_at.isoformat(timespec="seconds") if r.sent_at else None,
            "status": r.status,
        }
        for r in rows
    ]
    return _ok("get_recent_interest_notices", args, items)
