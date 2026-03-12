CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(32) PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_in_group_id BIGINT,
    joined_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_telegram_user_id ON users (telegram_user_id);

CREATE TABLE IF NOT EXISTS daily_digests (
    id VARCHAR(32) PRIMARY KEY,
    work_date DATE NOT NULL,
    period VARCHAR(10) NOT NULL,
    group_chat_id BIGINT NOT NULL,
    message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_digest_date_period UNIQUE (work_date, period)
);

CREATE INDEX IF NOT EXISTS ix_daily_digests_work_date ON daily_digests (work_date);

CREATE TABLE IF NOT EXISTS daily_submissions (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_date DATE NOT NULL,
    hashtag VARCHAR(50) NOT NULL,
    am_submitted_at TIMESTAMPTZ,
    pm_submitted_at TIMESTAMPTZ,
    final_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_submission_user_date UNIQUE (user_id, work_date)
);

CREATE INDEX IF NOT EXISTS ix_daily_submissions_user_id ON daily_submissions (user_id);
CREATE INDEX IF NOT EXISTS ix_daily_submissions_work_date ON daily_submissions (work_date);

CREATE TABLE IF NOT EXISTS submission_items (
    id VARCHAR(32) PRIMARY KEY,
    submission_id VARCHAR(32) NOT NULL REFERENCES daily_submissions(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    task_name VARCHAR(500) NOT NULL,
    subtask_name VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_submission_items_submission_id ON submission_items (submission_id);

CREATE TABLE IF NOT EXISTS submission_item_statuses (
    id VARCHAR(32) PRIMARY KEY,
    submission_item_id VARCHAR(32) NOT NULL REFERENCES submission_items(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_item_status_item UNIQUE (submission_item_id)
);

CREATE INDEX IF NOT EXISTS ix_submission_item_statuses_submission_item_id ON submission_item_statuses (submission_item_id);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id VARCHAR(32) PRIMARY KEY,
    admin_telegram_user_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL,
    payload TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_admin_telegram_user_id ON admin_audit_logs (admin_telegram_user_id);
