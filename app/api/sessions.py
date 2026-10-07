from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app import database
from app.auth import require_user_id
from app.models.session import (
    BaselineResumeCreate,
    BaselineResumeSummary,
    SessionDetail,
    SessionSummary,
    SessionWrite,
)


router = APIRouter(prefix="/api", tags=["sessions"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found.")


@router.post("/baseline-resumes", response_model=BaselineResumeSummary, status_code=201)
async def create_baseline_resume_route(
    payload: BaselineResumeCreate, user_id: str = Depends(require_user_id)
) -> dict:
    return await database.create_baseline_resume(user_id, payload.name, payload.resume.model_dump())


@router.get("/baseline-resumes", response_model=list[BaselineResumeSummary])
async def list_baseline_resumes_route(user_id: str = Depends(require_user_id)) -> list[dict]:
    return await database.list_baseline_resumes(user_id)


@router.post("/sessions", response_model=SessionSummary, status_code=201)
async def create_session_route(payload: SessionWrite, user_id: str = Depends(require_user_id)) -> dict:
    session = await database.create_session(
        user_id,
        payload.session_name,
        payload.job_description,
        payload.baseline_resume_id,
        payload.current_resume.model_dump(),
    )
    if session is None:
        raise _not_found()
    return session


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions_route(user_id: str = Depends(require_user_id)) -> list[dict]:
    return await database.list_sessions(user_id)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_route(session_id: UUID, user_id: str = Depends(require_user_id)) -> dict:
    session = await database.get_session(user_id, session_id)
    if session is None:
        raise _not_found()
    return session


@router.put("/sessions/{session_id}", response_model=SessionSummary)
async def update_session_route(
    session_id: UUID, payload: SessionWrite, user_id: str = Depends(require_user_id)
) -> dict:
    session = await database.update_session(
        user_id,
        session_id,
        payload.session_name,
        payload.job_description,
        payload.baseline_resume_id,
        payload.current_resume.model_dump(),
    )
    if session is None:
        raise _not_found()
    return session
