"""FastAPI application entrypoint for CodeDNA."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dashboard import router as dashboard_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.core.errors import CodeDNAError, ExternalServiceError, SecurityValidationError
from app.core.logging import (
    clear_trace_context,
    configure_logging,
    get_logger,
    set_trace_context,
)

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
    delivery_id = request.headers.get("X-GitHub-Delivery")
    request.state.request_id = request_id
    if delivery_id:
        request.state.delivery_id = delivery_id

    set_trace_context(request_id=request_id, delivery_id=delivery_id)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if delivery_id:
            response.headers["X-GitHub-Delivery"] = delivery_id
        return response
    finally:
        clear_trace_context()


# Include routers
app.include_router(health_router)
app.include_router(webhook_router, prefix=settings.api_v1_prefix)
app.include_router(feedback_router, prefix=settings.api_v1_prefix)
app.include_router(dashboard_router, prefix=settings.api_v1_prefix)


@app.exception_handler(CodeDNAError)
async def codedna_error_handler(request: Request, exc: CodeDNAError):
    status_code = (
        400
        if isinstance(exc, SecurityValidationError)
        else 502
        if isinstance(exc, ExternalServiceError)
        else 500
    )
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "codedna_error_caught",
        error_code=exc.code,
        error_msg=exc.message,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "unhandled_internal_error",
        error_msg=str(exc),
        request_id=request_id,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred.",
            "request_id": request_id,
        },
    )
