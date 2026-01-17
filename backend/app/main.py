from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.api.routes import chat, sessions, files

# Setup logging before creating the app
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Startup
    await init_db()
    logger.info(f"API started on {settings.HOST}:{settings.PORT}")
    yield


app = FastAPI(
    title="StocksGPT API",
    description="Unified chat interface for ChatGPT and Gemini 3.0 Flash with financial analysis",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Serve static uploaded files at /uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router, prefix="/api/files", tags=["files"])


@app.get("/")
async def root():
    import logging
    logger = logging.getLogger(__name__)
    logger.debug("Root endpoint accessed")
    return JSONResponse({"message": "StocksGPT API", "status": "running"})


@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy"})


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
