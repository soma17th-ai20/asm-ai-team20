# crawler — 학교/채용 공지 스크래퍼 모듈

> 양현서 담당. 다른 팀원의 백엔드/AI 파이프라인에 **내부 서비스 인터페이스**로 붙는 크롤러 모듈.
> 프론트엔드 연동용 FastAPI는 `app.service`를 감싸는 얇은 어댑터다.

## 책임 범위

| 항목               | 구현 위치                                                          |
| ------------------ | ------------------------------------------------------------------ |
| 사이트 URL 관리    | `config/sites.json`                                                |
| 사이트별 파서      | `app/scrapers/<site>.py`                                           |
| 중복 제거          | `app/storage.py` (SHA-256(source_id+url+title) UNIQUE)             |
| 내부 인터페이스    | `app/service.py`                                                   |
| DB 저장            | SQLite — `data/notices.db` (Postgres 전환 시 저장소 클래스만 교체) |
| 프론트 연동 어댑터 | FastAPI — `app/main.py`, `app/api.py`                              |

## 디렉토리 구조

```
crawler/
├── config/
│   └── sites.json              # 크롤 대상 사이트 정의 (단일 진실)
├── app/
│   ├── main.py                 # FastAPI 엔트리
│   ├── api.py                  # /api/* 라우터
│   ├── config.py               # sites.json 로더
│   ├── models.py               # RawNotice / StoredNotice / CrawlReport
│   ├── service.py              # 통합용 내부 서비스
│   ├── storage.py              # SQLite 저장소 구현체
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

| id                  | URL                                                              |
| ------------------- | ---------------------------------------------------------------- |
| `snu_cse_notice`    | https://cse.snu.ac.kr/community/notice                           |
| `snu_cba_notice`    | https://cba.snu.ac.kr/newsroom/notice?sc=y                       |
| `saramin_hot100`    | https://www.saramin.co.kr/zf_user/jobs/hot100                    |
| `naver_recruit`     | https://recruit.navercorp.com/rcrt/list.do                       |
| `jobkorea_ai`       | https://www.jobkorea.co.kr/recruit/ai-jobs?pageNo=1&pageSize=100 |
| `naver_cafe_notice` | https://cafe.naver.com/f-e/cafes/31723403/menus/2                |

## 셋업

```bash
cd crawler
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 사용법

### API 서버

```bash
uvicorn app.main:app --reload --port 8000
```

엔드포인트:

| Method | Path                                         | 설명                            |
| ------ | -------------------------------------------- | ------------------------------- |
| `GET`  | `/api/health`                                | 헬스체크                        |
| `GET`  | `/api/sources`                               | 등록 사이트 목록                |
| `GET`  | `/api/notices?source=<id>&limit=50&offset=0` | 저장된 공지 조회                |
| `POST` | `/api/crawl?source=<id>`                     | 즉시 크롤 트리거 (생략 시 전체) |

OpenAPI 스펙: `http://localhost:8000/docs`

### 내부 서비스 직접 사용

```python
from app.service import build_service

service = build_service()
reports = service.crawl_all()
items = service.list_notices(source_id="snu_cse_notice", limit=20)
```

## 내부 인터페이스 설명

통합 기준 진입점은 `app.service.NoticeCrawlService`다. 다른 파일을 먼저 볼 필요 없이, 서버 쪽에서는 이 서비스 객체만 만들어 호출하면 된다.

자주 쓰는 메서드:

- `list_sources(enabled_only=False)` — 등록된 사이트 목록 조회
- `preview_site(source_id, limit=10)` — 저장 없이 파싱 결과 미리보기
- `crawl_site(source_id)` — 한 사이트 크롤링 후 저장
- `crawl_all(source_id=None)` — 전체 또는 특정 사이트 크롤링 후 저장
- `list_notices(source_id=None, limit=50, offset=0)` — 저장된 공지 조회
- `count_notices(source_id=None)` — 저장된 공지 개수 조회
- `delete_all_notices()` — 현재 저장된 공지 전체 삭제

메서드 반환 타입:

- 크롤링 실행 결과: `CrawlReport`
- 크롤링 원본 아이템: `RawNotice`
- DB 저장/조회 아이템: `StoredNotice`

서비스 내부 흐름:

1. `service.py`가 사이트 설정을 읽는다.
2. 해당 스크래퍼가 `RawNotice` 리스트를 만든다.
3. 저장소 구현체가 이를 DB에 저장한다.
4. 최종적으로 `CrawlReport`를 반환한다.

즉 통합 서버는 스크래퍼 파일이나 SQLite 함수들을 직접 호출하지 말고, `NoticeCrawlService`만 호출하는 쪽으로 맞추는 것이 기준이다.

### 통합 예시 1: 기본 SQLite 그대로 사용

```python
from app.service import build_service

service = build_service()

report = service.crawl_site("snu_cse_notice")
rows = service.list_notices(source_id="snu_cse_notice", limit=20)
```

### 통합 예시 2: 기존 서버 DB로 교체

`NoticeCrawlService`는 저장소 객체에 다음 메서드가 있으면 그대로 동작한다.

- `insert_many(notices)`
- `list_notices(source_id=None, limit=50, offset=0)`
- `count(source_id=None)`
- `delete_all()`

예시:

```python
from app.service import NoticeCrawlService
from app.config import load_config


class MyNoticeRepository:
    def insert_many(self, notices):
        ...

    def list_notices(self, source_id=None, limit=50, offset=0):
        ...

    def count(self, source_id=None):
        ...

    def delete_all(self):
        ...


service = NoticeCrawlService(
    config=load_config(),
    repository=MyNoticeRepository(),
)
```

이렇게 두면 크롤링 로직은 그대로 두고, 저장만 기존 백엔드의 ORM/DB 계층으로 바꿀 수 있다.

## 다른 팀원과의 통합 포인트

- **서성민(백엔드 API)** — `app.service.build_service()` 또는 `NoticeCrawlService`를 직접 import해서 기존 서버 라우트 안에서 호출하면 된다. 데이터 모델(`RawNotice`/`StoredNotice`)은 Pydantic이라 그대로 import 가능하다.
- **권기혁(AI 파이프라인)** — `RawNotice` 단위로 임베딩 파이프라인에 흘리면 된다. 새 공지 알림이 필요하면 `storage.insert_many` 호출 전후를 hook으로 바꾸거나, `POST /api/crawl` 응답의 `inserted` 카운트를 활용.
- **이주호(스케줄러)** — Celery Beat나 배치에서 `NoticeCrawlService.crawl_all()`을 직접 호출하면 된다.

학교 공지 계열 스크래퍼(`snu_cse_notice`, `snu_cba_notice`)는 상세 페이지 본문까지 `body` 필드로 저장한다. 채용/외부 플랫폼 계열은 현재 목록 메타데이터 중심이다.

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
python tests/test_service.py
```
