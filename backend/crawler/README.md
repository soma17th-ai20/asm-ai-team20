# crawler — 학교/채용 공지 스크래퍼 모듈

> 양현서 담당. 다른 팀원의 백엔드/AI 파이프라인에 **REST API**로 그대로 붙는 독립 모듈.
> 프론트엔드와 **완전히 분리**되어 있으며, 입출력 계약은 `/api/*` 엔드포인트로 고정한다.

## 책임 범위

| 항목 | 구현 위치 |
| --- | --- |
| 사이트 URL 관리 | `config/sites.json` |
| 사이트별 파서 | `app/scrapers/<site>.py` |
| 중복 제거 | `app/storage.py` (SHA-256(source_id+url+title) UNIQUE) |
| DB 저장 | SQLite — `data/notices.db` (Postgres 전환 시 `storage.py`만 교체) |
| 외부 노출 | FastAPI — `app/main.py`, `app/api.py` |

## 디렉토리 구조

```
crawler/
├── config/
│   └── sites.json              # 크롤 대상 사이트 정의 (단일 진실)
├── app/
│   ├── main.py                 # FastAPI 엔트리
│   ├── api.py                  # /api/* 라우터
│   ├── runner.py               # CLI: crawl / dry-run / list-sites
│   ├── config.py               # sites.json 로더
│   ├── models.py               # RawNotice / StoredNotice / CrawlReport
│   ├── storage.py              # SQLite + 중복 제거
│   ├── fetcher.py              # httpx 클라이언트
│   └── scrapers/
│       ├── base.py             # ScrapeContext, helpers
│       ├── snu_cse_notice.py
│       ├── snu_cba_notice.py
│       ├── saramin_hot100.py
│       ├── naver_recruit.py
│       └── jobkorea_ai.py
├── data/                       # SQLite 파일 (gitignore)
└── tests/
```

## 등록된 사이트

`config/sites.json` 한 곳에서 관리한다. 사이트 추가는 JSON에 한 줄 + 스크래퍼 모듈 한 개 추가로 끝.

| id | URL |
| --- | --- |
| `snu_cse_notice` | https://cse.snu.ac.kr/community/notice |
| `snu_cba_notice` | https://cba.snu.ac.kr/newsroom/notice?sc=y |
| `saramin_hot100` | https://www.saramin.co.kr/zf_user/jobs/hot100 |
| `naver_recruit` | https://recruit.navercorp.com/rcrt/list.do |
| `jobkorea_ai` | https://www.jobkorea.co.kr/recruit/ai-jobs?pageNo=1&pageSize=100 |

## 셋업

```bash
cd crawler
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 사용법

### 1) CLI

```bash
# 등록된 사이트 목록
python -m app.runner list-sites

# 한 사이트만 dry-run (DB 저장 없이 파싱 결과만 출력)
python -m app.runner dry-run --source snu_cse_notice --limit 5

# 전체 크롤 + DB 저장
python -m app.runner crawl

# 특정 사이트만 크롤
python -m app.runner crawl --source saramin_hot100
```

### 2) API 서버

```bash
uvicorn app.main:app --reload --port 8000
```

엔드포인트:

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/api/health` | 헬스체크 |
| `GET` | `/api/sources` | 등록 사이트 목록 |
| `GET` | `/api/notices?source=<id>&limit=50&offset=0` | 저장된 공지 조회 |
| `POST` | `/api/crawl?source=<id>` | 즉시 크롤 트리거 (생략 시 전체) |

OpenAPI 스펙: `http://localhost:8000/docs`

## 다른 팀원과의 통합 포인트

- **서성민(백엔드 API)** — `/api/notices`를 그대로 호출하거나, `storage.py`의 `notices` 테이블을 PostgreSQL로 마이그레이션 후 공유 DB로 합치면 된다. 데이터 모델(`RawNotice`/`StoredNotice`)은 Pydantic이라 그대로 import 가능.
- **권기혁(AI 파이프라인)** — `RawNotice` 단위로 임베딩 파이프라인에 흘리면 된다. 새 공지 알림이 필요하면 `storage.insert_many` 호출 전후를 hook으로 바꾸거나, `POST /api/crawl` 응답의 `inserted` 카운트를 활용.
- **이주호(스케줄러)** — Celery Beat에서 30분 주기로 `POST /api/crawl`을 치거나, `app.runner.crawl_all`을 직접 import해 task로 등록하면 된다.

## 중복 제거 정책

`hash = SHA-256(source_id | url | title)` 기준으로 `notices.hash` UNIQUE 제약. 제목이 같아도 URL이 다르면 별건. 사이트가 URL에 세션/추적 파라미터를 붙이는 경우 `app/scrapers/<site>.py`에서 정규화 후 반환할 것.

## 제약/주의

- `naver_recruit`은 SPA로, HTTP-only 폴백 파서가 들어있다. 결과가 0건이면 playwright를 추가 설치해 `render: "playwright"` 분기를 별도 워커로 구현. (현재는 `errors`에 안내 메시지를 남긴다.)
- 사이트 구조 변경에 대비해 모든 셀렉터에 generic 폴백을 두었지만, 셀렉터 깨짐 → 0건은 정상 흐름이므로 모니터링이 필요하다. (스케줄러 측에서 `inserted == 0 && fetched == 0`이 N회 연속이면 슬랙 알림 — 기획서 4장 제약사항 참조.)
- 요청 간격 5초, robots.txt 정책 준수 — `config/sites.json`의 `defaults.request_delay_seconds`로 조정.

## 테스트

```bash
cd crawler
python tests/test_models_storage.py
python tests/test_scrapers_parse.py
```
