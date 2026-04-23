"""Company profile returned at the root `company` field (and as nested defendants)."""

from pydantic import BaseModel

from models.industry import Industry


class Company(BaseModel):
    companyId: int
    orbisId: str
    companyName: str
    industry: Industry
