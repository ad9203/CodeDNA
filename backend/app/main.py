"""FastAPI application entrypoint for CodeDNA."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging(settings.log_level)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "codedna_startup",
        environment=settings.environment,
        log_level=settings.log_level,
    )
    yield
    logger.info("codedna_shutdown")


app = FastAPI(
    title="CodeDNA AI Code Review Engine",
    description="Context-aware GitHub code review agent with persistent memory powered by Hindsight and Groq.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Middleware (strict origin configuration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(settings.frontend_origin).rstrip("/")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Include routers
app.include_router(health_router)
