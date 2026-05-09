from __future__ import annotations

import re

from .types import AgentPlan, FunctionCall

RECENT_HINTS = ("최근", "스크랩", "공지")
SHOW_HINTS = ("보여", "조회", "목록", "뭐 있어", "뭐있어", "알려")
CREATE_HINTS = ("추가", "등록", "넣어", "넣어줘", "저장")
DELETE_HINTS = ("삭제", "제거", "빼", "지워")

NOISE_TOKENS = {
    "관심사", "관심", "키워드", "등록", "추가", "삭제", "제거", "넣어줘",
    "넣어", "빼줘", "빼", "지워줘", "지워", "목록", "조회", "보여줘", "보여",
    "알려줘", "알려", "해줘", "해주세요", "추가해줘", "등록해줘", "삭제해줘",
    "제거해줘", "넣어줘", "빼줘", "지워줘", "좀", "내", "를", "을", "에", "로",
}

KOREAN_HOURS = {
    "하루": 24,
    "하룻동안": 24,
    "하루동안": 24,
    "이틀": 48,
    "이튿날": 48,
    "사흘": 72,
    "나흘": 96,
}


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_hours(prompt: str) -> int | None:
    text = _normalize_spaces(prompt)
    match = re.search(r"(\d+)\s*시간", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*일", text)
    if match:
        return int(match.group(1)) * 24
    for token, hours in KOREAN_HOURS.items():
        if token in text:
            return hours
    return None


def _strip_trailing_particles(text: str) -> str:
    return re.sub(r"(을|를|이|가|은|는|도|에|로|와|과)$", "", text.strip())


def _extract_keyword(prompt: str) -> str | None:
    text = _normalize_spaces(prompt)
    patterns = [
        r"(.+?)\s*(?:키워드|관심사)(?:로)?\s*(?:추가|등록|삭제|제거|빼줘|빼|지워줘|지워)",
        r"(?:관심사(?:에|로)?)\s*(.+?)\s*(?:추가|등록|삭제|제거)",
        r"(.+?)\s*(?:추가|등록|삭제|제거|빼줘|빼|지워줘|지워)해?줘?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        keyword = _strip_trailing_particles(match.group(1))
        if keyword and keyword not in NOISE_TOKENS:
            return keyword

    tokens = [tok for tok in re.split(r"[ ,]+", text) if tok]
    candidates = [tok for tok in tokens if tok not in NOISE_TOKENS]
    if len(candidates) == 1:
        return _strip_trailing_particles(candidates[0])
    return None


def plan_with_fallback(prompt: str) -> AgentPlan:
    text = _normalize_spaces(prompt)

    if _contains_any(text, RECENT_HINTS):
        hours = _extract_hours(text)
        if hours is None:
            return AgentPlan(False, [], "함수 호출에 필요한 파라미터가 부족합니다.")
        return AgentPlan(
            True,
            [FunctionCall("get_recent_interest_notices", {"hours": hours})],
            "최근 관심 공지 조회 요청으로 해석했습니다.",
        )

    if "키워드" in text or "관심사" in text:
        if _contains_any(text, CREATE_HINTS):
            keyword = _extract_keyword(text)
            if keyword is None:
                return AgentPlan(False, [], "함수 호출에 필요한 파라미터가 부족합니다.")
            return AgentPlan(
                True,
                [FunctionCall("create_interest_keyword", {"keyword": keyword})],
                "관심사 키워드 등록 요청으로 해석했습니다.",
            )
        if _contains_any(text, DELETE_HINTS):
            keyword = _extract_keyword(text)
            if keyword is None:
                return AgentPlan(False, [], "함수 호출에 필요한 파라미터가 부족합니다.")
            return AgentPlan(
                True,
                [FunctionCall("delete_interest_keyword", {"keyword": keyword})],
                "관심사 키워드 삭제 요청으로 해석했습니다.",
            )
        if _contains_any(text, SHOW_HINTS):
            return AgentPlan(
                True,
                [FunctionCall("get_interest_keywords", {})],
                "관심사 키워드 조회 요청으로 해석했습니다.",
            )

    return AgentPlan(False, [], "현재 지원하지 않는 요청입니다.")
