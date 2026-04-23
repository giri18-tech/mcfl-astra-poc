"""Single litigation matter (`cases[]`)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from models.attorney import Attorney
from models.case_status import CaseStatus
from models.company import Company
from models.court import Court
from models.mdl import MDL
from models.plaintiff import Plaintiff


class Case(BaseModel):
    caseId: int
    docketNumber: str
    caseType: str
    dateFiled: str
    summary: str
    isClassAction: bool
    isOccupational: bool
    court: Court
    status: CaseStatus | None = None
    mdl: MDL | None = None
    attorney: Attorney | None = None
    plaintiffs: list[Plaintiff] = Field(default_factory=list)
    defendants: list[Company] = Field(default_factory=list)
    causesOfAction: list[Any] = Field(default_factory=list)
    harms: list[Any] = Field(default_factory=list)
    hazards: list[Any] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    documents: list[Any] = Field(default_factory=list)
