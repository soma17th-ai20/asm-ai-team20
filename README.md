# 학교 공지 AI 알림 서비스 — 20팀

여러 학교/채용 사이트의 공지를 자동 수집·분석해 사용자에게 꼭 필요한 공지만 골라 알려주는 에이전트 서비스. 본 저장소는 그중 **스크래퍼 모듈**이 1차로 구현되어 있다.

## 구성

| 모듈                | 위치               | 스택                                | 역할                                                  |
| ------------------- | ------------------ | ----------------------------------- | ----------------------------------------------------- |
| **backend**         | `backend/`         | Python 3.10+ / FastAPI / SQLAlchemy | 크롤러 + 임베딩 + LLM 판정 + DB(PostgreSQL+pgvector)  |
| **crawler**         | `backend/crawler/` | Python                              | 6개 사이트 크롤링·중복 제거 (backend가 내부 호출)      |
| **frontend (demo)** | `src/`             | React 19 / Vite 8                   | 크롤러 동작 검증용 최소 UI (실 서비스 UI는 별도 담당) |
| **인프라**          | `docker-compose.yml` | PostgreSQL+pgvector / Redis       | 로컬 개발용 한 방 부트스트랩                           |

프론트와 백엔드는 **완전히 분리**되어 있고, 통신은 `/api/*` REST로만 한다. 다른 팀원의 백엔드/AI/스케줄러는 이 API에 그대로 붙는다.

## 현재 구현 상태

- `backend/crawler/`는 MVP 수집 레이어까지 구현되어 있다. 등록된 6개 사이트를 크롤링하고, FastAPI 어댑터로 조회/실행할 수 있다.
- `backend/db/`에 PostgreSQL+pgvector 스키마와 `PostgresNoticeRepository`가 있어, 크롤러는 이 리포지토리를 통해 Postgres에 적재한다.
- `backend/service/`에 임베딩(OpenAI)·LLM 판정·Redis 매칭 코드가 있다. `service/ingestion.py`가 *크롤 → 임베딩 → 저장* 파이프라인을 한 번에 돌린다.
- `src/`는 실서비스 UI가 아니라 크롤러 동작 확인용 데모 화면이다.
- 알림 발송과 스케줄러 연동은 다른 팀원이 이 백엔드의 함수를 import해서 붙이도록 설계되어 있다.

## 빠른 시작

### 1) DB·Redis (한 방 부트스트랩)

```bash
cp backend/.env.example backend/.env   # OPENAI_API_KEY 채우기
docker compose up -d                   # postgres(5432, pgvector) + redis(6379)
```

스키마는 컨테이너 시작 시 `backend/db/schema.sql`이 자동으로 적용된다.

### 2) 백엔드 (Python)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m cli init      # 스키마(멱등 재적용) 확인
python -m cli ingest    # 6개 사이트 크롤 → 신규 공지 임베딩 → Postgres 저장
```

크롤러 단독 FastAPI는 `uvicorn crawler.app.main:app --reload --port 8000`.

확인: <http://localhost:8000/api/health> → `{"status":"ok"}`
Swagger UI: <http://localhost:8000/docs>

### 3) 프론트 (데모)

```bash
npm install
npm run dev
```

브라우저: <http://localhost:5173>
백엔드 주소를 바꾸려면 `VITE_CRAWLER_API` 환경변수.

## API

기본 URL: `http://localhost:8000`. CORS는 Vite dev/preview 포트(`5173`, `4173`)에 한해 열려 있다.

### `GET /api/health`

헬스체크.

```json
{ "status": "ok" }
```

### `GET /api/sources`

등록된 크롤 대상 목록. `config/sites.json`을 그대로 노출.

```json
[
  {
    "id": "snu_cse_notice",
    "name": "서울대 컴퓨터공학부 공지",
    "url": "https://cse.snu.ac.kr/community/notice",
    "category": "school",
    "enabled": true
  }
]
```

### `GET /api/notices`

저장된 공지 페이지네이션 조회.

| 쿼리 파라미터 | 타입        | 기본값 | 설명                            |
| ------------- | ----------- | ------ | ------------------------------- |
| `source`      | string      | `null` | `source_id` 필터 (생략 시 전체) |
| `limit`       | int (1–200) | `50`   | 페이지 크기                     |
| `offset`      | int (≥0)    | `0`    | 오프셋                          |

응답:

```json
{
  "total": 120,
  "items": [
    {
      "id": 42,
      "source_id": "naver_recruit",
      "title": "[NAVER] AI 엔지니어 (체험형 인턴)",
      "url": "https://recruit.navercorp.com/rcrt/view.do?annoId=30001234&lang=ko",
      "posted_at": "2026.04.29 10:00:00",
      "summary": "신입 · 수시 · 채용진행중",
      "body": null,
      "hash": "9a3c…",
      "fetched_at": "2026-05-08T12:34:56+00:00"
    }
  ]
}
```

### `POST /api/crawl`

즉시 크롤 트리거. `source` 쿼리로 단일 사이트만 돌릴 수 있고, 생략 시 전체.
스케줄러(이주호)는 이 엔드포인트를 cron/Celery Beat로 호출하면 된다.

| 쿼리 파라미터 | 타입    | 설명                               |
| ------------- | ------- | ---------------------------------- |
| `source`      | string? | 단일 사이트 크롤 (잘못된 id면 404) |

응답:

```json
{
  "reports": [
    {
      "source_id": "snu_cse_notice",
      "fetched": 40,
      "inserted": 5,
      "duplicates": 35,
      "errors": [],
      "started_at": "2026-05-08T12:34:50+00:00",
      "finished_at": "2026-05-08T12:34:53+00:00"
    }
  ]
}
```

`fetched`는 파서가 잡아낸 건수, `inserted`는 신규 저장 건수, `duplicates`는 hash 충돌로 거른 건수. `errors`가 비어있지 않으면 사이트 구조 변경 또는 봇 차단 의심.

## 등록된 사이트 (`backend/crawler/config/sites.json`)

| id               | URL                                                              | 비고                                       |
| ---------------- | ---------------------------------------------------------------- | ------------------------------------------ |
| `snu_cse_notice` | https://cse.snu.ac.kr/community/notice                           | HTML 테이블                                |
| `snu_cba_notice` | https://cba.snu.ac.kr/newsroom/notice?sc=y                       | HTML 리스트                                |
| `saramin_hot100` | https://www.saramin.co.kr/zf_user/jobs/hot100                    | HTML                                       |
| `naver_recruit`  | https://recruit.navercorp.com/rcrt/list.do                       | AJAX JSON 직접 호출 (`loadJobList.do`)     |
| `jobkorea_ai`    | https://www.jobkorea.co.kr/recruit/ai-jobs?pageNo=1&pageSize=100 | AJAX JSON+embedded HTML (`GetRecruitList`) |
| `naver_cafe_notice` | https://cafe.naver.com/f-e/cafes/31723403/menus/2             | 공식 SPA의 공개 ArticleList AJAX (`apis.naver.com`) |

사이트 추가는 `sites.json`에 한 줄 + `backend/crawler/app/scrapers/<id>.py` 한 개 + `backend/crawler/app/scrapers/__init__.py` 레지스트리에 한 줄.

## 데이터 모델 (PostgreSQL + pgvector)

스키마 단일 진실: `backend/db/schema.sql`. 컨테이너 첫 부팅 시 자동 적용.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- 크롤러 적재 — 메타데이터 only
notices(
  id          BIGSERIAL PK,
  source_id   TEXT,
  title       TEXT,
  url         TEXT,
  posted_at   TEXT?,
  summary     TEXT?,
  body        TEXT?,
  hash        TEXT UNIQUE,        -- SHA-256(source_id | url | title)
  fetched_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ
)

-- 임베딩은 분리 테이블 (1:1). 모델 교체/재임베딩이 깔끔.
notice_embeddings(
  notice_id   BIGINT PK FK→notices.id ON DELETE CASCADE,
  embedding   vector(1536),
  model       TEXT,
  created_at  TIMESTAMPTZ
)

-- 유저 — 이메일 1건 = 한 사람
users(
  id          SERIAL PK,
  email       TEXT UNIQUE,
  created_at  TIMESTAMPTZ
)

-- 유저 관심사 — 한 유저가 여러 관심사 가질 수 있음. embedding 인라인.
user_interests(
  id            SERIAL PK,
  user_id       INT FK→users.id ON DELETE CASCADE,
  interest_text TEXT,
  embedding     vector(1536),
  created_at    TIMESTAMPTZ,
  UNIQUE (user_id, interest_text)
)
```

프론트엔드는 `POST /api/users` 로 `{email, interest_text}`를 보내면 백엔드가 임베딩 후 위 두 테이블에 적재한다.

크롤러는 `backend/db/repository.PostgresNoticeRepository`를 통해 적재한다. SQLite 구현체(`backend/crawler/app/storage.py`)는 단위 테스트용으로 유지.

## 디렉토리

```
.
├── docker-compose.yml             # postgres(pgvector) + redis
├── backend/
│   ├── crawler/                   # 크롤러 모듈 (feat/crawler에서 이관)
│   │   ├── config/sites.json
│   │   ├── app/                   # main · api · service · scrapers …
│   │   └── tests/
│   ├── db/
│   │   ├── schema.sql             # PostgreSQL + pgvector 스키마
│   │   ├── connection.py          # SQLAlchemy 엔진/세션
│   │   ├── repository.py          # PostgresNoticeRepository
│   │   └── users_repository.py    # UserRepository (email + interest 등록)
│   ├── service/
│   │   ├── embedding.py           # OpenAI 임베딩
│   │   ├── llm_judge.py           # GPT-4o 판정
│   │   ├── filter.py              # 유저 매칭 + Redis 큐 적재
│   │   └── ingestion.py           # 크롤 → 임베딩 → 저장 파이프라인
│   ├── api/
│   │   └── users.py               # POST/GET /api/users 라우터
│   ├── main.py                    # uvicorn main:app — 통합 FastAPI 엔트리
│   ├── cli.py                     # python -m cli {init|crawl|embed|ingest}
│   ├── config.py · prompts.{py,yml}
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md                  # 백엔드 상세 + 통합 가이드
├── src/                           # 프론트 — React 데모
└── docs/프로젝트기획서_20팀_학교공지AI알림서비스.md
```

## 테스트

```bash
cd backend/crawler
.venv/bin/python tests/test_models_storage.py     # storage·dedup
.venv/bin/python tests/test_scrapers_parse.py     # 6개 파서 + URL 가드
```

## 팀 분담 (기획서 §6)

| 담당   | 역할          | 이 저장소에서                                                   |
| ------ | ------------- | --------------------------------------------------------------- |
| 양현서 | 스크래퍼      | `backend/crawler/`                                              |
| 김승원 | 프론트엔드    | 추후 `src/`에 실 UI 구현 (현재는 데모만)                        |
| 서성민 | 백엔드/DB     | **`backend/db/`, `backend/service/ingestion.py`** ← 본 작업     |
| 권기혁 | AI 파이프라인 | `backend/service/embedding.py · llm_judge.py · filter.py`       |
| 이주호 | 스케줄러+알림 | Celery Beat에서 `service.ingestion.run_full_ingestion` 30분 주기 |
| 박현병 | 코치          | —                                                               |

자세한 통합 포인트는 `backend/README.md` 참조.
