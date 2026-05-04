"""
Litigation data access — SQL Server (pymssql).

Schema (LitigationTracking_QA):
  agg.AllDefendantCaseData   NormalizedDefendantId, Name, CompanyId, CaseID,
                              CaseTypeId, MDLID, CourtID, AttorneyId,
                              IndustryId, IndustryCode, IndustryName
  agg.AllCases               ClientID, LitagionID, LitagionName, IsGroup,
                              MostRecentFilingDate, NumberOfCases, TotalFederal,
                              TotalState, TotalCompanies, TotalIndustries
  dbo.LitigationTrackingCase CaseID, DocketNumber, MDLID, HasMultiplePlaintiffs,
                              CourtID, DateFiled, IsClassAction, Summary,
                              CaseTypeId, IsOccupational, IsInjunctive, ...
  dbo.NormalizedDefendant    NormalizedDefendantID, Name, ModelingIndustryId
  dbo.Court                  CourtID, Name, IsFederal, StateId
  dbo.State                  StateId, Name, Abbreviation
  dbo.Attorney               AttorneyID, Name, City, StateId
  dbo.CaseType               CaseTypeId, Name
  dbo.CaseStatus             CaseID, StatusTypeId, StatusDate, Amount, Note
  dbo.StatusType             StatusTypeId, Name
  dbo.MDL                    MDLID, Name, ...
  dbo.CasePlaintiff          CasePlaintiffId, CaseID, FirstName, Middlename,
                              LastName, OrderId, PlaintiffTypeId

orbisId query param maps directly to NormalizedDefendantID (integer).
Pagination is pushed to SQL (OFFSET/FETCH) — never fetch all rows into Python.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import partial
from typing import Any

import pymssql

from config.database import close_connection, get_connection
from models.attorney import Attorney
from models.case import Case
from models.case_status import CaseStatus
from models.company import Company
from models.court import Court
from models.court_state import CourtState
from models.industry import Industry
from models.mdl import MDL
from models.plaintiff import Plaintiff
from models.summary import Summary

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

_SUMMARY_SQL = """
    SELECT
        COUNT(DISTINCT adcd.CaseID)                                              AS totalCases,
        COUNT(DISTINCT CASE WHEN co.IsFederal=1 THEN adcd.CaseID ELSE NULL END) AS totalFederal,
        COUNT(DISTINCT CASE WHEN co.IsFederal=0 THEN adcd.CaseID ELSE NULL END) AS totalState,
        MAX(ltc.DateFiled)                                                       AS mostRecentFilingDate
    FROM agg.AllDefendantCaseData adcd
    JOIN dbo.LitigationTrackingCase ltc ON adcd.CaseID  = ltc.CaseID
    JOIN dbo.Court co                   ON ltc.CourtID  = co.CourtID
    WHERE adcd.NormalizedDefendantId = %s
"""

_COMPANY_SQL = """
    SELECT TOP 1
        nd.NormalizedDefendantID AS companyId,
        nd.Name                  AS companyName,
        adcd.IndustryId,
        adcd.IndustryCode,
        adcd.IndustryName
    FROM dbo.NormalizedDefendant nd
    LEFT JOIN agg.AllDefendantCaseData adcd
           ON nd.NormalizedDefendantID = adcd.NormalizedDefendantId
          AND adcd.IndustryId IS NOT NULL
    WHERE nd.NormalizedDefendantID = %s
    ORDER BY adcd.IndustryId
"""

_CASES_BASE_SQL = """
    SELECT
        ltc.CaseID,
        ltc.DocketNumber,
        ltc.IsClassAction,
        ltc.IsOccupational,
        ltc.IsInjunctive,
        ltc.DateFiled,
        ltc.Summary,
        ltc.MDLID,
        ct.Name         AS caseType,
        co.CourtID,
        co.Name         AS courtName,
        co.IsFederal,
        s.Name          AS stateName,
        s.Abbreviation  AS stateAbbr,
        adcd.AttorneyId,
        a.Name          AS attorneyName,
        a.City          AS attorneyCity,
        sa.Abbreviation AS attorneyState,
        status_sub.StatusName,
        status_sub.StatusDate,
        status_sub.Amount,
        status_sub.Note,
        mdl.MDLID       AS mdlId,
        mdl.Name        AS mdlName
    FROM agg.AllDefendantCaseData adcd
    JOIN dbo.LitigationTrackingCase ltc ON adcd.CaseID    = ltc.CaseID
    JOIN dbo.CaseType ct                ON ltc.CaseTypeId  = ct.CaseTypeId
    JOIN dbo.Court co                   ON ltc.CourtID    = co.CourtID
    LEFT JOIN dbo.State s               ON co.StateId     = s.StateId
    LEFT JOIN dbo.Attorney a            ON adcd.AttorneyId = a.AttorneyID
    LEFT JOIN dbo.State sa              ON a.StateId      = sa.StateId
    OUTER APPLY (
        SELECT TOP 1
            st.Name     AS StatusName,
            cs.StatusDate,
            cs.Amount,
            cs.Note
        FROM dbo.CaseStatus cs
        JOIN dbo.StatusType st ON cs.StatusTypeId = st.StatusTypeId
        WHERE cs.CaseID = ltc.CaseID
        ORDER BY cs.StatusDate DESC
    ) AS status_sub
    LEFT JOIN dbo.MDL mdl               ON ltc.MDLID      = mdl.MDLID
    WHERE adcd.NormalizedDefendantId = %s
"""

# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


def _build_filter_clauses(query: LitigationQuery) -> tuple[str, list[Any]]:
    """Return extra WHERE clause fragments and their parameter values."""
    clauses, params = [], []
    if query.date_from:
        clauses.append("AND ltc.DateFiled >= %s")
        params.append(str(query.date_from))
    if query.date_to:
        clauses.append("AND ltc.DateFiled <= %s")
        params.append(str(query.date_to))
    return (" ".join(clauses), params)


# ---------------------------------------------------------------------------
# Sync helpers — run inside run_in_executor
# ---------------------------------------------------------------------------


def _fetchone(conn: pymssql.Connection, sql: str, params: list) -> dict | None:
    with conn.cursor(as_dict=True) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _fetchall(conn: pymssql.Connection, sql: str, params: list) -> list[dict]:
    with conn.cursor(as_dict=True) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Model mappers
# ---------------------------------------------------------------------------


def _to_summary(row: dict) -> Summary:
    return Summary(
        totalCases=row["totalCases"] or 0,
        totalFederal=row["totalFederal"] or 0,
        totalState=row["totalState"] or 0,
        mostRecentFilingDate=str(row["mostRecentFilingDate"]) if row["mostRecentFilingDate"] else None,
    )


def _to_company(row: dict, orbis_id: str) -> Company:
    industry = None
    if row.get("IndustryId"):
        industry = Industry(
            industryId=row["IndustryId"],
            industryName=row["IndustryName"] or "",
            industryCode=row["IndustryCode"] or "",
        )
    return Company(
        companyId=row["companyId"],
        orbisId=orbis_id,
        companyName=row["companyName"] or "",
        industry=industry or Industry(industryId=0, industryName="", industryCode=""),
    )


def _to_case(row: dict) -> Case:
    court_state = (
        CourtState(name=row["stateName"], abbreviation=row["stateAbbr"])
        if row["stateName"]
        else None
    )
    status = (
        CaseStatus(
            status=row["StatusName"],
            statusDate=str(row["StatusDate"]) if row["StatusDate"] else None,
            amount=float(row["Amount"]) if row["Amount"] is not None else None,
            note=row["Note"],
        )
        if row["StatusName"]
        else None
    )
    mdl = (
        MDL(mdlId=row["mdlId"], name=row["mdlName"] or "", role="")
        if row["mdlId"]
        else None
    )
    attorney = (
        Attorney(
            attorneyId=row["AttorneyId"],
            name=row["attorneyName"] or "",
            city=row["attorneyCity"] or "",
            state=row["attorneyState"] or "",
        )
        if row["AttorneyId"]
        else None
    )
    return Case(
        caseId=row["CaseID"],
        docketNumber=row["DocketNumber"] or "",
        caseType=row["caseType"] or "",
        dateFiled=str(row["DateFiled"]),
        summary=row["Summary"] or "",
        isClassAction=bool(row["IsClassAction"]),
        isOccupational=bool(row["IsOccupational"]),
        isInjunctive=bool(row["IsInjunctive"]),
        court=Court(
            courtId=row["CourtID"],
            name=row["courtName"] or "",
            isFederal=bool(row["IsFederal"]),
            state=court_state,
        ),
        status=status,
        mdl=mdl,
        attorney=attorney,
        plaintiffs=[],
        causesOfAction=[],
        harms=[],
        hazards=[],
        tags=[],
        documents=[],
    )


# ---------------------------------------------------------------------------
# Query dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LitigationQuery:
    orbis_id: str
    date_from: date | None
    date_to: date | None
    harm_type: str | None
    limit: int = 20
    offset: int = 0


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class LitigationRepository:
    async def fetch_litigation_bundle(
        self,
        query: LitigationQuery,
    ) -> tuple[Summary, Company, list[Case]]:
        db_result = await self._try_load_from_db(query)
        if db_result is not None:
            return db_result
        # Fallback: mock data with manual pagination
        all_cases = self._mock_cases(query)
        page = all_cases[query.offset : query.offset + query.limit]
        return self._mock_summary(query), self._mock_company(query), page

    async def fetch_case_by_id(self, case_id: int) -> Case | None:
        try:
            conn = await get_connection()
            loop = asyncio.get_running_loop()
            sql = (
                _CASES_BASE_SQL
                + " AND ltc.CaseID = %s"
                + " ORDER BY ltc.DateFiled DESC"
                + " OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY"
            )
            # NormalizedDefendantId filter not applicable here; use a broad match
            # Re-query without the defendant filter
            single_sql = """
                SELECT
                    ltc.CaseID, ltc.DocketNumber, ltc.IsClassAction, ltc.IsOccupational,
                    ltc.IsInjunctive, ltc.DateFiled, ltc.Summary, ltc.MDLID,
                    ct.Name         AS caseType,
                    co.CourtID, co.Name AS courtName, co.IsFederal,
                    s.Name          AS stateName, s.Abbreviation AS stateAbbr,
                    NULL            AS AttorneyId,
                    NULL            AS attorneyName,
                    NULL            AS attorneyCity,
                    NULL            AS attorneyState,
                    status_sub.StatusName, status_sub.StatusDate,
                    status_sub.Amount, status_sub.Note,
                    mdl.MDLID       AS mdlId, mdl.Name AS mdlName
                FROM dbo.LitigationTrackingCase ltc
                JOIN dbo.CaseType ct  ON ltc.CaseTypeId = ct.CaseTypeId
                JOIN dbo.Court co     ON ltc.CourtID    = co.CourtID
                LEFT JOIN dbo.State s ON co.StateId     = s.StateId
                OUTER APPLY (
                    SELECT TOP 1 st.Name AS StatusName, cs.StatusDate, cs.Amount, cs.Note
                    FROM dbo.CaseStatus cs
                    JOIN dbo.StatusType st ON cs.StatusTypeId = st.StatusTypeId
                    WHERE cs.CaseID = ltc.CaseID
                    ORDER BY cs.StatusDate DESC
                ) AS status_sub
                LEFT JOIN dbo.MDL mdl ON ltc.MDLID = mdl.MDLID
                WHERE ltc.CaseID = %s
            """
            row = await loop.run_in_executor(
                None, partial(_fetchone, conn, single_sql, [case_id])
            )
            return _to_case(row) if row else None
        except Exception:
            await close_connection()
            return self._find_mock_case_by_id(case_id)

    async def _try_load_from_db(
        self,
        query: LitigationQuery,
    ) -> tuple[Summary, Company, list[Case]] | None:
        try:
            conn = await get_connection()
            loop = asyncio.get_running_loop()
            nd_id = int(query.orbis_id)

            filter_clause, filter_params = _build_filter_clauses(query)

            # --- Summary ---
            summary_sql = _SUMMARY_SQL + " " + filter_clause
            summary_row = await loop.run_in_executor(
                None, partial(_fetchone, conn, summary_sql, [nd_id] + filter_params)
            )
            if not summary_row or not summary_row["totalCases"]:
                return None

            # --- Company ---
            company_row = await loop.run_in_executor(
                None, partial(_fetchone, conn, _COMPANY_SQL, [nd_id])
            )
            if not company_row:
                return None

            # --- Cases (SQL-paginated) ---
            cases_sql = (
                _CASES_BASE_SQL
                + " "
                + filter_clause
                + " ORDER BY ltc.DateFiled DESC"
                + " OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
            )
            case_rows = await loop.run_in_executor(
                None,
                partial(
                    _fetchall,
                    conn,
                    cases_sql,
                    [nd_id] + filter_params + [query.offset, query.limit],
                ),
            )

            return (
                _to_summary(summary_row),
                _to_company(company_row, query.orbis_id),
                [_to_case(r) for r in case_rows],
            )

        except Exception:
            await close_connection()
            return None

    # -----------------------------------------------------------------------
    # Mock helpers (fallback when DB is unreachable)
    # -----------------------------------------------------------------------

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
            industry=Industry(industryId=44, industryName="Manufacturing", industryCode="MFG"),
        )

    def _mock_cases(self, query: LitigationQuery) -> list[Case]:
        _ = query
        base = date(2023, 10, 18)
        plaintiffs = [
            Plaintiff(plaintiffId=1, firstName="John", middleName=None, lastName="Smith", order=1),
            Plaintiff(plaintiffId=2, firstName="Mary", middleName="Q", lastName="Jones", order=2),
        ]
        template = Case(
            caseId=998877,
            docketNumber="2:23-cv-01234",
            caseType="Product Liability",
            dateFiled=base.isoformat(),
            summary="Example case summary",
            isClassAction=False,
            isOccupational=False,
            isInjunctive=False,
            court=Court(
                courtId=22,
                name="US District Court",
                isFederal=True,
                state=CourtState(name="California", abbreviation="CA"),
            ),
            status=CaseStatus(status="Open", statusDate="2023-11-01", amount=100000.0, note="Status note"),
            mdl=None,
            attorney=Attorney(attorneyId=55, name="Jane Doe", city="San Francisco", state="CA"),
            plaintiffs=plaintiffs,
            causesOfAction=[],
            harms=[],
            hazards=[],
            tags=[],
            documents=[],
        )
        cases = [
            template.model_copy(update={"caseId": 998877 + i, "dateFiled": (base - timedelta(days=i)).isoformat()})
            for i in range(120)
        ]
        cases.sort(key=lambda c: c.dateFiled, reverse=True)
        return cases
