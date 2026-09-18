from fastapi import FastAPI

from app.api.tailor import router as tailor_router


app = FastAPI()
app.include_router(tailor_router)
