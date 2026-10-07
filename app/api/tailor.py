from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.models.resume import Resume
from app import database
from app.auth import require_user_id
from app.services.tailorer import GenerationUnavailableError, InvalidResumeOutputError, tailor_resume


router = APIRouter(prefix="/api/tailor", tags=["tailor"])
MAX_JOB_DESCRIPTION_LENGTH = 15_000


def _request_error(message: str, location: tuple[str, ...] = ("body",)) -> RequestValidationError:
    return RequestValidationError(
        [{"type": "value_error", "loc": location, "msg": message, "input": None}]
    )


@router.post("/resume", response_model=Resume)
async def tailor_resume_route(
    payload: dict[str, Any] = Body(...), user_id: str = Depends(require_user_id)
) -> Resume:
    expected_fields = {"job_description", "resume"}
    baseline_fields = {"job_description", "baseline_resume_id"}
    if set(payload) not in (expected_fields, baseline_fields):
        raise _request_error(
            "Request must contain job_description and exactly one of resume or baseline_resume_id."
        )

    job_description = payload["job_description"]
    if not isinstance(job_description, str) or not job_description.strip():
        raise _request_error("job_description must contain non-whitespace text.", ("body", "job_description"))
    job_description = job_description[:MAX_JOB_DESCRIPTION_LENGTH]

    if "resume" in payload:
        try:
            tailoring_input = Resume.model_validate(payload["resume"])
        except ValidationError as error:
            errors = []
            for item in error.errors():
                item["loc"] = ("body", "resume", *item["loc"])
                errors.append(item)
            raise RequestValidationError(errors) from None
    else:
        baseline_resume_id = payload["baseline_resume_id"]
        if not isinstance(baseline_resume_id, str):
            raise _request_error("baseline_resume_id must be a UUID.", ("body", "baseline_resume_id"))
        try:
            baseline = await database.get_baseline_resume(user_id, UUID(baseline_resume_id))
        except ValueError:
            raise _request_error("baseline_resume_id must be a UUID.", ("body", "baseline_resume_id")) from None
        if baseline is None:
            raise HTTPException(status_code=404, detail="Not found.")
        try:
            tailoring_input = Resume.model_validate(baseline["resume"])
        except ValidationError:
            raise HTTPException(status_code=500, detail="Stored baseline resume is invalid.") from None

    try:
        return await tailor_resume(job_description, tailoring_input)
    except GenerationUnavailableError:
        raise HTTPException(
            status_code=502, detail="Resume generation is temporarily unavailable."
        ) from None
    except InvalidResumeOutputError:
        raise HTTPException(
            status_code=502, detail="Resume generation returned an invalid structure."
        ) from None
