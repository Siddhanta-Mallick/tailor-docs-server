BEGIN;

CREATE TABLE IF NOT EXISTS baseline_resumes (
    baseline_resume_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    resume JSONB NOT NULL,

    CHECK (btrim(name) <> ''),
    CHECK (jsonb_typeof(resume) = 'object'),
    UNIQUE (user_id, baseline_resume_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    session_name VARCHAR(255) NOT NULL,
    job_description VARCHAR(15000) NOT NULL,
    baseline_resume_id UUID NOT NULL,
    baseline_jd_score SMALLINT,
    current_jd_score SMALLINT,
    current_resume JSONB NOT NULL,

    CHECK (btrim(session_name) <> ''),
    CHECK (btrim(job_description) <> ''),
    CHECK (baseline_jd_score BETWEEN 0 AND 100),
    CHECK (current_jd_score BETWEEN 0 AND 100),
    CHECK (jsonb_typeof(current_resume) = 'object'),
    FOREIGN KEY (user_id, baseline_resume_id)
        REFERENCES baseline_resumes(user_id, baseline_resume_id)
        ON DELETE RESTRICT
);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS baseline_resume_id UUID;
ALTER TABLE sessions ALTER COLUMN baseline_jd_score DROP NOT NULL;
ALTER TABLE sessions ALTER COLUMN current_jd_score DROP NOT NULL;

-- Preserve legacy embedded baselines by turning each one into an immutable saved baseline.
DO $$
DECLARE
    legacy_session RECORD;
    migrated_baseline_id UUID;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'sessions' AND column_name = 'baseline_resume'
    ) THEN
        FOR legacy_session IN
            SELECT session_id, user_id, baseline_resume
            FROM sessions
            WHERE baseline_resume_id IS NULL
        LOOP
            INSERT INTO baseline_resumes (user_id, name, resume)
            VALUES (
                legacy_session.user_id,
                'Migrated baseline ' || legacy_session.session_id,
                legacy_session.baseline_resume
            )
            RETURNING baseline_resume_id INTO migrated_baseline_id;

            UPDATE sessions
            SET baseline_resume_id = migrated_baseline_id
            WHERE session_id = legacy_session.session_id;
        END LOOP;

        ALTER TABLE sessions DROP COLUMN baseline_resume;
    END IF;
END $$;

ALTER TABLE sessions ALTER COLUMN baseline_resume_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'baseline_resumes'::regclass
          AND conname = 'baseline_resumes_user_id_baseline_resume_id_key'
    ) THEN
        ALTER TABLE baseline_resumes
        ADD CONSTRAINT baseline_resumes_user_id_baseline_resume_id_key
        UNIQUE (user_id, baseline_resume_id);
    END IF;
END $$;

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_baseline_resume_id_fkey;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'sessions'::regclass
          AND conname = 'sessions_user_id_baseline_resume_id_fkey'
    ) THEN
        ALTER TABLE sessions
        ADD CONSTRAINT sessions_user_id_baseline_resume_id_fkey
        FOREIGN KEY (user_id, baseline_resume_id)
        REFERENCES baseline_resumes(user_id, baseline_resume_id)
        ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS baseline_resumes_user_id_idx ON baseline_resumes (user_id);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions (user_id);

COMMIT;
