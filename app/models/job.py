from typing import Literal

from pydantic import BaseModel


class JobDescriptionRequest(BaseModel):
    url: str | None = None
    text: str | None = None


class JobDescriptionResponse(BaseModel):
    candidate_job_description: str
    source: Literal["url", "text"]
    requires_user_approval: Literal[True] = True
