# 학교 공지 AI 알림 서비스 — 20팀

여러 학교/채용 사이트의 공지를 자동 수집·분석해 사용자에게 꼭 필요한 공지만 골라 알려주는 에이전트 서비스. 본 저장소는 그중 **스크래퍼 모듈**이 1차로 구현되어 있다.

## 구성

| 모듈                | 위치       | 스택                   | 역할                                                  |
| ------------------- | ---------- | ---------------------- | ----------------------------------------------------- |
| **crawler**         | `crawler/` | Python 3.10+ / FastAPI | 5개 사이트 크롤링·중복 제거·DB 저장·REST API          |
| **frontend (demo)** | `src/`     | React 19 / Vite 8      | 크롤러 동작 검증용 최소 UI (실 서비스 UI는 별도 담당) |

프론트와 크롤러는 **완전히 분리**되어 있고, 통신은 `/api/*` REST로만 한다. 다른 팀원의 백엔드/AI/스케줄러는 이 API에 그대로 붙는다.

## 빠른 시작

### 1) 백엔드 (크롤러 API)

```bash
cd crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

확인: <http://localhost:8000/api/health> → `{"status":"ok"}`
Swagger UI: <http://localhost:8000/docs>

### 2) 프론트 (데모)

```bash
npm install
npm run dev
```

브라우저: <http://localhost:5173>
백엔드 주소를 바꾸려면 `VITE_CRAWLER_API` 환경변수.

### 3) CLI로만 크롤할 때 (서버 없이)

```bash
cd crawler
.venv/bin/python -m app.runner list-sites
.venv/bin/python -m app.runner dry-run --source naver_recruit --limit 5   # DB 저장 X
.venv/bin/python -m app.runner crawl                                       # 전체 + DB 저장
.venv/bin/python -m app.runner crawl --source jobkorea_ai
```

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

## 등록된 사이트 (`crawler/config/sites.json`)

| id               | URL                                                              | 비고                                       |
| ---------------- | ---------------------------------------------------------------- | ------------------------------------------ |
| `snu_cse_notice` | https://cse.snu.ac.kr/community/notice                           | HTML 테이블                                |
| `snu_cba_notice` | https://cba.snu.ac.kr/newsroom/notice?sc=y                       | HTML 리스트                                |
| `saramin_hot100` | https://www.saramin.co.kr/zf_user/jobs/hot100                    | HTML                                       |
| `naver_recruit`  | https://recruit.navercorp.com/rcrt/list.do                       | AJAX JSON 직접 호출 (`loadJobList.do`)     |
| `jobkorea_ai`    | https://www.jobkorea.co.kr/recruit/ai-jobs?pageNo=1&pageSize=100 | AJAX JSON+embedded HTML (`GetRecruitList`) |

사이트 추가는 `sites.json`에 한 줄 + `crawler/app/scrapers/<id>.py` 한 개 + `crawler/app/scrapers/__init__.py` 레지스트리에 한 줄.

## 데이터 모델

```
notices(
  id          INTEGER PK,
  source_id   TEXT,
  title       TEXT,
  url         TEXT,
  posted_at   TEXT?,
  summary     TEXT?,
  hash        TEXT UNIQUE,    -- SHA-256(source_id | url | title)
  fetched_at  TEXT
)
```

기본 SQLite (`crawler/data/notices.db`). Postgres+pgvector로 옮길 때는 `crawler/app/storage.py`만 교체하면 된다.

## 디렉토리

```
.
├── crawler/                       # 백엔드 — Python/FastAPI
│   ├── config/sites.json          # 크롤 대상 단일 진실
│   ├── app/
│   │   ├── main.py · api.py       # FastAPI
│   │   ├── runner.py              # CLI: list-sites · dry-run · crawl
│   │   ├── config.py · models.py · storage.py · fetcher.py
│   │   └── scrapers/              # 사이트별 파서 + 공통 베이스
│   ├── tests/                     # 단위 테스트
│   ├── data/                      # SQLite (gitignore)
│   ├── requirements.txt
│   └── README.md                  # 모듈 상세 + 통합 가이드
├── src/                           # 프론트 — React 데모
└── docs/프로젝트기획서_20팀_학교공지AI알림서비스.md
```

## 테스트

```bash
cd crawler
.venv/bin/python tests/test_models_storage.py     # storage·dedup
.venv/bin/python tests/test_scrapers_parse.py     # 5개 파서 + URL 가드
```

## 팀 분담 (기획서 §6)

| 담당   | 역할          | 이 저장소에서                                    |
| ------ | ------------- | ------------------------------------------------ |
| 양현서 | 스크래퍼      | **`crawler/`** ← 본 모듈                         |
| 김승원 | 프론트엔드    | 추후 `src/`에 실 UI 구현 (현재는 데모만)         |
| 서성민 | 백엔드 API    | `/api/notices`를 호출하거나 공유 DB로 통합       |
| 권기혁 | AI 파이프라인 | `RawNotice` Pydantic 모델 import → 임베딩 입력   |
| 이주호 | 스케줄러+알림 | Celery Beat에서 `POST /api/crawl` 30분 주기 호출 |
| 박현병 | 코치          | —                                                |

자세한 통합 포인트는 `crawler/README.md` 참조.
