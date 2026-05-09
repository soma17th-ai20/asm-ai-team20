-- 학교 공지 AI 알림 — 통합 DB 스키마
-- pgvector 확장은 docker-entrypoint 단계에서 한 번 생성되며, 일반 사용자도
-- CREATE EXTENSION 권한이 필요해서 IF NOT EXISTS로 안전하게 처리한다.
CREATE EXTENSION IF NOT EXISTS vector;

-- 1) 크롤러가 적재하는 공지 메타데이터.
--    hash 컬럼은 (source_id|url|title)의 SHA-256으로, 중복 INSERT를
--    ON CONFLICT (hash) DO NOTHING 으로 거른다.
CREATE TABLE IF NOT EXISTS notices (
    id          BIGSERIAL PRIMARY KEY,
    source_id   TEXT        NOT NULL,
    title       TEXT        NOT NULL,
    url         TEXT        NOT NULL,
    posted_at   TEXT,
    summary     TEXT,
    body        TEXT,
    hash        TEXT        NOT NULL UNIQUE,
    fetched_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notices_source     ON notices (source_id);
CREATE INDEX IF NOT EXISTS idx_notices_fetched_at ON notices (fetched_at DESC);

-- 2) 임베딩은 별도 테이블. 1:1 (notice_id가 PK이자 FK).
--    임베딩 모델 교체 시 model 컬럼만 분기하면 되고, 미임베딩 공지는
--    LEFT JOIN으로 즉시 식별 가능.
CREATE TABLE IF NOT EXISTS notice_embeddings (
    notice_id   BIGINT      PRIMARY KEY REFERENCES notices(id) ON DELETE CASCADE,
    embedding   vector(1536) NOT NULL,
    model       TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 3) 유저 — 이메일 1건 = 한 사람. 알림 수신 주체.
CREATE TABLE IF NOT EXISTS users (
    id                      SERIAL      PRIMARY KEY,
    email                   TEXT        NOT NULL UNIQUE,
    notification_frequency  TEXT        NOT NULL DEFAULT 'realtime'
                                        CHECK (notification_frequency IN ('realtime','daily','weekly')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 기존 DB에 컬럼 추가 (멱등). 새 컬럼이 이미 있으면 NOOP.
ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_frequency TEXT
    NOT NULL DEFAULT 'realtime'
    CHECK (notification_frequency IN ('realtime','daily','weekly'));

-- 4) 유저 관심사 — 한 유저가 여러 관심사를 가질 수 있다.
--    embedding은 인라인 (filter.py가 cosine으로 직접 매칭).
--    같은 유저가 같은 관심사를 두 번 보내도 멱등이 되도록 (user_id, interest_text) UNIQUE.
CREATE TABLE IF NOT EXISTS user_interests (
    id            SERIAL      PRIMARY KEY,
    user_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest_text TEXT        NOT NULL,
    embedding     vector(1536) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, interest_text)
);
CREATE INDEX IF NOT EXISTS idx_user_interests_user ON user_interests (user_id);

-- 5) 알림 로그 — filter.py가 Redis 큐에 push할 때 같이 INSERT.
--    notifier worker(이주호 영역)가 이메일 발송 후 sent_at + status 업데이트 예정.
--    한 (user, notice) 쌍은 한 번만 알림.
CREATE TABLE IF NOT EXISTS notifications (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notice_id   BIGINT      NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    queued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ,
    status      TEXT        NOT NULL DEFAULT 'queued',
    feedback    TEXT        CHECK (feedback IN ('like','dislike')),
    UNIQUE (user_id, notice_id)
);
-- 기존 DB에 feedback 컬럼 추가 (멱등).
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS feedback TEXT
    CHECK (feedback IN ('like','dislike'));
CREATE INDEX IF NOT EXISTS idx_notifications_user_queued
    ON notifications (user_id, queued_at DESC);

-- 6) Slack 연동 — slack_user_id를 우리 users.id에 1:1 매핑.
--    /notice link <email> 슬래시 커맨드로 자기 자신을 등록.
--    한 Slack 계정 ↔ 한 DB 유저 (PRIMARY KEY로 강제).
CREATE TABLE IF NOT EXISTS slack_links (
    slack_user_id  TEXT        PRIMARY KEY,
    user_id        INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    linked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_slack_links_user ON slack_links (user_id);

-- 7) ANN 인덱스. 데이터가 충분히 쌓인 뒤(>10K rows) 의미있고,
--    그 전에는 seq scan이 더 빠를 수 있어 주석 처리. 운영에서 ANALYZE 후 켠다.
-- CREATE INDEX IF NOT EXISTS idx_notice_embeddings_ann
--     ON notice_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX IF NOT EXISTS idx_user_interests_ann
--     ON user_interests USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
