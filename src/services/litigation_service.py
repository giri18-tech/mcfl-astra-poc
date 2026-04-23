"""
Litigation use-cases.

`LitigationRepository` owns I/O (Postgres when ready, otherwise mocks).
This layer only shapes responses: list + pagination for search, pass-through for get-by-id.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from models.case import Case
from models.litigation_response import LitigationResponse
from models.pagination import Pagination
from repositories.litigation_repository import LitigationQuery, LitigationRepository


class LitigationService:
    def __init__(self, repository: LitigationRepository | None = None) -> None:
        self._repository = repository or LitigationRepository()

    async def get_litigation(
        self,
        *,
        orbis_id: str,
        date_from: date | None,
        date_to: date | None,
        harm_type: str | None,
        limit: int,
        offset: int,
    ) -> LitigationResponse:
        query = LitigationQuery(
            orbis_id=orbis_id,
            date_from=date_from,
            date_to=date_to,
            harm_type=harm_type,
        )
        summary, company, all_cases = await self._repository.fetch_litigation_bundle(query)
        page = all_cases[offset : offset + limit]
        total = summary.totalCases
        next_page = self._build_next_page(
            orbis_id=orbis_id,
            date_from=date_from,
            date_to=date_to,
            harm_type=harm_type,
            limit=limit,
            offset=offset,
            total=total,
        )
        pagination = Pagination(
            total_records=total,
            limit=limit,
            offset=offset,
            next_page=next_page,
        )
        return LitigationResponse(
            summary=summary,
            company=company,
            cases=page,
            pagination=pagination,
        )

    async def get_case_by_id(self, case_id: int) -> Case | None:
        return await self._repository.fetch_case_by_id(case_id)

    def _build_next_page(
        self,
        *,
        orbis_id: str,
        date_from: date | None,
        date_to: date | None,
        harm_type: str | None,
        limit: int,
        offset: int,
        total: int,
    ) -> str | None:
        if offset + limit >= total:
            return None
        params: dict[str, str] = {
            "orbisId": orbis_id,
            "limit": str(limit),
            "offset": str(offset + limit),
        }
        if date_from is not None:
            params["date_from"] = date_from.isoformat()
        if date_to is not None:
            params["date_to"] = date_to.isoformat()
        if harm_type is not None:
            params["harm_type"] = harm_type
        return f"/litigation?{urlencode(params)}"
