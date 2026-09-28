"""Health endpoints for container orchestration and uptime monitoring."""

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.db.session import check_db_ready

router = APIRouter(tags=["Health"])


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness probe: returns 200 if process is running."""
    return {"status": "ok", "service": "codedna-backend"}


@router.get("/health/ready")
async def health_ready() -> dict[str, str]:
    """Readiness probe: returns 200 if database and configuration are healthy."""
    db_ok = await check_db_ready()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )

    return {
        "status": "ready",
        "service": "codedna-backend",
        "environment": settings.environment,
        "database": "connected",
    }
