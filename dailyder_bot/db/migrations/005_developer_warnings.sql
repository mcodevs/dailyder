CREATE TABLE IF NOT EXISTS developer_warnings (
    id VARCHAR(32) PRIMARY KEY,
    developer_user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    admin_telegram_user_id BIGINT NOT NULL,
    group_chat_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_developer_warnings_developer_user_id
    ON developer_warnings (developer_user_id);

CREATE INDEX IF NOT EXISTS ix_developer_warnings_admin_telegram_user_id
    ON developer_warnings (admin_telegram_user_id);

CREATE INDEX IF NOT EXISTS ix_developer_warnings_created_at
    ON developer_warnings (created_at);
