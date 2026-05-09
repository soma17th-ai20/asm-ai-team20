"""유저 등록 / 조회 / 관심사 CRUD / 알림 설정 라우터."""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from db import agent_repo
from db.users_repository import UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


class UserRegisterIn(BaseModel):
    email: EmailStr
    interest_text: str = Field(min_length=1, max_length=2000)


class UserRegisterOut(BaseModel):
    user_id: int
    email: EmailStr
    interest_text: str
    interest_id: int | None
    created_user: bool
    duplicate_interest: bool


class UserListItem(BaseModel):
    id: int
    email: EmailStr
    created_at: str
    interests: list[str]


class UserListOut(BaseModel):
    total: int
    items: list[UserListItem]


class LoginIn(BaseModel):
    email: EmailStr


class LoginOut(BaseModel):
    user_id: int
    email: EmailStr
    notification_frequency: Literal["realtime", "daily", "weekly"]
    interest_count: int
    created_at: str


class InterestIn(BaseModel):
    interest_text: str = Field(min_length=1, max_length=200)


class InterestOut(BaseModel):
    keyword: str
    interest_id: int | None
    duplicate: bool


class InterestListOut(BaseModel):
    user_id: int
    interests: list[str]


class SettingsPatchIn(BaseModel):
    email: Optional[EmailStr] = None
    notification_frequency: Optional[Literal["realtime", "daily", "weekly"]] = None


class SettingsOut(BaseModel):
    user_id: int
    email: EmailStr
    notification_frequency: Literal["realtime", "daily", "weekly"]
    created_at: str


class NotificationItem(BaseModel):
    notification_id: int
    notice_id: int
    title: str
    url: str
    source_id: str
    posted_at: str | None
    summary: str
    queued_at: str | None
    sent_at: str | None
    status: str
    feedback: str | None


class NotificationListOut(BaseModel):
    user_id: int
    items: list[NotificationItem]


def _repo() -> UserRepository:
    return UserRepository()


@router.post("", response_model=UserRegisterOut, status_code=201)
def register_user(payload: UserRegisterIn) -> UserRegisterOut:
    try:
        result = _repo().register(payload.email, payload.interest_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    logger.info(
        "user registered: email=%s user_id=%s interest_id=%s created_user=%s",
        result.email, result.user_id, result.interest_id, result.created_user,
    )
    return UserRegisterOut(
        user_id=result.user_id,
        email=result.email,
        interest_text=result.interest_text,
        interest_id=result.interest_id,
        created_user=result.created_user,
        duplicate_interest=result.interest_id is None,
    )


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn) -> LoginOut:
    """이메일로 사용자 식별. 없으면 404. (비밀번호 없는 식별만 — 알림 수신용 식별 한정)"""
    from sqlalchemy import text as _text

    from db.connection import session_scope

    with session_scope() as s:
        row = s.execute(
            _text(
                """
                SELECT u.id, u.email, u.notification_frequency, u.created_at,
                       (SELECT COUNT(*) FROM user_interests ui WHERE ui.user_id = u.id) AS ic
                FROM users u WHERE u.email = :email
                """
            ),
            {"email": payload.email},
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"등록되지 않은 이메일: {payload.email}")
    return LoginOut(
        user_id=row.id,
        email=row.email,
        notification_frequency=row.notification_frequency,
        interest_count=int(row.ic),
        created_at=row.created_at.isoformat(timespec="seconds"),
    )


@router.get("", response_model=UserListOut)
def list_users(limit: int = 100, offset: int = 0) -> UserListOut:
    if not (1 <= limit <= 500):
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    repo = _repo()
    items = [UserListItem(**row) for row in repo.list_users(limit=limit, offset=offset)]
    return UserListOut(total=repo.count_users(), items=items)


# ───── 관심사 CRUD ──────────────────────────────────────────────────────

@router.get("/{user_id}/interests", response_model=InterestListOut)
def list_interests(user_id: int) -> InterestListOut:
    result = agent_repo.get_interest_keywords(user_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result.get("error", "not found"))
    return InterestListOut(user_id=user_id, interests=list(result["data"]))


@router.post("/{user_id}/interests", response_model=InterestOut, status_code=201)
def add_interest(user_id: int, payload: InterestIn) -> InterestOut:
    result = agent_repo.create_interest_keyword(user_id, payload.interest_text)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result.get("error", "failed"))
    data = result["data"]
    return InterestOut(
        keyword=data["keyword"],
        interest_id=data["interest_id"],
        duplicate=data["duplicate"],
    )


@router.delete("/{user_id}/interests/{keyword}")
def remove_interest(user_id: int, keyword: str) -> dict:
    result = agent_repo.delete_interest_keyword(user_id, keyword)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "failed"))
    data = result["data"]
    if not data["deleted"]:
        raise HTTPException(status_code=404, detail=f"keyword {keyword!r} not found")
    return {"deleted": True, "keyword": data["keyword"]}


# ───── 알림 설정 + 내 알림 ──────────────────────────────────────────────

@router.get("/{user_id}/settings", response_model=SettingsOut)
def get_settings(user_id: int) -> SettingsOut:
    user = _repo().get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"user {user_id} not found")
    return SettingsOut(user_id=user["id"], **{k: user[k] for k in ("email", "notification_frequency", "created_at")})


@router.patch("/{user_id}/settings", response_model=SettingsOut)
def update_settings(user_id: int, payload: SettingsPatchIn) -> SettingsOut:
    try:
        user = _repo().update_settings(
            user_id,
            email=payload.email,
            notification_frequency=payload.notification_frequency,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if user is None:
        raise HTTPException(status_code=404, detail=f"user {user_id} not found")
    return SettingsOut(user_id=user["id"], **{k: user[k] for k in ("email", "notification_frequency", "created_at")})


@router.get("/{user_id}/notifications", response_model=NotificationListOut)
def list_my_notifications(user_id: int, hours: int = 24 * 7) -> NotificationListOut:
    if not (1 <= hours <= 24 * 90):
        raise HTTPException(status_code=422, detail="hours must be 1..2160")
    items_raw = _repo().list_user_notifications(user_id, hours=hours)
    return NotificationListOut(
        user_id=user_id,
        items=[NotificationItem(**r) for r in items_raw],
    )
