import logging
from typing import List
import json

from sqlalchemy import text
from sqlalchemy.orm import Session
import redis

from config import settings
from service.llm_judge import judge

logger = logging.getLogger(__name__)
redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)


def push_notice_to_redis_queue(
    db: Session,
    notice_id: int
):
    notice = db.execute(
        text("""
            SELECT title, content, embedding
            FROM notice
            WHERE notice_id = :nid
        """),
        {"nid": notice_id}
    ).fetchone()

    if not notice:
        logger.error(f"Notice not found for notice_id={notice_id}")
        return

    matched_users = db.execute(
        text("""
            SELECT id, interest_text
            FROM users
            WHERE 1 - (embedding <=> CAST(:n_emb AS vector)) >= :threshold
        """),
        {
            "n_emb": str(notice.embedding),
            "threshold": settings.similarity_threshold
        }
    ).fetchall()

    if not matched_users:
        logger.info(f"No similar users found for notice_id={notice_id}")
        return


    for user in matched_users:
        is_relevant = judge(user.interest_text, notice.title, notice.content)

        if is_relevant:
            queue_data = {
                "user_id": user.id,
                "notice_id": notice_id
            }

            redis_client.rpush("notification_queue", json.dumps(queue_data))
            logger.info(f"Successfully queued: User {user.id} for Notice {notice_id}")