# backend — DB · 임베딩 · 크롤러 · 스케줄러 · 알림 통합 레이어

이 디렉토리는 다섯 모듈을 묶는다.

| 영역 | 위치 | 비고 |
| --- | --- | --- |
| 크롤러 | `crawler/` | feat/crawler에서 가져온 모듈 (변경 없음) |
| 임베딩 / LLM 판정 / Redis 매칭 | `service/` | feat/embedding에서 가져옴 — `filter.py`는 분리 스키마에 맞게 수정 |
| DB | `db/` | PostgreSQL + pgvector. 세션 팩토리 + 스키마 + 리포지토리. |
| HTTP 라우터 | `api/`, `main.py` | 크롤러 라우터 + 유저 등록 라우터 + 에이전트 라우터를 한 앱으로 묶는다. |
| AI 에이전트 | `ai_agent/` | feat/ai-agent에서 가져옴. Upstage solar-pro2로 자연어 → 함수 호출 계획 변환. `SECRET_KEY` 미설정 시 룰 기반 fallback. |
| **스케줄러 + 알림 (이주호)** | **`scheduler/`, `notifier/`** | **APScheduler가 `/api/crawl` 주기 호출, Redis BLPOP 워커가 이메일 발송.** |

## 스키마

`backend/db/schema.sql`. 핵심 결정:

- `notices` — 크롤러 메타데이터 (`source_id`, `url`, `posted_at`, `summary`, `body`, `hash`, `fetched_at`). 중복은 `hash UNIQUE` + `ON CONFLICT DO NOTHING`.
- `notice_embeddings` — `notice_id` PK FK → `notices.id`. 1:1. 모델 교체 추적용 `model TEXT`. 미임베딩 공지는 `LEFT JOIN ... WHERE ne.notice_id IS NULL`로 즉시 식별.
- `users` — `email UNIQUE`. 알림 수신 주체.
- `user_interests` — `user_id FK`, `interest_text`, `embedding vector(1536)`. 한 유저에 여러 관심사 가능. `(user_id, interest_text)` UNIQUE로 멱등.
- `notifications` — `(user_id, notice_id) UNIQUE`. `filter.py`가 매칭 통과 시 `queued`로 INSERT. notifier worker가 발송 후 `sent_at` + `status` 업데이트.
- pgvector ANN 인덱스(`ivfflat`)는 row가 충분히 쌓이면 켠다. 현재는 주석.

## 빠른 시작

### A. Docker만으로 (권장)

```bash
cd ..                      # 프로젝트 루트
cp .env.example .env       # OPENAI_API_KEY 채우기
docker compose up -d --build
# postgres + redis + backend 모두 한 번에. backend는 자동 스키마 init + uvicorn --reload.
```

자주 쓰는 컨테이너 명령:

```bash
docker compose exec backend python -m cli ingest               # 크롤+임베딩
docker compose exec backend python -m cli crawl --source snu_cse_notice
docker compose exec backend python -m cli embed
docker compose exec postgres psql -U team20 -c '\dt'           # 테이블 확인
docker compose logs -f backend                                 # 로그
docker compose down                                            # 정지
docker compose down -v                                         # 정지 + 볼륨 초기화
```

### B. 로컬 Python (인프라만 docker)

```bash
docker compose up -d postgres redis
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # backend 단독 실행용 — OPENAI_API_KEY 채우기

python -m cli init         # 스키마(멱등)
python -m cli ingest       # 크롤+임베딩
uvicorn main:app --reload --port 8000
```

API: <http://localhost:8000/docs>

## HTTP 엔드포인트

### 시스템 / 크롤
| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/api/health` | 헬스체크 |
| GET | `/api/sources` | 크롤 대상 목록 |
| GET | `/api/notices` | 저장된 공지 페이지네이션 |
| POST | `/api/crawl` | 즉시 크롤 트리거 (FE "지금 크롤링" 버튼) |

### 사용자 / 인증
| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| POST | `/api/users` | 가입 — `{email, interest_text}` → user_id, 첫 관심사 등록 |
| POST | `/api/users/login` | 이메일로 식별 (비밀번호 X, newsletter-style) |
| GET | `/api/users` | 등록된 유저 + 관심사 목록 |

### 관심사 키워드 (LLM 우회 직접 CRUD — FE의 `/keywords` 페이지에서 사용)
| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/api/users/{uid}/interests` | 키워드 목록 |
| POST | `/api/users/{uid}/interests` | 키워드 추가 (`{interest_text}`) |
| DELETE | `/api/users/{uid}/interests/{keyword}` | 키워드 삭제 |

### 알림 설정 / 피드 / 피드백
| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET · PATCH | `/api/users/{uid}/settings` | 이메일 + `notification_frequency` (realtime/daily/weekly) |
| GET | `/api/users/{uid}/notifications?hours=N` | 내가 받은 알림 (notifications ⨝ notices) |
| POST | `/api/notifications/{nid}/feedback` | 👍/👎 (`{feedback: 'like'\|'dislike'\|null}`) |

### AI 에이전트 / Slack
| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| POST | `/api/agent` | 자연어 프롬프트 → ai_agent 의도 해석 → 함수 dispatch |
| POST | `/api/slack/command` | Slack 슬래시 커맨드 (HMAC 서명 검증) — 자세한 건 [SLACK.md](SLACK.md) |

### 에이전트 워크플로우 (5개 기능)

| # | 기능 | 라우팅 | 처리 함수 |
| - | --- | --- | --- |
| 1 | n일 전부터 알림 리스트 | `POST /api/agent` (LLM) | `db.agent_repo.get_recent_interest_notices(user_id, hours)` ← `notifications ⨝ notices` |
| 2 | 키워드 추가 | `POST /api/agent` (LLM) | `db.agent_repo.create_interest_keyword(user_id, keyword)` ← embed + INSERT user_interests |
| 3 | 키워드 삭제 | `POST /api/agent` (LLM) | `db.agent_repo.delete_interest_keyword(user_id, keyword)` |
| 4 | 키워드 조회 | `POST /api/agent` (LLM) | `db.agent_repo.get_interest_keywords(user_id)` |
| 5 | 지금 크롤링 | `POST /api/crawl` (직접 호출, ai_agent 우회) | `crawler.app.service.NoticeCrawlService.crawl_all()` |

5번이 ai_agent 우회 이유: 현재 ai_agent의 system prompt + fallback이 4개 함수만 알고 있기 때문. ai_agent를 수정하지 않는 방침이라 프론트가 별도 버튼으로 직접 호출.

### `POST /api/agent` 예시

```bash
curl -X POST http://localhost:8000/api/agent \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 1, "prompt": "장학금 키워드 추가해줘"}'
```

응답:

```json
{
  "prompt": "장학금 키워드 추가해줘",
  "planner": "upstage",
  "plan": {
    "should_call_function": true,
    "calls": [{"function_name": "create_interest_keyword", "arguments": {"keyword": "장학금"}}],
    "message": "관심사 키워드 등록 요청으로 해석했습니다."
  },
  "results": [
    {"ok": true, "function_name": "create_interest_keyword",
     "arguments": {"user_id": 1, "keyword": "장학금"},
     "data": {"keyword": "장학금", "interest_id": 7, "duplicate": false}}
  ]
}
```

`SECRET_KEY` 미설정이거나 LLM 실패 시 `planner`가 `fallback`으로 떨어지고 룰 기반 파서가 동일 형식의 plan을 만든다. `use_llm=false`로 강제 가능.

`POST /api/users` 예시:

```bash
curl -X POST http://localhost:8000/api/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","interest_text":"장학금 인턴"}'
```

응답:

```json
{
  "user_id": 1,
  "email": "alice@example.com",
  "interest_text": "장학금 인턴",
  "interest_id": 1,
  "created_user": true,
  "duplicate_interest": false
}
```

같은 email로 다시 보내면 `created_user=false`. 같은 (email, interest_text) 쌍을 다시 보내면 `duplicate_interest=true`이고 `interest_id=null`.

## 데이터 흐름

```
[프론트엔드]
   POST /api/users  {email, interest_text}
        └─ api.users → service.embedding.embed_text → users + user_interests 저장

[크롤러]                    ◀── (이주호) scheduler/main.py 가 30분마다 POST /api/crawl
crawler.NoticeCrawlService
   └─ PostgresNoticeRepository.insert_many()
        └─ INSERT ... ON CONFLICT (hash) DO NOTHING

service.ingestion.embed_pending()
   ├─ repo.list_pending_embeddings()   # LEFT JOIN으로 미임베딩 공지
   ├─ service.embedding.embed_texts()   # OpenAI batch
   └─ repo.save_embeddings()            # notice_embeddings UPSERT

[매칭]
service.filter.push_notice_to_redis_queue(db, notice_id)
   ├─ notices ⨝ notice_embeddings 조회
   ├─ user_interests와 cosine 유사도 매칭 (DISTINCT ON user_id, 점수 최고 1건)
   ├─ service.llm_judge.judge()        # 정밀 판정
   ├─ notifications INSERT (status='queued')
   └─ Redis "notification_queue" rpush  {user_id, notice_id}

[발송]                      ◀── (이주호) notifier/worker.py BLPOP
notifier.worker
   ├─ users ⨝ notices 조회 (이메일, 제목, 본문)
   ├─ ratelimit.try_consume (Redis INCR, 유저당 일일 5건)
   ├─ mailer.send_email (smtplib STARTTLS)
   └─ notifications UPDATE (status='sent', sent_at=now)
```

## AI 에이전트 (`ai_agent/`)

Upstage solar-pro2를 호출해 자연어를 함수 호출 계획 JSON으로 바꾸는 모듈. `SECRET_KEY`가 설정되어 있지 않으면 자동으로 룰 기반 fallback 파서를 쓴다.

```bash
# Docker (env에 SECRET_KEY가 들어가 있음)
docker compose exec backend python -m ai_agent.main "장학금 키워드 추가해줘"

# 로컬 (backend/.env에 SECRET_KEY 설정)
cd backend && python -m ai_agent.main "최근 하루 동안 스크랩된 공지 보여줘"

# LLM 호출 없이 fallback만
python -m ai_agent.main "인턴 키워드 삭제해줘" --no-llm
```

지원 함수: `get_interest_keywords`, `create_interest_keyword`, `delete_interest_keyword`, `get_recent_interest_notices`. `dispatcher`가 `db.agent_repo`로 라우팅한다.

## 스케줄러 + 알림 (이주호)

### 구성

```
scheduler/main.py     # APScheduler → POST /api/crawl 주기 트리거
notifier/worker.py    # Redis notification_queue BLPOP → DB lookup → 이메일 → notifications UPDATE
notifier/mailer.py    # SMTP 발송 (stdlib smtplib)
notifier/ratelimit.py # 유저당 일일 N건 한도 (Redis INCR, KST 기준)
```

### 실행 (backend/ 에서)

```bash
# 사전: docker compose up -d postgres redis 가 떠 있어야 함
.venv/Scripts/python -m uvicorn main:app --port 8000   # API
.venv/Scripts/python -m scheduler.main                  # 스케줄러 (별도 셸)
.venv/Scripts/python -m notifier.worker                 # 알림 워커 (별도 셸)
```

### 환경변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `CRAWLER_API_URL` | `http://localhost:8000` | 스케줄러가 호출할 엔드포인트 호스트 |
| `CRAWL_INTERVAL_MINUTES` | `30` | 크롤 주기 |
| `SMTP_HOST`/`PORT` | `smtp.gmail.com`/`587` | STARTTLS 사용 |
| `SMTP_USER`/`PASSWORD` | — | Gmail은 앱 비밀번호 |
| `SMTP_FROM` | `SMTP_USER`로 폴백 | From 헤더 |
| `DEV_RECIPIENT_EMAIL` | — | `users.email` 누락 시 폴백 |
| `DAILY_LIMIT_PER_USER` | `5` | KST 자정 리셋 |
| `SLACK_SIGNING_SECRET` | `""` | Slack 슬래시 커맨드 HMAC 검증. 비면 검증 스킵 (개발용). |

### 후속 v0.5

- 마감일 자동 추출(LLM 툴) + D-7/D-1 리마인더 cron
- score 4~6 점 일일 요약 배치 (현재 `filter.py`는 score≥7만 큐 적재)
- 카카오 알림톡 채널 (Solapi) — `notifier/`에 채널 분기 추가

## 통합 인터페이스 (다른 팀원용)

- **권기혁(AI 파이프라인)** — `crawler.app.models.RawNotice`는 그대로. 추가로 `db.repository.PostgresNoticeRepository.list_pending_embeddings(limit)` / `.save_embeddings([(id, vec, model)])` 사용.
- **이주호(스케줄러+알림)** — `scheduler/main.py`가 30분마다 `service.ingestion.run_full_ingestion()` 직접 호출 (HTTP 우회 — LLM 호출 포함 수 분 소요라 타임아웃 방지). `notifier/worker.py`가 Redis 큐 BLPOP → SMTP 발송 후 `notifications.status='sent'` 업데이트. Slack 슬래시 커맨드는 `api/slack.py` ([SLACK.md](SLACK.md) 참조).
- **서성민(백엔드 API)** — DB가 SQLite → Postgres로 바뀌었다. SQLAlchemy 세션은 `db.connection.session_scope()` 컨텍스트매니저 사용.
- **양현서(크롤러)** — 크롤러 코드는 그대로. `NoticeCrawlService(repository=PostgresNoticeRepository())`로 주입만 바꿈.

## 포트 / 환경변수

| 변수 | 용도 |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy 접속 문자열. 기본은 docker-compose 동일. |
| `POSTGRES_USER/PASSWORD/DB/PORT` | docker-compose에서만 사용. |
| `OPENAI_API_KEY` | 임베딩 + LLM 판정. |
| `EMBEDDING_MODEL` | 기본 `text-embedding-3-small` (1536-d, 스키마와 일치). |
| `REDIS_HOST`, `REDIS_PORT` | 매칭 큐. docker-compose가 띄움. |
| `SECRET_KEY` | Upstage solar-pro2 API key (ai_agent). |
| `SMTP_*`, `DAILY_LIMIT_PER_USER`, `CRAWLER_API_URL`, `CRAWL_INTERVAL_MINUTES` | 이주호 모듈. |
| `SLACK_SIGNING_SECRET` | Slack 슬래시 커맨드 검증. |

## 테스트

크롤러 단위 테스트는 그대로 동작:

```bash
cd backend/crawler
.venv/bin/python tests/test_models_storage.py
.venv/bin/python tests/test_scrapers_parse.py
```

DB/임베딩 통합은 docker-compose가 떠 있는 환경에서 `python -m cli ingest`로 end-to-end 확인.
