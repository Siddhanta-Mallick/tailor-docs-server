import os
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


pool: AsyncConnectionPool | None = None


async def open_pool() -> None:
    global pool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")

    pool = AsyncConnectionPool(conninfo=database_url, open=False)
    await pool.open(wait=True)


async def close_pool() -> None:
    global pool

    if pool is not None:
        await pool.close()
        pool = None


def _pool() -> AsyncConnectionPool:
    if pool is None:
        raise RuntimeError("Database connection pool is unavailable.")
    return pool


async def create_baseline_resume(user_id: str, name: str, resume: dict[str, Any]) -> dict[str, Any]:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                INSERT INTO baseline_resumes (user_id, name, resume)
                VALUES (%s, %s, %s)
                RETURNING baseline_resume_id, name
                """,
                (user_id, name, Jsonb(resume)),
            )
            return await cursor.fetchone()


async def list_baseline_resumes(user_id: str) -> list[dict[str, Any]]:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT baseline_resume_id, name
                FROM baseline_resumes
                WHERE user_id = %s
                ORDER BY name, baseline_resume_id
                """,
                (user_id,),
            )
            return await cursor.fetchall()


async def get_baseline_resume(user_id: str, baseline_resume_id: UUID) -> dict[str, Any] | None:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT baseline_resume_id, resume
                FROM baseline_resumes
                WHERE user_id = %s AND baseline_resume_id = %s
                """,
                (user_id, baseline_resume_id),
            )
            return await cursor.fetchone()


async def create_session(
    user_id: str,
    session_name: str,
    job_description: str,
    baseline_resume_id: UUID,
    current_resume: dict[str, Any],
) -> dict[str, Any] | None:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                INSERT INTO sessions (user_id, session_name, job_description, baseline_resume_id, current_resume)
                SELECT %s, %s, %s, baseline_resume_id, %s
                FROM baseline_resumes
                WHERE user_id = %s AND baseline_resume_id = %s
                RETURNING session_id, session_name
                """,
                (
                    user_id,
                    session_name,
                    job_description,
                    Jsonb(current_resume),
                    user_id,
                    baseline_resume_id,
                ),
            )
            return await cursor.fetchone()


async def list_sessions(user_id: str) -> list[dict[str, Any]]:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT session_id, session_name
                FROM sessions
                WHERE user_id = %s
                ORDER BY session_name, session_id
                """,
                (user_id,),
            )
            return await cursor.fetchall()


async def get_session(user_id: str, session_id: UUID) -> dict[str, Any] | None:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT session_id, session_name, job_description, baseline_resume_id,
                       baseline_jd_score, current_jd_score, current_resume
                FROM sessions
                WHERE user_id = %s AND session_id = %s
                """,
                (user_id, session_id),
            )
            return await cursor.fetchone()


async def update_session(
    user_id: str,
    session_id: UUID,
    session_name: str,
    job_description: str,
    baseline_resume_id: UUID,
    current_resume: dict[str, Any],
) -> dict[str, Any] | None:
    async with _pool().connection() as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                UPDATE sessions
                SET session_name = %s,
                    job_description = %s,
                    baseline_resume_id = %s,
                    current_resume = %s
                WHERE user_id = %s
                  AND session_id = %s
                  AND EXISTS (
                      SELECT 1
                      FROM baseline_resumes
                      WHERE user_id = %s AND baseline_resume_id = %s
                  )
                RETURNING session_id, session_name
                """,
                (
                    session_name,
                    job_description,
                    baseline_resume_id,
                    Jsonb(current_resume),
                    user_id,
                    session_id,
                    user_id,
                    baseline_resume_id,
                ),
            )
            return await cursor.fetchone()
