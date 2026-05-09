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
