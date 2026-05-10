# 학교 공지 AI 알림 서비스 — 20팀

여러 학교/채용 사이트의 공지를 자동 수집·분석해 사용자에게 꼭 필요한 공지만 골라
이메일·Slack으로 알려주는 에이전트 서비스.

```
[크롤러] 6개 사이트 → [임베딩+LLM 매칭] → [Redis 큐] → [이메일/Slack]
                              ↑                              ↑
                       (관심사 임베딩)                    (피드백 👍/👎)
                              ↑                              ↑
                       프론트엔드 (Next.js 16) ←─────────────┘
                              ↕
                          Slack 슬래시 커맨드
```

## 저장소 구성

이 저장소는 **백엔드 + 인프라**만 담는다. 프론트엔드는 별도 저장소.

| 모듈 | 위치 | 스택 | 역할 |
|---|---|---|---|
| **backend** | `backend/` | Python 3.11+ / FastAPI / SQLAlchemy | 통합 API, 크롤러 호출, 매칭, 알림 발송 |
| **crawler** | `backend/crawler/` | httpx + BeautifulSoup4 | 6개 사이트 스크래퍼 (HTTP-only) |
| **service** | `backend/service/` | OpenAI | 임베딩, LLM judge, 매칭, ETL |
| **db** | `backend/db/` | PostgreSQL + pgvector | 스키마, 리포지토리, 세션 |
| **scheduler** | `backend/scheduler/` | APScheduler | 30분 주기 풀 인제스천 트리거 |
| **notifier** | `backend/notifier/` | smtplib + Redis | Redis 큐 소비 → 이메일 발송 + 일일 한도 |
| **ai_agent** | `backend/ai_agent/` | Upstage solar-pro2 | 자연어 → 함수 호출 계획 (fallback 룰 파서) |
| **api/slack** | `backend/api/slack.py` | HMAC | `/notice` 슬래시 커맨드 처리 |
| **인프라** | `docker-compose.yml` | Postgres+pgvector / Redis | 한 방 부트스트랩 |
| 데모 (legacy) | `src/` | Vite/React | 초기 크롤러 검증용. 실 UI는 FE 저장소 사용 |

**프론트엔드**: https://github.com/soma17th-ai20/soma17th-ai20-FE (Next.js 16, 별 폴더 `soma17th-ai20-FE/`로 클론)

## 빠른 시작

### 0) 필수 환경변수

```bash
cp .env.example .env                 # OPENAI_API_KEY 채우기 (필수)
cp backend/.env.example backend/.env # SMTP_USER/PASSWORD/FROM, DEV_RECIPIENT_EMAIL,
                                     # SLACK_SIGNING_SECRET (Slack 쓸 때만)
```

`.env` (프로젝트 루트) — docker-compose가 읽음:
```
OPENAI_API_KEY=sk-...
SECRET_KEY=                          # Upstage solar-pro2 (없으면 fallback 룰)
```

`backend/.env` — 호스트의 scheduler/notifier 프로세스가 읽음:
```
OPENAI_API_KEY=sk-...                # 같은 키
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx    # Gmail 앱 비밀번호
SMTP_FROM=you@gmail.com
DEV_RECIPIENT_EMAIL=                 # users.email 누락 시 폴백 (보통 비워둠)
SLACK_SIGNING_SECRET=                # Slack 슬래시 커맨드 검증
DAILY_LIMIT_PER_USER=5               # 유저당 하루 최대 알림 (KST)
```

### 1) Docker — 인프라 + 백엔드 한 번에

```bash
docker compose up -d --build
```

세 컨테이너 (`postgres`, `redis`, `backend`) 자동 기동. 부팅 시 `backend/db/schema.sql` 자동 적용.

확인: <http://localhost:8000/api/health> · <http://localhost:8000/docs>

### 2) 호스트에서 백그라운드 워커 2개

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 셸 1 — 30분마다 크롤+임베딩+매칭+큐 적재
python -m scheduler.main

# 셸 2 — 큐 소비 → 이메일 발송
python -m notifier.worker
```

scheduler는 시작 즉시 1회 실행 후 30분 주기. notifier는 BLPOP 무한 루프.

### 3) 프론트엔드 (별도 저장소)

```bash
git clone https://github.com/soma17th-ai20/soma17th-ai20-FE
cd soma17th-ai20-FE
npm install
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
npm run dev   # http://localhost:3000
```

자세한 건 FE 저장소 README 참조.

### 4) Slack 연동 (선택)

`backend/SLACK.md` 참조. 5분 셋업으로 `/notice <키워드> 추가` 같은 슬래시 커맨드 가능.

로컬 노출은 cloudflared 권장 (회원가입 X):
```bash
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
```

## API 엔드포인트

기본 URL: `http://localhost:8000`. CORS는 `:3000` (Next.js), `:5173`/`:4173` (Vite) 허용.

### 시스템 / 크롤
| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/api/health` | 헬스체크 |
| GET | `/api/sources` | 크롤 대상 목록 |
| GET | `/api/notices` | 저장된 공지 페이지네이션 |
| POST | `/api/crawl` | 즉시 크롤 트리거 (`?source=...` 단일/생략 시 전체) |

### 사용자 / 인증
| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/api/users` | 가입 (`{email, interest_text}` → user_id, 첫 관심사 등록) |
| POST | `/api/users/login` | 이메일로 식별 (비밀번호 X, newsletter-style) |
| GET | `/api/users` | 전체 유저 + 관심사 목록 |

### 관심사 키워드
| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/api/users/{uid}/interests` | 키워드 목록 |
| POST | `/api/users/{uid}/interests` | 키워드 추가 |
| DELETE | `/api/users/{uid}/interests/{keyword}` | 키워드 삭제 |

### 알림 설정 / 피드
| 메서드 | 경로 | 용도 |
|---|---|---|
| GET · PATCH | `/api/users/{uid}/settings` | 이메일 + `notification_frequency` (realtime/daily/weekly) |
| GET | `/api/users/{uid}/notifications?hours=N` | 내가 받은 알림 (제목+url+요약+피드백 상태) |
| POST | `/api/notifications/{nid}/feedback` | 👍/👎 (`{feedback: 'like'\|'dislike'\|null}`) |

### AI 에이전트 / Slack
| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/api/agent` | 자연어 프롬프트 → ai_agent 의도 해석 → 함수 dispatch |
| POST | `/api/slack/command` | Slack 슬래시 커맨드 (HMAC 서명 검증) |

상세 스펙은 <http://localhost:8000/docs> (Swagger UI).

## 데이터 모델 (PostgreSQL + pgvector)

스키마 단일 진실: `backend/db/schema.sql`. 컨테이너 첫 부팅 시 자동 적용 (멱등 `ALTER TABLE`).

| 테이블 | 키 컬럼 | 비고 |
|---|---|---|
| `notices` | `id, source_id, title, url, body, hash UNIQUE` | 크롤러 적재 — 메타+본문, `hash`로 중복 거름 |
| `notice_embeddings` | `notice_id PK FK, vector(1536), model` | 1:1 분리 (모델 교체 시 갱신) |
| `users` | `id, email UNIQUE, notification_frequency` | `realtime`/`daily`/`weekly` |
| `user_interests` | `id, user_id FK, interest_text, vector(1536)`, UNIQUE`(user_id, interest_text)` | 한 유저 N개 관심사 |
| `notifications` | `id, user_id, notice_id`, UNIQUE`(user_id, notice_id)`, `status, sent_at, feedback` | 발송 이력 + 👍/👎 |
| `slack_links` | `slack_user_id PK, user_id FK` | Slack 계정 ↔ DB 유저 매핑 |

## 등록된 사이트 (`backend/crawler/config/sites.json`)

| id | URL | 비고 |
|---|---|---|
| `snu_cse_notice` | https://cse.snu.ac.kr/community/notice | HTML 테이블 |
| `snu_cba_notice` | https://cba.snu.ac.kr/newsroom/notice?sc=y | HTML 리스트 |
| `saramin_hot100` | https://www.saramin.co.kr/zf_user/jobs/hot100 | HTML |
| `naver_recruit` | https://recruit.navercorp.com/rcrt/list.do | AJAX JSON 직접 호출 |
| `jobkorea_ai` | https://www.jobkorea.co.kr/recruit/ai-jobs | AJAX JSON+embedded HTML |
| `naver_cafe_notice` | https://cafe.naver.com/f-e/cafes/31723403/menus/2 | 공식 SPA의 공개 ArticleList AJAX |

사이트 추가는 `sites.json`에 한 줄 + `backend/crawler/app/scrapers/<id>.py` 한 개 +
`backend/crawler/app/scrapers/__init__.py` 레지스트리에 한 줄.

## 풀 자동 사이클 (현재 상태)

```
[scheduler.main] 매 30분
       ↓
service.ingestion.run_full_ingestion()
       ├─ crawl_all      (6개 사이트)
       ├─ embed_pending  (OpenAI 배치 임베딩)
       └─ ★ for each new notice_id:
              service.filter.push_notice_to_redis_queue
                ├─ user_interests cosine ≥ 0.40 후보 추출
                ├─ service.llm_judge.judge() (gpt-4o, score ≥ 7)
                ├─ notifications INSERT (status='queued')
                └─ Redis rpush "notification_queue"

[notifier.worker] BLPOP 무한루프
       ↓
{user_id, notice_id} 꺼내서:
  ├─ DB lookup (users.email + notices.title/body/url)
  ├─ ratelimit (Redis INCR, 일일 N건 제한, KST 자정 리셋)
  ├─ smtplib STARTTLS 발송 (Message-ID/List-Unsubscribe 등 RFC 표준 헤더)
  └─ notifications UPDATE status='sent' / 'failed'

[프론트엔드] /feed
       ↓
GET /api/users/{uid}/notifications → 카드 렌더 + 👍/👎 버튼
```

## CLI

```bash
# 컨테이너 안에서
docker compose exec backend python -m cli init        # 스키마 생성
docker compose exec backend python -m cli crawl       # 크롤만
docker compose exec backend python -m cli embed       # 미임베딩 공지 임베딩만
docker compose exec backend python -m cli ingest      # 풀 파이프라인
docker compose exec backend python -m cli rematch     # 기존 notices 전체를 재매칭 → 큐
                                                       # (새 사용자 가입 직후 시범용)
```

`rematch`는 `--threshold 0.30`, `--limit 50` 옵션으로 튜닝 가능.

## 디렉토리

```
.
├── docker-compose.yml             # postgres + redis + backend
├── README.md                      # ← 본 파일
├── .env.example                   # 루트 .env 템플릿 (docker-compose용)
├── backend/
│   ├── Dockerfile
│   ├── README.md                  # 백엔드 상세
│   ├── SLACK.md                   # Slack 슬래시 커맨드 셋업 가이드
│   ├── main.py · cli.py
│   ├── config.py · prompts.{py,yml}
│   ├── crawler/                   # 양현서 — 6개 사이트
│   ├── service/                   # 권기혁 — embedding/llm_judge/filter/ingestion
│   ├── db/                        # 서성민 — schema.sql, repos, sessions
│   ├── api/                       # users/agent/notifications/slack 라우터
│   ├── ai_agent/                  # 권기혁 — Upstage solar-pro2 의도 해석
│   ├── scheduler/                 # 이주호 — APScheduler 30분 트리거
│   ├── notifier/                  # 이주호 — Redis BLPOP → SMTP
│   └── tests/
├── src/                           # legacy Vite/React 데모 (실 UI는 FE 저장소)
└── docs/                          # 기획서 등
```

## 테스트

```bash
cd backend/crawler
.venv/bin/python tests/test_models_storage.py
.venv/bin/python tests/test_scrapers_parse.py
```

DB/임베딩 통합 테스트는 docker compose 인프라 떠 있는 상태에서 `python -m cli ingest`로 e2e.

## 팀 분담 (기획서 §6)

| 담당 | 역할 | 이 저장소에서 |
|---|---|---|
| 양현서 | 스크래퍼 | `backend/crawler/` |
| 김승원 | 프론트엔드 | 별도 저장소 `soma17th-ai20-FE` |
| 서성민 | 백엔드/DB | `backend/db/`, `backend/service/ingestion.py`, `backend/api/` |
| 권기혁 | AI 파이프라인 | `backend/service/{embedding,llm_judge,filter}.py` + `backend/ai_agent/` |
| 이주호 | 스케줄러+알림 | `backend/scheduler/`, `backend/notifier/`, `backend/api/slack.py` |
| 박현병 | 코치 | — |
