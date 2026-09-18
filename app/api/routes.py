import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.request import OptimizeRequest
from app.schemas.response import HealthResponse, OptimizationResponse
from app.services.optimization_service import (
    InterpretationError,
    OptimizationError,
    OptimizationService,
    ValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter()
service = OptimizationService()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.post("/optimize-energy", response_model=OptimizationResponse)
async def optimize_energy(request: OptimizeRequest):
    try:
        return service.optimize(request)
    except (InterpretationError, OptimizationError, ValidationError) as exc:
        logger.exception("optimize-energy failed")
        return JSONResponse(
            status_code=500, content={"detail": "internal processing error"}
        )