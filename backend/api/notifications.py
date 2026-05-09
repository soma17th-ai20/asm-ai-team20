"""알림 피드백 라우터."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.users_repository import UserRepository

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class FeedbackIn(BaseModel):
    feedback: Optional[Literal["like", "dislike"]]


class FeedbackOut(BaseModel):
    notification_id: int
    feedback: Optional[Literal["like", "dislike"]]


@router.post("/{notification_id}/feedback", response_model=FeedbackOut)
def set_feedback(notification_id: int, payload: FeedbackIn) -> FeedbackOut:
    try:
        result = UserRepository().set_feedback(notification_id, payload.feedback)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if result is None and payload.feedback is not None:
        # UPDATE가 빈 행이면 notification이 없는 것
        raise HTTPException(status_code=404, detail=f"notification {notification_id} not found")
    return FeedbackOut(notification_id=notification_id, feedback=result)
