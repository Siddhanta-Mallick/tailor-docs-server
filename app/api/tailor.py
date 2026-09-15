from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.models.resume import Resume
from app.services.tailorer import GenerationUnavailableError, InvalidResumeOutputError, tailor_resume


router = APIRouter(prefix="/api/tailor", tags=["tailor"])


def _request_error(message: str, location: tuple[str, ...] = ("body",)) -> RequestValidationError:
    return RequestValidationError(
        [{"type": "value_error", "loc": location, "msg": message, "input": None}]
    )


@router.post("/resume", response_model=Resume)
async def tailor_resume_route(payload: dict[str, Any] = Body(...)) -> Resume:
    expected_fields = {"approved_job_description", "baseline_resume"}
    if set(payload) != expected_fields:
        raise _request_error("Request must contain exactly approved_job_description and baseline_resume.")

    job_description = payload["approved_job_description"]
    if not isinstance(job_description, str) or not job_description.strip():
        raise _request_error("approved_job_description must contain non-whitespace text.", ("body", "approved_job_description"))

    try:
        baseline_resume = Resume.model_validate(payload["baseline_resume"])
    except ValidationError as error:
        errors = []
        for item in error.errors():
            item["loc"] = ("body", "baseline_resume", *item["loc"])
            errors.append(item)
        raise RequestValidationError(errors) from None

    try:
        return await tailor_resume(job_description, baseline_resume)
    except GenerationUnavailableError:
        raise HTTPException(
            status_code=502, detail="Resume generation is temporarily unavailable."
        ) from None
    except InvalidResumeOutputError:
        raise HTTPException(
            status_code=502, detail="Resume generation returned an invalid structure."
        ) from None
