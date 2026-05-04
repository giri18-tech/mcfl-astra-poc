"""Latest known procedural / monetary status (`cases[].status`)."""

from pydantic import BaseModel


class CaseStatus(BaseModel):
    status: str
    statusDate: str | None = None
    amount: float | None = None
    note: str | None = None
