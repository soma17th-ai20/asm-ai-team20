# 학교 공지 AI 알림 서비스 — 20팀

이 저장소는 학교/채용 공지 수집과 AI 기반 함수 호출 라우팅을 분리해서 개발하는 통합용 작업 공간이다.

## 구성

| 디렉토리 | 역할 | 통합 기준 문서 |
| --- | --- | --- |
| `crawler/` | 공지 수집, 정규화, 저장, 조회 | [crawler/README.md](./crawler/README.md) |
| `ai_agent/` | 자연어 요청을 함수 호출 계획 JSON으로 변환 | [ai_agent/README.md](./ai_agent/README.md) |
| `src/` | 현재 데모 UI | - |
| `docs/` | 기획/스펙 문서 | - |

## 현재 상태

- `crawler/`는 수집 레이어 MVP가 구현되어 있다.
- `ai_agent/`는 agentic flow 1단계 구현체다.
- `src/`는 실제 서비스 UI가 아니라 개발 확인용 데모다.

## 팀원이 먼저 봐야 할 곳

- 공지 수집/DB 통합: [crawler/README.md](./crawler/README.md)
- 자연어 요청 -> 함수 호출 계획 연동: [ai_agent/README.md](./ai_agent/README.md)

## 빠른 실행

크롤러 API:

```bash
cd crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

AI 에이전트 테스트:

```bash
python3 -m ai_agent.main "장학금 키워드 추가해줘" --no-llm
```

프론트 데모:

```bash
npm install
npm run dev
```
