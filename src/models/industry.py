"""Industry classification returned under `company.industry`."""

from pydantic import BaseModel


class Industry(BaseModel):
    industryId: int
    industryName: str
    industryCode: str
