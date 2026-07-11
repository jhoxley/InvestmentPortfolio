"""Health and readiness endpoints for operational monitoring."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.ladder import ProblemDetail

router = APIRouter(tags=["Operations"])


@router.get("/health", summary="Liveness check")
async def health_check() -> dict[str, str]:
    """Return a simple liveness response.

    Returns:
        JSON object with status 'ok'.
    """
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness check — confirms data directory is accessible",
    responses={503: {"model": ProblemDetail}},
)
async def readiness_check() -> JSONResponse:
    """Return readiness status based on data directory accessibility.

    Returns:
        200 with status 'ready' if the data directory exists and is accessible,
        503 with a ProblemDetail body otherwise.
    """
    settings = get_settings()
    data_dir = settings.data.directory
    if data_dir.exists() and data_dir.is_dir():
        return JSONResponse(status_code=200, content={"status": "ready"})

    problem = ProblemDetail(
        type="https://portfolio-analysis/errors/service-not-ready",
        title="Service Not Ready",
        status=503,
        detail=f"Data directory '{data_dir}' is not accessible.",
        instance="/ready",
    )
    return JSONResponse(
        status_code=503,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )
