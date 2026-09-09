from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.job import JobDescriptionRequest, JobDescriptionResponse
from app.services.scraper import DisallowedHostError, InvalidUrlError, ScrapeError, scrape_url


router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SCRAPE_FAILURE = {
    "code": "SCRAPE_BLOCKED_OR_FAILED",
    "message": "Could not retrieve usable job-description text. Please paste it manually.",
}


@router.post("/description/preview", response_model=JobDescriptionResponse)
async def preview_job_description(request: JobDescriptionRequest):
    if (request.url is None) == (request.text is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of url or text.")

    if request.text is not None:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text must not be empty.")
        candidate_job_description = request.text[:15_000]
        return JobDescriptionResponse(
            candidate_job_description=candidate_job_description,
            source="text",
        )

    try:
        candidate_job_description = await scrape_url(request.url)
    except InvalidUrlError:
        raise HTTPException(status_code=400, detail="URL must use http or https.") from None
    except DisallowedHostError:
        raise HTTPException(status_code=400, detail="URL host is not allowed.") from None
    except ScrapeError:
        return JSONResponse(status_code=422, content=SCRAPE_FAILURE)

    return JobDescriptionResponse(
        candidate_job_description=candidate_job_description,
        source="url",
    )
