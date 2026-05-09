# crawler

공지/채용 사이트 수집 모듈이다.  
통합 기준은 HTTP API가 아니라 `app.service.NoticeCrawlService`다. FastAPI는 현재 프론트 테스트용 어댑터다.

## 이 모듈이 하는 일

- 등록된 사이트를 크롤링한다.
- 공지 데이터를 `RawNotice` 형식으로 정규화한다.
- 중복 제거 후 DB에 저장한다.
- 저장된 공지를 조회한다.

## 통합 시 먼저 볼 파일

- [app/service.py](./app/service.py): 통합 기준 서비스
- [app/storage.py](./app/storage.py): 현재 SQLite 저장 구현
- [config/sites.json](./config/sites.json): 수집 대상 목록

## 통합 기준 인터페이스

백엔드/스케줄러는 `NoticeCrawlService`만 호출하면 된다.

주요 메서드:

- `list_sources(enabled_only=False)`
- `preview_site(source_id, limit=10)`
- `crawl_site(source_id)`
- `crawl_all(source_id=None)`
- `list_notices(source_id=None, limit=50, offset=0)`
- `count_notices(source_id=None)`
- `delete_all_notices()`

반환 모델:

- `RawNotice`: 크롤러가 만든 정규화 원본
- `StoredNotice`: 저장된 공지
- `CrawlReport`: 크롤 실행 결과

## 가장 흔한 사용 방식

기본 SQLite 그대로 사용할 때:

```python
from app.service import build_service

service = build_service()
report = service.crawl_all()
rows = service.list_notices(limit=20)
```

기존 서버 DB로 교체할 때:

```python
from app.config import load_config
from app.service import NoticeCrawlService


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

저장소 교체 시 필요한 메서드는 `insert_many`, `list_notices`, `count`, `delete_all` 네 개뿐이다.

## HTTP 어댑터

프론트가 붙어야 하면 현재 FastAPI를 그대로 써도 된다.

- `GET /api/health`
- `GET /api/sources`
- `GET /api/notices`
- `POST /api/crawl`

실제 통합 서버가 이미 있으면 이 API를 유지할 필요는 없고, 해당 서버 라우트에서 `NoticeCrawlService`를 직접 호출하는 편이 더 단순하다.

## 데이터 모델

현재 저장 테이블 핵심 필드:

- `source_id`
- `title`
- `url`
- `posted_at`
- `summary`
- `body`
- `hash`
- `fetched_at`

중복 기준은 `SHA-256(source_id | url | title)`이다.

## 수집 대상

현재 등록 사이트:

- `snu_cse_notice`
- `snu_cba_notice`
- `saramin_hot100`
- `naver_recruit`
- `jobkorea_ai`
- `naver_cafe_notice`

세부 URL은 [config/sites.json](./config/sites.json) 기준이다.

## 알아야 할 제약

- 학교 공지 계열은 `body` 수집이 들어가 있다.
- 외부 채용 플랫폼은 사이트 구조 변경 영향을 자주 받는다.
- `naver_cafe_notice`는 공개 구조 제약으로 다른 소스보다 불안정할 수 있다.
- 요청 간격은 `config/sites.json`의 `request_delay_seconds`로 조정한다.

## 로컬 실행

```bash
cd crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 테스트

```bash
cd crawler
python tests/test_models_storage.py
python tests/test_scrapers_parse.py
python tests/test_service.py
```
