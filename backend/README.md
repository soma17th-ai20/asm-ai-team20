# backend — DB · 임베딩 · 크롤러 통합 레이어

이 디렉토리는 세 모듈을 묶는다.

| 영역 | 위치 | 비고 |
| --- | --- | --- |
| 크롤러 | `crawler/` | feat/crawler에서 가져온 모듈 (변경 없음) |
| 임베딩 / LLM 판정 / Redis 매칭 | `service/` | feat/embedding에서 가져옴 — `filter.py`는 분리 스키마에 맞게 수정 |
| DB | `db/` | **본 브랜치에서 신규**. PostgreSQL + pgvector. |
| HTTP 라우터 | `api/`, `main.py` | **본 브랜치에서 신규**. 크롤러 라우터 + 유저 등록 라우터를 한 앱으로 묶는다. |
| AI 에이전트 | `ai_agent/` | feat/ai-agent에서 가져옴. Upstage solar-pro2로 자연어 → 함수 호출 계획 변환. `SECRET_KEY` 미설정 시 룰 기반 fallback. |

## 스키마

`backend/db/schema.sql`. 핵심 결정:

- `notices` — 크롤러 메타데이터 (`source_id`, `url`, `posted_at`, `summary`, `body`, `hash`, `fetched_at`). 중복은 `hash UNIQUE` + `ON CONFLICT DO NOTHING`.
- `notice_embeddings` — `notice_id` PK FK → `notices.id`. 1:1. 모델 교체 추적용 `model TEXT`. 미임베딩 공지는 `LEFT JOIN ... WHERE ne.notice_id IS NULL`로 즉시 식별.
- `users` — `email UNIQUE`. 알림 수신 주체.
- `user_interests` — `user_id FK`, `interest_text`, `embedding vector(1536)`. 한 유저에 여러 관심사 가능. `(user_id, interest_text)` UNIQUE로 멱등.
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

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/api/health` | 헬스체크 |
| GET | `/api/sources` | 크롤 대상 목록 |
| GET | `/api/notices` | 저장된 공지 페이지네이션 |
| POST | `/api/crawl` | 즉시 크롤 트리거 (스케줄러용) |
| **POST** | **`/api/users`** | **유저 등록 — 프론트가 보낸 `{email, interest_text}`를 임베딩해서 DB 저장** |
| GET | `/api/users` | 등록된 유저 + 관심사 목록 |

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

[크롤러]
crawler.NoticeCrawlService
   └─ PostgresNoticeRepository.insert_many()
        └─ INSERT ... ON CONFLICT (hash) DO NOTHING

service.ingestion.embed_pending()
   ├─ repo.list_pending_embeddings()   # LEFT JOIN으로 미임베딩 공지
   ├─ service.embedding.embed_texts()   # OpenAI batch
   └─ repo.save_embeddings()            # notice_embeddings UPSERT

[알림]
service.filter.push_notice_to_redis_queue(db, notice_id)
   ├─ notices ⨝ notice_embeddings 조회
   ├─ user_interests와 cosine 유사도 매칭 (DISTINCT ON user_id, 점수 최고 1건)
   ├─ service.llm_judge.judge()        # 정밀 판정
   └─ Redis "notification_queue" rpush  {user_id, notice_id}
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

지원 함수: `get_interest_keywords`, `create_interest_keyword`, `delete_interest_keyword`, `get_recent_interest_notices`. 현재는 `dispatcher`가 dummy 함수로 응답 — 실제 DB 연결은 권기혁 영역.

## 통합 인터페이스 (다른 팀원용)

- **권기혁(AI 파이프라인)** — `crawler.app.models.RawNotice`는 그대로. 추가로 `db.repository.PostgresNoticeRepository.list_pending_embeddings(limit)` / `.save_embeddings([(id, vec, model)])` 사용.
- **이주호(스케줄러)** — Celery Beat에서 30분마다 `python -m backend.cli ingest` 또는 `service.ingestion.run_full_ingestion()` 호출.
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

## 테스트

크롤러 단위 테스트는 그대로 동작:

```bash
cd backend/crawler
.venv/bin/python tests/test_models_storage.py
.venv/bin/python tests/test_scrapers_parse.py
```

DB/임베딩 통합은 docker-compose가 떠 있는 환경에서 `python -m backend.cli ingest`로 end-to-end 확인.
