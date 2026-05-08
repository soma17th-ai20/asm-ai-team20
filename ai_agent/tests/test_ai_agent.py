from __future__ import annotations

import unittest

from ai_agent.dispatcher import dispatch_plan
from ai_agent.fallback import plan_with_fallback
from ai_agent.service import AgenticFlowService


class FallbackPlannerTest(unittest.TestCase):
    def test_create_keyword(self) -> None:
        plan = plan_with_fallback("장학금 키워드 추가해줘")
        self.assertTrue(plan.should_call_function)
        self.assertEqual(plan.calls[0].function_name, "create_interest_keyword")
        self.assertEqual(plan.calls[0].arguments, {"keyword": "장학금"})

    def test_list_keywords(self) -> None:
        plan = plan_with_fallback("내 관심 키워드 보여줘")
        self.assertTrue(plan.should_call_function)
        self.assertEqual(plan.calls[0].function_name, "get_interest_keywords")
        self.assertEqual(plan.calls[0].arguments, {})

    def test_recent_notice(self) -> None:
        plan = plan_with_fallback("최근 하루 동안 스크랩된 공지 보여줘")
        self.assertTrue(plan.should_call_function)
        self.assertEqual(plan.calls[0].function_name, "get_recent_interest_notices")
        self.assertEqual(plan.calls[0].arguments, {"hours": 24})

    def test_missing_parameter(self) -> None:
        plan = plan_with_fallback("키워드 추가해줘")
        self.assertFalse(plan.should_call_function)
        self.assertEqual(plan.calls, [])
        self.assertEqual(plan.message, "함수 호출에 필요한 파라미터가 부족합니다.")

    def test_unsupported_request(self) -> None:
        plan = plan_with_fallback("오늘 날씨 알려줘")
        self.assertFalse(plan.should_call_function)
        self.assertEqual(plan.calls, [])
        self.assertEqual(plan.message, "현재 지원하지 않는 요청입니다.")


class DispatcherTest(unittest.TestCase):
    def test_dispatch_runs_dummy_function(self) -> None:
        plan = plan_with_fallback("장학금 키워드 추가해줘")
        results = dispatch_plan(plan)
        self.assertEqual(results[0]["function_name"], "create_interest_keyword")
        self.assertEqual(results[0]["arguments"], {"keyword": "장학금"})


class ServiceTest(unittest.TestCase):
    def test_service_runs_end_to_end_without_llm(self) -> None:
        service = AgenticFlowService(use_llm=False)
        result = service.run("인턴 키워드 삭제해줘")
        self.assertEqual(result.planner, "fallback")
        self.assertEqual(result.plan.calls[0].function_name, "delete_interest_keyword")
        self.assertEqual(result.results[0]["data"]["status"], "deleted")


if __name__ == "__main__":
    unittest.main()
