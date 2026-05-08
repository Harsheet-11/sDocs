# main.py - FastAPI application entry point

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.result import router as result_router
from app.api.upload import router as upload_router
from app.database import create_tables


# LOGGING

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


# APPLICATION LIFESPAN

@asynccontextmanager
async def lifespan(app: FastAPI):

    # STARTUP

    logger.info(
        "Starting Research Paper Intelligence Tool API..."
    )

    create_tables()

    logger.info("Database tables ready")

    logger.info("API startup complete")

    yield

    # SHUTDOWN

    logger.info("Shutting down API...")


# CREATE FASTAPI APP

app = FastAPI(
    title="Research Paper Intelligence Tool API",
    description=(
        "Extract, analyze, and inspect "
        "claims from research papers."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# CORS

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ROUTERS

app.include_router(
    upload_router,
    prefix="/api",
)

app.include_router(
    result_router,
    prefix="/api",
)


# HEALTH CHECK

@app.get(
    "/health",
    tags=["Health"],
)
async def health_check() -> dict[str, str]:
    
    return {
        "status": "healthy",
        "version": "2.0.0",
    }


# ROOT

@app.get(
    "/",
    tags=["Root"],
)
async def root() -> dict[str, str]:

    return {
        "message": "Research Paper Intelligence Tool API",
        "docs": "/docs",
        "health": "/health",
    }