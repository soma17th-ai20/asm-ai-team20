"""Slack 슬래시 커맨드 라우터.

Slack 앱 설정 → Slash Commands → Request URL: https://<공개주소>/api/slack/command
서명 검증: Basic Information → Signing Secret 을 SLACK_SIGNING_SECRET env로.

지원 명령 (모두 ephemeral, 본인에게만 보임):
  /notice link <email>          내 Slack 계정을 등록된 이메일에 바인딩
  /notice 키워드                 내 키워드 목록
  /notice <키워드> 추가           키워드 추가
  /notice <키워드> 삭제           키워드 삭제
  /notice 알림                   최근 24시간 받은 알림
  /notice <자연어>               위 패턴에 안 맞으면 ai_agent에 그대로 위임
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, HTTPException, Request

from config import settings
from db import agent_repo
from db.users_repository import UserRepository
from service.agent_handler import run_for_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/slack", tags=["slack"])

REPLAY_WINDOW_SEC = 60 * 5  # Slack 권장: 5분 안 timestamp만 허용


def _verify_signature(
    raw_body: bytes,
    timestamp: str | None,
    signature: str | None,
) -> bool:
    """SLACK_SIGNING_SECRET 비어있으면 검증 스킵 (개발 모드)."""
    if not settings.SLACK_SIGNING_SECRET:
        return True
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > REPLAY_WINDOW_SEC:
        return False
    basestring = f"v0:{timestamp}:{raw_body.decode('utf-8', errors='replace')}".encode()
    expected = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_form(raw_body: bytes) -> dict[str, str]:
    pairs = parse_qs(raw_body.decode("utf-8"))
    return {k: v[0] for k, v in pairs.items() if v}


def _ephemeral(text: str) -> dict:
    return {"response_type": "ephemeral", "text": text}


HELP_TEXT = (
    "*학교공지 AI — 슬래시 커맨드*\n"
    "• `/notice link <email>` — 슬랙 계정 ↔ 등록된 이메일 연결\n"
    "• `/notice 키워드` — 내 키워드 목록\n"
    "• `/notice <키워드> 추가` — 키워드 추가\n"
    "• `/notice <키워드> 삭제` — 키워드 삭제\n"
    "• `/notice 알림` — 최근 24시간 받은 알림\n"
    "• `/notice <자유 자연어>` — AI 에이전트가 의도 해석"
)


@router.post("/command")
async def slash_command(
    request: Request,
    x_slack_request_timestamp: str | None = Header(default=None),
    x_slack_signature: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()
    if not _verify_signature(raw_body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=401, detail="invalid Slack signature")

    form = _parse_form(raw_body)
    slack_user_id = form.get("user_id")
    text_arg = (form.get("text") or "").strip()
    if not slack_user_id:
        raise HTTPException(status_code=400, detail="missing user_id")

    if not text_arg or text_arg.lower() in ("help", "도움", "도움말"):
        return _ephemeral(HELP_TEXT)

    repo = UserRepository()

    # 1) link 명령은 ai_agent 우회 — 인증/매핑 흐름이라 자연어로 처리하면 위험.
    if text_arg.lower().startswith("link "):
        email = text_arg[5:].strip()
        uid = repo.link_slack(slack_user_id, email)
        if uid is None:
            return _ephemeral(
                f"❌ `{email}` 이메일로 가입된 사용자가 없습니다.\n"
                "먼저 웹에서 회원가입 후 다시 시도해주세요."
            )
        return _ephemeral(f"✅ Slack 계정을 user_id={uid} ({email})에 연결했습니다.")

    # 2) 그 외 명령은 모두 우리 DB user_id가 필요하다.
    db_user_id = repo.get_user_id_by_slack(slack_user_id)
    if db_user_id is None:
        return _ephemeral(
            "👋 아직 계정이 연결되지 않았습니다.\n"
            "먼저 `/notice link <가입한이메일>` 로 연결해주세요."
        )

    # 3) 정형 패턴은 직접 dispatch (빠르고 결정론적). 매칭 안 되면 ai_agent로 위임.
    direct = _try_direct_dispatch(db_user_id, text_arg)
    if direct is not None:
        return _ephemeral(direct)

    try:
        result = run_for_user(db_user_id, text_arg, use_llm=True)
    except Exception as e:  # noqa: BLE001
        logger.exception("agent dispatch failed: %s", e)
        return _ephemeral(f"⚠️ 처리 중 오류: {e}")

    return _ephemeral(_format_result(result))


def _try_direct_dispatch(user_id: int, text_arg: str) -> str | None:
    """정형 슬래시 커맨드를 ai_agent 우회해서 직접 처리. 매칭 시 응답 문자열 반환, 아니면 None."""
    t = text_arg.strip()
    low = t.lower()

    # 키워드 목록
    if low in ("키워드", "키워드목록", "list", "ls"):
        result = agent_repo.get_interest_keywords(user_id)
        kws = result.get("data") or []
        return f"*키워드 ({len(kws)}개)*: " + (", ".join(kws) if kws else "_없음_")

    # 최근 알림
    if low in ("알림", "최근알림", "recent"):
        result = agent_repo.get_recent_interest_notices(user_id, hours=24)
        items = result.get("data") or []
        if not items:
            return "📭 최근 24시간 동안 받은 알림이 없어요."
        lines = [f"*최근 알림 ({len(items)}건)*"]
        for it in items[:5]:
            lines.append(f"• <{it.get('url')}|{it.get('title')}>")
        if len(items) > 5:
            lines.append(f"_…외 {len(items) - 5}건_")
        return "\n".join(lines)

    # `<keyword> 추가` / `<keyword> 삭제` — 마지막 토큰이 동사인 경우만.
    parts = t.split()
    if len(parts) >= 2:
        verb = parts[-1]
        keyword = " ".join(parts[:-1]).strip()
        if verb in ("추가", "등록"):
            result = agent_repo.create_interest_keyword(user_id, keyword)
            data = result.get("data") or {}
            if not result.get("ok"):
                return f"❌ 추가 실패: {result.get('error')}"
            if data.get("duplicate"):
                return f"⚠️ `{keyword}` 는 이미 등록되어 있어요."
            return f"✅ `{keyword}` 추가됨."
        if verb in ("삭제", "제거"):
            result = agent_repo.delete_interest_keyword(user_id, keyword)
            data = result.get("data") or {}
            if not result.get("ok"):
                return f"❌ 삭제 실패: {result.get('error')}"
            if data.get("deleted"):
                return f"🗑️ `{keyword}` 삭제됨."
            return f"⚠️ `{keyword}` 는 등록되어 있지 않아요."

    return None


def _format_result(result: dict) -> str:
    """ai_agent 응답을 사람이 읽을 수 있는 Slack 메시지로."""
    plan = result.get("plan", {})
    msg = plan.get("message", "")
    results = result.get("results", [])
    if not plan.get("should_call_function"):
        return msg or "처리할 작업을 찾지 못했어요."

    lines: list[str] = []
    if msg:
        lines.append(f"_{msg}_")
    for r in results:
        fn = r.get("function_name", "?")
        ok = r.get("ok")
        data = r.get("data")
        err = r.get("error")
        if not ok:
            lines.append(f"❌ `{fn}` 실패: {err}")
            continue
        if fn == "get_interest_keywords":
            kws = data or []
            lines.append(f"*키워드 ({len(kws)}개)*: " + (", ".join(kws) if kws else "_없음_"))
        elif fn == "create_interest_keyword":
            kw = data.get("keyword")
            if data.get("duplicate"):
                lines.append(f"⚠️ `{kw}` 는 이미 등록되어 있어요.")
            else:
                lines.append(f"✅ `{kw}` 추가됨.")
        elif fn == "delete_interest_keyword":
            kw = data.get("keyword")
            if data.get("deleted"):
                lines.append(f"🗑️ `{kw}` 삭제됨.")
            else:
                lines.append(f"⚠️ `{kw}` 는 등록되어 있지 않아요.")
        elif fn == "get_recent_interest_notices":
            items = data or []
            if not items:
                lines.append("📭 최근 알림이 없어요.")
            else:
                lines.append(f"*최근 알림 ({len(items)}건)*")
                for it in items[:5]:
                    lines.append(f"• <{it.get('url')}|{it.get('title')}>")
                if len(items) > 5:
                    lines.append(f"_…외 {len(items) - 5}건_")
        else:
            lines.append(f"`{fn}` → {data}")
    return "\n".join(lines)
