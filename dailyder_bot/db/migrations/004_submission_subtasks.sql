CREATE TABLE IF NOT EXISTS submission_subtasks (
    id VARCHAR(32) PRIMARY KEY,
    submission_item_id VARCHAR(32) NOT NULL REFERENCES submission_items(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL,
    subtask_name TEXT NOT NULL,
    status VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_submission_subtask_order UNIQUE (submission_item_id, sort_order)
);

CREATE INDEX IF NOT EXISTS ix_submission_subtasks_submission_item_id
    ON submission_subtasks (submission_item_id);

INSERT INTO submission_subtasks (
    id,
    submission_item_id,
    sort_order,
    subtask_name,
    status,
    created_at,
    updated_at
)
SELECT
    md5(random()::text || clock_timestamp()::text),
    submission_item.id,
    expanded.sort_order,
    expanded.subtask_name,
    NULL,
    NOW(),
    NOW()
FROM submission_items AS submission_item
JOIN LATERAL (
    SELECT
        TRIM(parts.subtask_name) AS subtask_name,
        parts.sort_order
    FROM regexp_split_to_table(COALESCE(submission_item.subtask_name, ''), E'\n')
        WITH ORDINALITY AS parts(subtask_name, sort_order)
) AS expanded ON TRUE
WHERE submission_item.subtask_name IS NOT NULL
    AND TRIM(expanded.subtask_name) <> ''
    AND NOT EXISTS (
        SELECT 1
        FROM submission_subtasks AS existing
        WHERE existing.submission_item_id = submission_item.id
    );
