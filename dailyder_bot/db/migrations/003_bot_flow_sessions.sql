CREATE TABLE IF NOT EXISTS bot_flow_sessions (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flow VARCHAR(50) NOT NULL,
    work_date DATE NOT NULL,
    step VARCHAR(100) NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    last_message_id BIGINT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_bot_flow_session UNIQUE (user_id, flow, work_date)
);

CREATE INDEX IF NOT EXISTS ix_bot_flow_sessions_user_id ON bot_flow_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_bot_flow_sessions_expires_at ON bot_flow_sessions (expires_at);
