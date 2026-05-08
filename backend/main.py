import logging
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("UniBot backend starting up...")
    yield
    logger.info("UniBot backend shutting down.")

app = FastAPI(
    title="UniBot API",
    description="University Course RAG Chatbot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers.chat import router as chat_router  # noqa: E402

app.include_router(chat_router, prefix="/api")

@app.get("/health", tags=["health"])
@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
