import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Preserve compatibility with the existing local environment variable spelling.
if not os.getenv("OPENAI_API_KEY") and os.getenv("OPEN_AI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_API_KEY"]

from app.api.tailor import router as tailor_router


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)
app.include_router(tailor_router)
