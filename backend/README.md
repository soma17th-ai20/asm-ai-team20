# backend 프로젝트 구조

```
backend/
├── crawler                 # 양현서 님이 만들어 주신 크롤러입니다. 자세한 설명은 crawler/README.md를 참조하세요
├── service/                # 핵심 비즈니스 로직 모듈
│   ├── __init__.py
│   ├── embedding.py        # OpenAI API를 이용한 텍스트 벡터화 로직
│   ├── llm_judge.py        # 공지 적합성 정밀 판정 LLM Judge
│   └── filter.py           # DB 검색, 유사도 필터링 및 Redis 큐 삽입 로직
├── scheduler/              # (이주호) 크롤러 주기 트리거
│   └── main.py             # APScheduler → POST /api/crawl 매 N분
├── notifier/               # (이주호) 알림 발송 워커
│   ├── worker.py           # Redis notification_queue BLPOP → 이메일 발송
│   ├── mailer.py           # SMTP 송신 (stdlib smtplib)
│   └── ratelimit.py        # 유저별 일일 알림 한도 (Redis 카운터)
├── db.py                   # 공유 SQLAlchemy 세션 팩토리
├── config.py               # 환경 변수 및 설정 관리
├── prompts.py              # YAML 프롬프트 파일을 로드하는 유틸리티
├── prompts.yml             # LLM 판정에 사용되는 System/User 프롬프트 템플릿
├── .env
├── .env.example
└── requirements.txt
```

## 1. 환경 설정 (.env)

프로젝트 실행을 위해 루트 디렉토리에 .env 파일을 생성하고 아래 항목을 설정하십시오.

```
OPENAI_API_KEY=your_api_key_here
SIMILARITY_THRESHOLD=0.55
LLM_THRESHOLD=7
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 2. 데이터베이스 스키마 가이드

아래는 서비스 함수들이 참조하는 기본 스키마입니다. 테이블명이나 컬럼명이 다를 경우 service/filter.py 내의 SQL 쿼리를 수정해야 합니다 (저한테 메시지 주시면 수정하겠습니다)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- 유저 테이블
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    interest_text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 공지사항 테이블
CREATE TABLE IF NOT EXISTS notice (
    notice_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## 3. Service 함수 인터페이스

### embed_text(text: str) -> List[float]
- 위치: service/embedding.py
- 설명: OpenAI API를 사용하여 입력된 텍스트를 1536차원의 벡터로 변환합니다.
- 활용: 유저의 관심사 텍스트를 저장하거나, 공지사항을 DB에 저장하기 전에 호출하여 임베딩 값을 생성할 때 사용합니다.

### push_notice_to_redis_queue(db: Session, notice_id: int)
- 위치: service/filter.py
- 설명: 특정 공지사항에 대해 유사도가 높은 유저를 선별하고, LLM 판정을 거쳐 최종 알림 대상을 Redis 큐에 적재합니다.
- 백엔드 API에서 새로운 공지사항을 DB에 저장(INSERT)한 직후 이 함수를 실행해 주세요.

## 4. 스케줄러 + 알림 (이주호)

### 4.1 스케줄러 — 크롤러 주기 호출

`backend/scheduler/main.py`. APScheduler `BlockingScheduler`로 매 `CRAWL_INTERVAL_MINUTES`마다
`POST {CRAWLER_API_URL}/api/crawl`을 호출한다. 시작 즉시 1회 즉시 실행 후 주기 실행.

```bash
# 사전: 크롤러 API가 떠 있어야 함 (uvicorn app.main:app --port 8000)
cd backend
.venv/Scripts/python.exe -m scheduler.main
```

관련 env: `CRAWLER_API_URL`, `CRAWL_INTERVAL_MINUTES` (기본 30).

### 4.2 알림 워커 — Redis 큐 → 이메일

`backend/notifier/worker.py`. Redis 리스트 `notification_queue`에서 BLPOP으로
`{"user_id": int, "notice_id": int}` 페이로드를 읽고:
1. `users`/`notice` 테이블에서 본문 조회
2. 일일 한도(`DAILY_LIMIT_PER_USER`, 기본 5건/유저/일) 체크
3. SMTP로 이메일 발송

```bash
cd backend
.venv/Scripts/python.exe -m notifier.worker
```

관련 env: `DATABASE_URL`, `REDIS_HOST`/`REDIS_PORT`, `SMTP_*`, `DAILY_LIMIT_PER_USER`,
`DEV_RECIPIENT_EMAIL` (users 테이블에 email 컬럼 추가 전 임시 폴백).

### 4.3 통합 시 필요한 후속 작업

- **users 테이블에 `email` 컬럼 추가** (서성민 영역). 그 전까지는 `DEV_RECIPIENT_EMAIL`로
  데모용 1개 주소에만 발송.
- **Redis 큐 페이로드 확장 권장** (권기혁과 협의): 현재 `{user_id, notice_id}`만 들어가서
  이메일 본문에 LLM이 만든 `summary`/`reason`을 못 실음. `{user_id, notice_id, score, summary, reason}`로
  확장하면 메일이 풍성해짐.
- **D-7/D-1 리마인더 + 일일 요약 배치**는 v0.5에서 별도 스케줄 잡으로 추가 예정.
