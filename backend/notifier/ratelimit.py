"""유저별 일일 알림 한도 (Redis 카운터)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import redis

from config import settings

KST = timezone(timedelta(hours=9))


def _key(user_id: int, day: str) -> str:
    return f"notif:rate:{user_id}:{day}"


def try_consume(client: redis.Redis, user_id: int) -> bool:
    """오늘 한도 내면 카운트 +1 하고 True. 초과면 False."""
    day = datetime.now(KST).strftime("%Y-%m-%d")
    key = _key(user_id, day)
    pipe = client.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, 60 * 60 * 26)
    count, _ = pipe.execute()
    return int(count) <= settings.DAILY_LIMIT_PER_USER
