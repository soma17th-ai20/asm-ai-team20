from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FunctionCall:
    function_name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentPlan:
    should_call_function: bool
    calls: list[FunctionCall] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_call_function": self.should_call_function,
            "calls": [call.to_dict() for call in self.calls],
            "message": self.message,
        }


@dataclass(slots=True)
class AgentRunResult:
    prompt: str
    plan: AgentPlan
    results: list[dict[str, Any]] = field(default_factory=list)
    planner: str = "fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "planner": self.planner,
            "plan": self.plan.to_dict(),
            "results": self.results,
        }
