import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import Container, Uow

logger = logging.getLogger("leeral.health")

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(container: Container, uow: Uow, response: Response) -> dict[str, str]:
    checks = {"api": "ok", "ai_provider": container.ai.name}
    try:
        await uow.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("health_database_failed")
        checks["database"] = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks
