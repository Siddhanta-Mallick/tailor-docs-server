# Store Tailoring Workspaces in Sessions

Tailoring persistence uses PostgreSQL rows owned by the verified Cognito User Pool `sub`, stored as `user_id`. A user first saves named Baseline Resumes. A Tailoring Session stores its Job Description, Current Resume, nullable JD scores, and a foreign key to the selected Baseline Resume. The browser owns all unsaved edits; only explicit baseline and session save requests write to PostgreSQL.

```sql
CREATE TABLE baseline_resumes (
    baseline_resume_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    resume JSONB NOT NULL,

    CHECK (btrim(name) <> ''),
    CHECK (jsonb_typeof(resume) = 'object')
);

CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    session_name VARCHAR(255) NOT NULL,
    job_description VARCHAR(15000) NOT NULL,
    baseline_resume_id UUID NOT NULL REFERENCES baseline_resumes(baseline_resume_id) ON DELETE RESTRICT,
    baseline_jd_score SMALLINT,
    current_jd_score SMALLINT,
    current_resume JSONB NOT NULL,

    CHECK (btrim(session_name) <> ''),
    CHECK (btrim(job_description) <> ''),
    CHECK (baseline_jd_score BETWEEN 0 AND 100),
    CHECK (current_jd_score BETWEEN 0 AND 100),
    CHECK (jsonb_typeof(current_resume) = 'object')
);
```

## Considered Options

Baseline Resumes are versioned by insertion rather than overwritten, so a saved session continues to reference the exact resume the user selected. The schema permits duplicate baseline and session names because their UUIDs are the only identity constraints. `user_id` is `VARCHAR(36)` to avoid coupling the database to an identity-provider format. Resume JSONB columns are constrained to objects; Pydantic validates their complete structure before storage.

## Consequences

The API exposes baseline lists as IDs and names only. It loads a selected baseline server-side for the first tailoring request, while later requests may supply a client-managed Tailoring Input. No endpoint persists a tailoring result automatically. Scores remain `NULL` until their algorithm is implemented. The local database schema is applied explicitly from `db/schema.sql`; no migration framework is used yet.
