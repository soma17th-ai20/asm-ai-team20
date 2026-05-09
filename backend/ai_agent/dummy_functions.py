from __future__ import annotations


def get_interest_keywords() -> dict:
    return {
        "ok": True,
        "function_name": "get_interest_keywords",
        "arguments": {},
        "data": ["장학금", "인턴", "세미나"],
    }


def create_interest_keyword(keyword: str) -> dict:
    return {
        "ok": True,
        "function_name": "create_interest_keyword",
        "arguments": {"keyword": keyword},
        "data": {"keyword": keyword, "status": "created"},
    }


def delete_interest_keyword(keyword: str) -> dict:
    return {
        "ok": True,
        "function_name": "delete_interest_keyword",
        "arguments": {"keyword": keyword},
        "data": {"keyword": keyword, "status": "deleted"},
    }


def get_recent_interest_notices(hours: int) -> dict:
    return {
        "ok": True,
        "function_name": "get_recent_interest_notices",
        "arguments": {"hours": hours},
        "data": [
            {"title": "장학금 신청 안내", "hours": hours},
            {"title": "인턴 모집 공지", "hours": hours},
        ],
    }
