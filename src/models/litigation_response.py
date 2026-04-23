"""Top-level GET /litigation response envelope."""

from pydantic import BaseModel

from models.case import Case
from models.company import Company
from models.pagination import Pagination
from models.summary import Summary


class LitigationResponse(BaseModel):
    summary: Summary
    company: Company
    cases: list[Case]
    pagination: Pagination
