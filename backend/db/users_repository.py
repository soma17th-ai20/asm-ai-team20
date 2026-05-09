"""유저 등록 + 관심사 저장.

프론트가 보낸 {email, interest_text}를 받아:
  1. users 테이블에 email로 upsert (이미 있으면 그대로 가져옴)
  2. interest_text를 임베딩
  3. user_interests에 (user_id, interest_text, embedding) 삽입
     - (user_id, interest_text) UNIQUE 충돌 시 무시 (멱등)

에 사용된다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from .connection import session_scope
from service.embedding import embed_text

logger = logging.getLogger(__name__)


@dataclass
class RegisterResult:
    user_id: int
    email: str
    interest_text: str
    interest_id: Optional[int]   # None이면 (user_id, interest_text) 중복으로 무시됨
    created_user: bool           # users 테이블에 새로 만들었는지


class UserRepository:
    def register(self, email: str, interest_text: str) -> RegisterResult:
        """email + interest_text 한 쌍을 멱등 등록."""
        if not email or "@" not in email:
            raise ValueError(f"invalid email: {email!r}")
        if not interest_text or not interest_text.strip():
            raise ValueError("interest_text is empty")
        interest_text = interest_text.strip()

        embedding = embed_text(interest_text)
        emb_literal = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"

        with session_scope() as s:
            # 1) users upsert. RETURNING으로 새로 만들어졌는지 판별.
            row = s.execute(
                text(
                    """
                    INSERT INTO users (email)
                    VALUES (:email)
                    ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
                    RETURNING id, (xmax = 0) AS created
                    """
                ),
                {"email": email},
            ).first()
            user_id = int(row.id)
            created_user = bool(row.created)

            # 2) user_interests insert. UNIQUE 충돌 시 None.
            interest_row = s.execute(
                text(
                    """
                    INSERT INTO user_interests (user_id, interest_text, embedding)
                    VALUES (:uid, :it, CAST(:emb AS vector))
                    ON CONFLICT (user_id, interest_text) DO NOTHING
                    RETURNING id
                    """
                ),
                {"uid": user_id, "it": interest_text, "emb": emb_literal},
            ).first()
            interest_id = int(interest_row.id) if interest_row is not None else None

        return RegisterResult(
            user_id=user_id,
            email=email,
            interest_text=interest_text,
            interest_id=interest_id,
            created_user=created_user,
        )

    def list_users(self, limit: int = 100, offset: int = 0) -> list[dict]:
        with session_scope() as s:
            rows = s.execute(
                text(
                    """
                    SELECT u.id, u.email, u.created_at,
                           COALESCE(
                               (SELECT json_agg(ui.interest_text ORDER BY ui.created_at)
                                FROM user_interests ui WHERE ui.user_id = u.id),
                               '[]'::json
                           ) AS interests
                    FROM users u
                    ORDER BY u.id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            ).fetchall()
        return [
            {
                "id": r.id,
                "email": r.email,
                "created_at": r.created_at.isoformat(timespec="seconds"),
                "interests": list(r.interests),
            }
            for r in rows
        ]

    def count_users(self) -> int:
        with session_scope() as s:
            row = s.execute(text("SELECT COUNT(*) AS c FROM users")).first()
        return int(row.c) if row else 0

    def get_user(self, user_id: int) -> Optional[dict]:
        with session_scope() as s:
            row = s.execute(
                text(
                    """
                    SELECT id, email, notification_frequency, created_at
                    FROM users WHERE id = :uid
                    """
                ),
                {"uid": user_id},
            ).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "email": row.email,
            "notification_frequency": row.notification_frequency,
            "created_at": row.created_at.isoformat(timespec="seconds"),
        }

    def update_settings(
        self,
        user_id: int,
        email: Optional[str] = None,
        notification_frequency: Optional[str] = None,
    ) -> Optional[dict]:
        """email/notification_frequency 부분 업데이트. 둘 다 None이면 NOOP."""
        if email is None and notification_frequency is None:
            return self.get_user(user_id)
        if notification_frequency is not None and notification_frequency not in (
            "realtime", "daily", "weekly",
        ):
            raise ValueError(f"invalid frequency: {notification_frequency!r}")

        sets, params = [], {"uid": user_id}
        if email is not None:
            sets.append("email = :email")
            params["email"] = email
        if notification_frequency is not None:
            sets.append("notification_frequency = :freq")
            params["freq"] = notification_frequency

        with session_scope() as s:
            row = s.execute(
                text(
                    f"""
                    UPDATE users SET {", ".join(sets)}
                    WHERE id = :uid
                    RETURNING id, email, notification_frequency, created_at
                    """
                ),
                params,
            ).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "email": row.email,
            "notification_frequency": row.notification_frequency,
            "created_at": row.created_at.isoformat(timespec="seconds"),
        }

    def list_user_notifications(self, user_id: int, hours: int = 24 * 7) -> list[dict]:
        with session_scope() as s:
            rows = s.execute(
                text(
                    """
                    SELECT nt.id          AS notification_id,
                           n.id           AS notice_id,
                           n.title        AS title,
                           n.url          AS url,
                           n.source_id    AS source_id,
                           n.posted_at    AS posted_at,
                           COALESCE(n.summary, LEFT(COALESCE(n.body, ''), 300)) AS summary,
                           nt.queued_at   AS queued_at,
                           nt.sent_at     AS sent_at,
                           nt.status      AS status,
                           nt.feedback    AS feedback
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
        return [
            {
                "notification_id": r.notification_id,
                "notice_id": r.notice_id,
                "title": r.title,
                "url": r.url,
                "source_id": r.source_id,
                "posted_at": r.posted_at,
                "summary": r.summary or "",
                "queued_at": r.queued_at.isoformat(timespec="seconds") if r.queued_at else None,
                "sent_at": r.sent_at.isoformat(timespec="seconds") if r.sent_at else None,
                "status": r.status,
                "feedback": r.feedback,
            }
            for r in rows
        ]

    def set_feedback(self, notification_id: int, feedback: Optional[str]) -> Optional[str]:
        """notifications.feedback을 'like'/'dislike'/None으로 세팅."""
        if feedback not in ("like", "dislike", None):
            raise ValueError(f"invalid feedback: {feedback!r}")
        with session_scope() as s:
            row = s.execute(
                text(
                    """
                    UPDATE notifications SET feedback = :fb
                    WHERE id = :nid
                    RETURNING feedback
                    """
                ),
                {"nid": notification_id, "fb": feedback},
            ).first()
        return row.feedback if row else None
