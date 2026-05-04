"""Aggregate counts for the litigation search (API `summary` object)."""

from pydantic import BaseModel


class Summary(BaseModel):
    totalCases: int
    totalFederal: int
    totalState: int
    mostRecentFilingDate: str | None = None
