from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from .config import UpstageConfig
from .prompts import SYSTEM_PROMPT
from .types import AgentPlan, FunctionCall


class LLMPlanningError(RuntimeError):
    pass


def _coerce_plan(payload: dict) -> AgentPlan:
    should_call_function = bool(payload.get("should_call_function", False))
    raw_calls = payload.get("calls", []) or []
    calls = [
        FunctionCall(
            function_name=str(call["function_name"]),
            arguments=dict(call.get("arguments", {})),
        )
        for call in raw_calls
        if "function_name" in call
    ]
    message = str(payload.get("message", ""))
    return AgentPlan(should_call_function=should_call_function, calls=calls, message=message)


class UpstagePlanner:
    def __init__(self, config: UpstageConfig) -> None:
        self.config = config

    def plan(self, prompt: str) -> AgentPlan:
        if not self.config.enabled:
            raise LLMPlanningError("SECRET_KEY is not configured.")

        body = json.dumps(
            {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        req = request.Request(
            self.config.chat_completions_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.secret_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise LLMPlanningError(f"upstage http error: {exc.code}") from exc
        except URLError as exc:
            raise LLMPlanningError(f"upstage url error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise LLMPlanningError("upstage response was not valid JSON.") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMPlanningError("upstage response schema was unexpected.") from exc

        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str):
            raise LLMPlanningError("upstage content was not a string.")

        try:
            plan_payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMPlanningError("planner output was not valid JSON.") from exc

        return _coerce_plan(plan_payload)
