import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.errors import ForeignKeyViolation
from psycopg.types.json import Jsonb


SCHEMA_SQL = Path(__file__).parents[1] / "db" / "schema.sql"


@pytest.mark.integration
def test_schema_upgrades_legacy_sessions_and_enforces_baseline_ownership():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests.")

    schema_name = f"persistence_test_{uuid4().hex}"
    baseline = {"objective": "Legacy baseline"}
    current = {"objective": "Legacy current"}

    with psycopg.connect(database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
            try:
                cursor.execute(
                    """
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
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO sessions (
                        user_id, session_name, job_description, baseline_jd_score,
                        current_jd_score, baseline_resume, current_resume
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    ("legacy-user", "Legacy session", "Build APIs.", 42, 54, Jsonb(baseline), Jsonb(current)),
                )

                cursor.execute(SCHEMA_SQL.read_text())

                cursor.execute(
                    """
                    SELECT b.user_id, b.name, b.resume, s.baseline_resume_id,
                           s.baseline_jd_score, s.current_jd_score, s.current_resume
                    FROM sessions AS s
                    JOIN baseline_resumes AS b ON b.baseline_resume_id = s.baseline_resume_id
                    """
                )
                user_id, name, migrated_baseline, baseline_id, baseline_score, current_score, migrated_current = (
                    cursor.fetchone()
                )
                assert (user_id, migrated_baseline, baseline_score, current_score, migrated_current) == (
                    "legacy-user",
                    baseline,
                    42,
                    54,
                    current,
                )
                assert name.startswith("Migrated baseline ")

                cursor.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = 'sessions'
                      AND column_name = 'baseline_resume'
                    """,
                    (schema_name,),
                )
                assert cursor.fetchone() is None

                with pytest.raises(ForeignKeyViolation):
                    cursor.execute(
                        """
                        INSERT INTO sessions (
                            user_id, session_name, job_description, baseline_resume_id, current_resume
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        ("another-user", "Invalid session", "Build APIs.", baseline_id, Jsonb(current)),
                    )
            finally:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))
