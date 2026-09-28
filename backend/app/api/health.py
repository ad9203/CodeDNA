"""Health endpoints for container orchestration and uptime monitoring."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness probe: returns 200 if process is running."""
    return {"status": "ok", "service": "codedna-backend"}


@router.get("/health/ready")
async def health_ready() -> dict[str, str]:
    """Readiness probe: returns 200 if application configuration is initialized."""
    return {
        "status": "ready",
        "service": "codedna-backend",
        "environment": settings.environment,
    }
