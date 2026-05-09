from __future__ import annotations

from dataclasses import dataclass

from .config import load_upstage_config
from .dispatcher import dispatch_plan
from .fallback import plan_with_fallback
from .llm import LLMPlanningError, UpstagePlanner
from .types import AgentPlan, AgentRunResult


@dataclass(slots=True)
class AgenticFlowService:
    use_llm: bool = True
    fallback_on_error: bool = True

    def plan(self, prompt: str) -> tuple[AgentPlan, str]:
        if self.use_llm:
            planner = UpstagePlanner(load_upstage_config())
            try:
                return planner.plan(prompt), "upstage"
            except LLMPlanningError:
                if not self.fallback_on_error:
                    raise
        return plan_with_fallback(prompt), "fallback"

    def run(self, prompt: str) -> AgentRunResult:
        plan, planner_name = self.plan(prompt)
        results = dispatch_plan(plan) if plan.should_call_function else []
        return AgentRunResult(
            prompt=prompt,
            plan=plan,
            results=results,
            planner=planner_name,
        )


def run_agentic_flow(
    prompt: str,
    *,
    use_llm: bool = True,
    fallback_on_error: bool = True,
) -> AgentRunResult:
    service = AgenticFlowService(
        use_llm=use_llm,
        fallback_on_error=fallback_on_error,
    )
    return service.run(prompt)
