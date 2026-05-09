"""유저 등록 / 조회 라우터.

프론트엔드는 관심사 텍스트와 이메일을 이 엔드포인트로 보낸다.
서버는 즉시 임베딩(OpenAI) 후 user_interests에 저장한다.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

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


@router.get("", response_model=UserListOut)
def list_users(limit: int = 100, offset: int = 0) -> UserListOut:
    if not (1 <= limit <= 500):
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    repo = _repo()
    items = [UserListItem(**row) for row in repo.list_users(limit=limit, offset=offset)]
    return UserListOut(total=repo.count_users(), items=items)
