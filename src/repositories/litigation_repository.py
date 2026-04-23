"""
Litigation data access.

Flow:
  1. Public methods are called by `LitigationService`.
  2. For Postgres, we `ping_postgres()` then run SQL (not implemented yet → falls through).
  3. When there is no DB rowset, `_mock_*` builders supply the same JSON shape as production.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from config.database import ping_postgres
from models.attorney import Attorney
from models.case import Case
from models.case_status import CaseStatus
from models.company import Company
from models.court import Court
from models.court_state import CourtState
from models.industry import Industry
from models.plaintiff import Plaintiff
from models.summary import Summary


@dataclass(frozen=True)
class LitigationQuery:
    orbis_id: str
    date_from: date | None
    date_to: date | None
    harm_type: str | None


class LitigationRepository:
    async def fetch_litigation_bundle(
        self,
        query: LitigationQuery,
    ) -> tuple[Summary, Company, list[Case]]:
        postgres_bundle = await self._try_load_from_postgres(query)
        if postgres_bundle is not None:
            return postgres_bundle
        return (
            self._mock_summary(query),
            self._mock_company(query),
            self._mock_cases(query),
        )

    async def fetch_case_by_id(self, case_id: int) -> Case | None:
        if await ping_postgres():
            # Future: `SELECT ... FROM cases WHERE case_id = $1` and map to `Case`.
            _ = case_id
        return self._find_mock_case_by_id(case_id)

    async def _try_load_from_postgres(
        self,
        query: LitigationQuery,
    ) -> tuple[Summary, Company, list[Case]] | None:
        if not await ping_postgres():
            return None
        _ = query
        return None

    def _find_mock_case_by_id(self, case_id: int) -> Case | None:
        sentinel = LitigationQuery(orbis_id="", date_from=None, date_to=None, harm_type=None)
        for row in self._mock_cases(sentinel):
            if row.caseId == case_id:
                return row
        return None

    def _mock_summary(self, query: LitigationQuery) -> Summary:
        _ = query
        return Summary(
            totalCases=120,
            totalFederal=70,
            totalState=50,
            mostRecentFilingDate="2022-10-18",
        )

    def _mock_company(self, query: LitigationQuery) -> Company:
        return Company(
            companyId=10537,
            orbisId=query.orbis_id,
            companyName="ABC Manufacturing Inc.",
            industry=Industry(
                industryId=44,
                industryName="Manufacturing",
                industryCode="MFG",
            ),
        )

    def _mock_cases(self, query: LitigationQuery) -> list[Case]:
        _ = query
        base = date(2023, 10, 18)
        plaintiffs = sorted(
            [
                Plaintiff(
                    plaintiffId=1,
                    firstName="John",
                    middleName=None,
                    lastName="Smith",
                    order=1,
                ),
                Plaintiff(
                    plaintiffId=2,
                    firstName="Mary",
                    middleName="Q",
                    lastName="Jones",
                    order=2,
                ),
            ],
            key=lambda p: p.order,
        )

        template = Case(
            caseId=998877,
            docketNumber="2:23-cv-01234",
            caseType="Product Liability",
            dateFiled=base.isoformat(),
            summary="Example case summary",
            isClassAction=False,
            isOccupational=False,
            court=Court(
                courtId=22,
                name="US District Court",
                isFederal=True,
                state=CourtState(name="California", abbreviation="CA"),
            ),
            status=CaseStatus(
                status="Open",
                statusDate="2023-11-01",
                amount=100000.0,
                note="Status note",
            ),
            mdl=None,
            attorney=Attorney(
                attorneyId=55,
                name="Jane Doe",
                city="San Francisco",
                state="CA",
            ),
            plaintiffs=plaintiffs,
            defendants=[],
            causesOfAction=[],
            harms=[],
            hazards=[],
            tags=[],
            documents=[],
        )

        cases: list[Case] = []
        for i in range(120):
            filed = base - timedelta(days=i)
            cases.append(
                template.model_copy(
                    update={
                        "caseId": 998877 + i,
                        "dateFiled": filed.isoformat(),
                    }
                )
            )

        cases.sort(key=lambda c: c.dateFiled, reverse=True)
        return cases
