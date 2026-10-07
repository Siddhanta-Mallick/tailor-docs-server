from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.resume import Resume


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _nonblank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Value must contain non-whitespace text.")
    return value


class BaselineResumeCreate(RequestModel):
    name: str = Field(max_length=255)
    resume: Resume

    _validate_name = field_validator("name")(_nonblank)


class BaselineResumeSummary(BaseModel):
    baseline_resume_id: UUID
    name: str


class SessionWrite(RequestModel):
    session_name: str = Field(max_length=255)
    job_description: str = Field(max_length=15_000)
    baseline_resume_id: UUID
    current_resume: Resume

    _validate_session_name = field_validator("session_name")(_nonblank)
    _validate_job_description = field_validator("job_description")(_nonblank)


class SessionSummary(BaseModel):
    session_id: UUID
    session_name: str


class SessionDetail(SessionSummary):
    job_description: str
    baseline_resume_id: UUID
    baseline_jd_score: int | None
    current_jd_score: int | None
    current_resume: Resume
