import json
import logging

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings
from service.llm_judge import judge

logger = logging.getLogger(__name__)
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)


def push_notice_to_redis_queue(db: Session, notice_id: int) -> None:
    """notice + notice_embeddings 조회 → 유사 유저 매칭 → LLM 판정 → Redis 큐."""
    notice = db.execute(
        text(
            """
            SELECT n.id        AS notice_id,
                   n.title     AS title,
                   COALESCE(n.body, n.summary, '') AS content,
                   ne.embedding AS embedding
            FROM notices n
            JOIN notice_embeddings ne ON ne.notice_id = n.id
            WHERE n.id = :nid
            """
        ),
        {"nid": notice_id},
    ).fetchone()

    if not notice:
        logger.error("Notice or its embedding not found for notice_id=%s", notice_id)
        return

    # 한 유저가 여러 관심사를 가질 수 있으므로, 각 user별로 가장 점수 높은
    # interest_text 하나만 LLM 판정으로 보낸다 (중복 호출 방지).
    matched_users = db.execute(
        text(
            """
            SELECT DISTINCT ON (ui.user_id)
                   ui.user_id        AS user_id,
                   ui.interest_text  AS interest_text,
                   1 - (ui.embedding <=> CAST(:n_emb AS vector)) AS score
            FROM user_interests ui
            WHERE 1 - (ui.embedding <=> CAST(:n_emb AS vector)) >= :threshold
            ORDER BY ui.user_id, score DESC
            """
        ),
        {
            "n_emb": str(notice.embedding),
            "threshold": settings.similarity_threshold,
        },
    ).fetchall()

    if not matched_users:
        logger.info("No similar users found for notice_id=%s", notice_id)
        return

    for user in matched_users:
        is_relevant = judge(user.interest_text, notice.title, notice.content)

        if is_relevant:
            queue_data = {"user_id": user.user_id, "notice_id": notice_id}
            redis_client.rpush("notification_queue", json.dumps(queue_data))
            logger.info("Successfully queued: User %s for Notice %s", user.user_id, notice_id)
