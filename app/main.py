from fastapi import FastAPI

from app.api.jobs import router as jobs_router
from app.api.tailor import router as tailor_router


app = FastAPI()
app.include_router(jobs_router)
app.include_router(tailor_router)
