"""SMTP 이메일 발송.

스팸 필터(특히 Outlook/Hotmail)에서 정크 처리 안 되도록 표준 헤더를 챙긴다:
  - Message-ID  : RFC 5322 필수, 없으면 신뢰도 하락
  - Date        : smtplib가 자동 추가하지만 명시
  - Reply-To    : 자동 메일임을 표시
  - List-Unsubscribe + List-Unsubscribe-Post : RFC 8058 원클릭 해지
  - Auto-Submitted: auto-generated  (RFC 3834)
  - X-Mailer    : 발신 시스템 식별
"""
from __future__ import annotations

import logging
import smtplib
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from config import settings

logger = logging.getLogger(__name__)


def _sender_domain() -> str:
    addr = settings.SMTP_FROM or settings.SMTP_USER
    return addr.split("@", 1)[1] if "@" in addr else "localhost"


def send_email(to_addr: str, subject: str, body: str) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping send to %s", to_addr)
        return False

    sender = settings.SMTP_FROM or settings.SMTP_USER

    msg = EmailMessage()
    msg["From"] = f"학교공지 AI <{sender}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=_sender_domain())
    msg["Reply-To"] = sender
    msg["Auto-Submitted"] = "auto-generated"
    msg["X-Mailer"] = "school-notice-ai/0.1"
    # 원클릭 구독 해지 (스팸 점수 큰 폭 감소). 실제 처리 endpoint는 v0.5에 추가 예정.
    msg["List-Unsubscribe"] = f"<mailto:{sender}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        logger.error("email send failed to=%s err=%s", to_addr, e)
        return False

    logger.info("email sent: to=%s subject=%s", to_addr, subject)
    return True
