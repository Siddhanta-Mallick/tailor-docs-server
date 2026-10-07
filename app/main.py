import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Preserve compatibility with the existing local environment variable spelling.
if not os.getenv("OPENAI_API_KEY") and os.getenv("OPEN_AI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_API_KEY"]

from app.api.tailor import router as tailor_router
from app.auth import require_user_id, validate_cognito_configuration
from app.database import close_pool, open_pool
from app.api.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_cognito_configuration()
    await open_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(tailor_router, dependencies=[Depends(require_user_id)])
app.include_router(sessions_router, dependencies=[Depends(require_user_id)])
