"""에이전트 라우터.

POST /api/agent — {user_id, prompt, use_llm?}을 받아 ai_agent로 의도를 해석한 뒤
실 DB 함수로 dispatch한 결과를 돌려준다. ai_agent 코드 자체는 수정하지 않는다.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from service.agent_handler import run_for_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentRequest(BaseModel):
    user_id: int = Field(ge=1)
    prompt: str = Field(min_length=1, max_length=2000)
    use_llm: bool = True   # SECRET_KEY 없으면 자동 fallback이라 그대로 둬도 무관


class FunctionCallOut(BaseModel):
    function_name: str
    arguments: dict


class AgentPlanOut(BaseModel):
    should_call_function: bool
    calls: list[FunctionCallOut]
    message: str


class AgentResponse(BaseModel):
    prompt: str
    planner: str  # "upstage" | "fallback"
    plan: AgentPlanOut
    results: list[dict]


@router.post("", response_model=AgentResponse)
def run_agent(payload: AgentRequest) -> AgentResponse:
    out = run_for_user(payload.user_id, payload.prompt, use_llm=payload.use_llm)
    return AgentResponse(**out)
