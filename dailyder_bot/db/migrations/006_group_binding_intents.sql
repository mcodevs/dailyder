CREATE TABLE IF NOT EXISTS group_binding_intents (
    id VARCHAR(32) PRIMARY KEY,
    token VARCHAR(64) NOT NULL UNIQUE,
    admin_telegram_user_id BIGINT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_group_binding_intents_token
    ON group_binding_intents (token);

CREATE INDEX IF NOT EXISTS ix_group_binding_intents_admin_telegram_user_id
    ON group_binding_intents (admin_telegram_user_id);
