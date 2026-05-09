"""ai_agent의 planning만 사용하고, dispatch는 우리 DB 함수로 대체.

ai_agent 내부 코드는 일절 수정하지 않는다 (사양). 흐름:

  prompt
    │
    ▼  ai_agent.UpstagePlanner.plan() (또는 SECRET_KEY 없을 때 fallback)
  AgentPlan
    │
    ▼  여기 자체 REGISTRY로 dispatch (db.agent_repo의 실 DB 함수)
  AgentRunResult-like dict
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from ai_agent.config import load_upstage_config
from ai_agent.fallback import plan_with_fallback
from ai_agent.llm import LLMPlanningError, UpstagePlanner
from ai_agent.types import AgentPlan

from db import agent_repo

logger = logging.getLogger(__name__)

# ai_agent.types.FunctionCall.function_name → 실 구현 함수.
# 모든 함수는 user_id를 첫 번째 키워드 인자로 받는다 + 나머지는 plan.arguments.
REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "get_interest_keywords": agent_repo.get_interest_keywords,
    "create_interest_keyword": agent_repo.create_interest_keyword,
    "delete_interest_keyword": agent_repo.delete_interest_keyword,
    "get_recent_interest_notices": agent_repo.get_recent_interest_notices,
}


def _plan(prompt: str, use_llm: bool) -> tuple[AgentPlan, str]:
    if use_llm:
        try:
            cfg = load_upstage_config()
            return UpstagePlanner(cfg).plan(prompt), "upstage"
        except LLMPlanningError as e:
            logger.warning("LLM planning failed → fallback: %s", e)
    return plan_with_fallback(prompt), "fallback"


def run_for_user(user_id: int, prompt: str, use_llm: bool = True) -> dict[str, Any]:
    plan, planner = _plan(prompt, use_llm)

    results: list[dict[str, Any]] = []
    for call in plan.calls:
        func = REGISTRY.get(call.function_name)
        if func is None:
            results.append({
                "ok": False,
                "function_name": call.function_name,
                "arguments": call.arguments,
                "error": "unknown function",
            })
            continue
        try:
            results.append(func(user_id=user_id, **call.arguments))
        except TypeError as e:
            results.append({
                "ok": False,
                "function_name": call.function_name,
                "arguments": call.arguments,
                "error": f"bad arguments: {e}",
            })
        except Exception as e:  # noqa: BLE001 — 사용자 메시지 처리 중 미예상 예외도 응답으로 흡수
            logger.exception("agent function error")
            results.append({
                "ok": False,
                "function_name": call.function_name,
                "arguments": call.arguments,
                "error": str(e),
            })

    return {
        "prompt": prompt,
        "planner": planner,
        "plan": plan.to_dict(),
        "results": results,
    }
