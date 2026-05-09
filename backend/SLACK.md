# Slack 슬래시 커맨드 연동 가이드

학교공지 AI를 Slack에서 슬래시 커맨드로 호출하는 방법.

## 사용 예시

```
/notice link saturn0601@outlook.kr     # 처음 1회: Slack 계정 ↔ 가입 이메일 연결
/notice 키워드                          # 내 키워드 목록
/notice 백엔드 추가                     # 키워드 추가
/notice 백엔드 삭제                     # 키워드 삭제
/notice 알림                            # 최근 24시간 받은 알림 (제목 + 링크)
/notice 인턴 키워드 등록해줘             # 자유 자연어 (ai_agent가 의도 해석)
/notice help                            # 도움말
```

응답은 항상 `ephemeral` (본인에게만 보임).

## 백엔드 측

### 신규 컴포넌트
| 위치 | 역할 |
|---|---|
| `backend/api/slack.py` | `POST /api/slack/command` — Slack에서 보내는 슬래시 커맨드 처리 |
| `backend/db/schema.sql` (table `slack_links`) | `slack_user_id ↔ users.id` 1:1 매핑 |
| `backend/db/users_repository.py` (`link_slack`, `get_user_id_by_slack`) | 매핑 CRUD |

### 라우팅 결정 트리

```
요청 도착
  ├─ HMAC 서명 검증 (X-Slack-Signature, 5분 replay 윈도우)
  │     └─ SLACK_SIGNING_SECRET 비어있으면 검증 스킵 (개발용)
  ├─ text="" or "help" → 도움말 ephemeral
  ├─ text="link <email>" → users 조회 → slack_links upsert
  ├─ slack_user_id가 미연결 → "먼저 link 해주세요"
  ├─ 정형 패턴 (키워드 / <X> 추가 / <X> 삭제 / 알림)
  │     └─ db.agent_repo 함수 직접 호출 (LLM 우회 — 빠르고 결정론적)
  └─ 자연어 → service.agent_handler.run_for_user (ai_agent / Upstage solar-pro2)
```

### 환경변수

`backend/.env` 또는 docker-compose 환경에:

```
SLACK_SIGNING_SECRET=<Slack 앱 Basic Information의 Signing Secret>
```

비워두면 검증 스킵 (로컬 개발 + ngrok 없이 curl로 테스트 가능).

## Slack 앱 셋업 (5분)

### 1) 앱 만들기

https://api.slack.com/apps → **Create New App** → **From scratch**
- App Name: `학교공지 AI`
- 워크스페이스 선택

### 2) 슬래시 커맨드 추가

좌측 메뉴 **Slash Commands** → **Create New Command**

| 필드 | 값 |
|---|---|
| Command | `/notice` |
| Request URL | `https://<공개주소>/api/slack/command` |
| Short Description | 학교공지 AI 에이전트 |
| Usage Hint | `<키워드> 추가 / 삭제 / 알림 / link <email>` |

**Request URL은 공개 도메인이어야 함**. 로컬 개발 시:
```bash
# ngrok으로 localhost:8000 터널링
ngrok http 8000
# 출력된 https://abc123.ngrok-free.app/api/slack/command 를 Request URL에 붙여넣기
```

### 3) Signing Secret 가져오기

좌측 **Basic Information** → **App Credentials** → **Signing Secret** → **Show** → 복사

`backend/.env`의 `SLACK_SIGNING_SECRET=` 에 붙여넣기 → 백엔드 재기동 (`docker compose restart backend`).

### 4) 워크스페이스 설치

좌측 **Install App** → **Install to Workspace** → 권한 승인.

### 5) Slack에서 사용

채널이나 DM에서 슬래시 커맨드 입력:
```
/notice link your-email@example.com
/notice 키워드
```

## 보안 주의

- `SLACK_SIGNING_SECRET`을 비워두면 **누구든** `POST /api/slack/command`로 임의 사용자 행세 가능. 운영에서는 반드시 설정.
- ngrok 무료 티어는 URL이 재시작마다 바뀜 → Slack 앱의 Request URL도 매번 갱신 필요. 운영 배포 시 고정 도메인 사용.
- `slack_user_id`는 한 번 연결되면 그 워크스페이스에서 영구 식별자. 잘못된 사용자에 연결됐다면 `DELETE FROM slack_links WHERE slack_user_id = '<id>'`로 수동 해제.

## 데모용 직접 테스트 (Slack 없이)

```bash
# 도움말
curl -X POST http://localhost:8000/api/slack/command \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "user_id=U_TEST&text=help"

# 연결
curl -X POST http://localhost:8000/api/slack/command \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "user_id=U_TEST" \
  --data-urlencode "text=link saturn0601@outlook.kr"

# 키워드 조회
curl -X POST http://localhost:8000/api/slack/command \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "user_id=U_TEST" \
  --data-urlencode "text=키워드"
```

## 후속 v0.5

- Block Kit 응답으로 카드형 UI (현재는 plaintext + 마크다운만)
- Events API로 멘션 (`@학교공지AI 장학금 추가`) 지원 — 슬래시 커맨드 외에
- Interactive Components: 알림 메시지에 👍/👎 버튼 직접 박기
- DM/채널 통지: 새 알림이 매칭될 때 Slack DM으로도 발송 (notifier에 `slack_dm` 채널 추가)
