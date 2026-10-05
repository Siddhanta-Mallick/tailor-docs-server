# Store Tailoring Workspaces in Sessions

Tailoring persistence will use PostgreSQL `sessions` rows, each owned by the verified Cognito User Pool `sub` stored as `user_id`. A session groups a job description, immutable baseline resume, mutable current resume, and their comparable floored similarity percentages. This replaces treating baseline and tailored resumes as independently stored records for the session-persistence work.

```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    session_name VARCHAR(255) NOT NULL,
    job_description VARCHAR(15000) NOT NULL,
    baseline_jd_score SMALLINT NOT NULL,
    current_jd_score SMALLINT NOT NULL,
    baseline_resume JSONB NOT NULL,
    current_resume JSONB NOT NULL,

    CHECK (btrim(session_name) <> ''),
    CHECK (btrim(job_description) <> ''),
    CHECK (baseline_jd_score BETWEEN 0 AND 100),
    CHECK (current_jd_score BETWEEN 0 AND 100),
    CHECK (jsonb_typeof(baseline_resume) = 'object'),
    CHECK (jsonb_typeof(current_resume) = 'object')
);
```

## Considered Options

The schema deliberately permits duplicate session names and job descriptions because `session_id` is the only identity constraint. It stores Cognito's external identifier as `VARCHAR(36)` rather than PostgreSQL `UUID` to avoid coupling the database to an identity-provider format. Scores are stored as integer percentages from 0 through 100, with fractional values discarded. JSONB constraints require resume payloads to be objects; Pydantic remains responsible for validating the full resume structure.

## Consequences

There is no index, timestamp, or account-deletion policy in this initial schema. Those concerns are deferred for a later persistence and lifecycle decision. `gen_random_uuid()` must be available in the target PostgreSQL deployment.
