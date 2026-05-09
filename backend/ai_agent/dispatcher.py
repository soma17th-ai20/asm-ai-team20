from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import dummy_functions
from .types import AgentPlan

DummyFunction = Callable[..., dict[str, Any]]

FUNCTION_REGISTRY: dict[str, DummyFunction] = {
    "get_interest_keywords": dummy_functions.get_interest_keywords,
    "create_interest_keyword": dummy_functions.create_interest_keyword,
    "delete_interest_keyword": dummy_functions.delete_interest_keyword,
    "get_recent_interest_notices": dummy_functions.get_recent_interest_notices,
}


def dispatch_plan(plan: AgentPlan) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for call in plan.calls:
        func = FUNCTION_REGISTRY.get(call.function_name)
        if func is None:
            results.append(
                {
                    "ok": False,
                    "function_name": call.function_name,
                    "arguments": call.arguments,
                    "error": "unknown function",
                }
            )
            continue
        results.append(func(**call.arguments))
    return results
