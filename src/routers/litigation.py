"""
Litigation HTTP routes.

Flow for every request:
  1. FastAPI calls the handler below.
  2. Handler builds `LitigationService` and awaits one async method.
  3. Service delegates to `LitigationRepository` (database ping + SQL later, or mock data).
  4. Repository returns Pydantic models; the handler serializes them with `model_dump()`.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from models.case import Case
from services.litigation_service import LitigationService

router = APIRouter(tags=["litigation"])


@router.get("/litigation")
async def get_litigation(
    orbisId: str = Query(..., description="ORBIS company identifier"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    harm_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    service = LitigationService()
    result = await service.get_litigation(
        orbis_id=orbisId,
        date_from=date_from,
        date_to=date_to,
        harm_type=harm_type,
        limit=limit,
        offset=offset,
    )
    return result.model_dump()


@router.get("/litigation/cases/{case_id}")
async def get_case_by_id(case_id: int) -> dict:
    """Return one case by internal `caseId`; 404 if it does not exist in the current data source."""
    service = LitigationService()
    case: Case | None = await service.get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.model_dump()
