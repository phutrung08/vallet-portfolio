from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Liveness check payload."""

    status: str


@router.get("/health")
def get_health() -> HealthResponse:
    """Return process liveness."""
    return HealthResponse(status="ok")
