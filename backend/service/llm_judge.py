import json
import logging
import time
from typing import Optional

from openai import OpenAI

from config import settings
from prompts import PROMPTS

MAX_RETRIES = 3
RETRY_DELAY = 2

logger = logging.getLogger(__name__)
_openai_client = OpenAI(api_key=settings.openai_api_key)


def judge(interest_text: str, title: str, content: str) -> Optional[dict]:
    """GPT API 호출 및 JSON 파싱. 실패 시 None 반환."""

    judge_cfg = PROMPTS["notice_judge"]
    user_prompt = judge_cfg["user_template"].format(
        interest_text=interest_text,
        title=title,
        content=content[:1500]
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _openai_client.chat.completions.create(
                model=settings.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": judge_cfg["system_prompt"]},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.1
            )

            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)

            score = int(parsed["score"])
            if not (0 <= score <= 10):
                raise ValueError(f"score out of range: {score}")

            if score >= settings.llm_threshold:
                return {
                    "score": score,
                    "summary": str(parsed["summary"]),
                    "reason": str(parsed["reason"]),
                }
            else:
                return None

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"[Attempt {attempt}] Parse error for notice '{title}': {e}")
        except Exception as e:
            logger.warning(f"[Attempt {attempt}] OpenAI API error: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return None


def extract_keyword(text: str) -> str:
    """자연어 문장에서 관심 키워드를 추출한다. 실패 시 원본 text 반환."""
    try:
        response = _openai_client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "사용자의 문장에서 관심 키워드를 짧은 명사 형태로 하나만 추출하세요. "
                        "예시: '장학금을 받고싶어요' → '장학금', 'AI 공모전이 궁금해요' → 'AI 공모전'. "
                        "키워드만 출력하고 다른 설명은 절대 하지 마세요."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=50,
            temperature=0,
        )
        keyword = response.choices[0].message.content.strip()
        return keyword if keyword else text
    except Exception as e:
        logger.warning("keyword extraction failed for %r: %s", text, e)
        return text
