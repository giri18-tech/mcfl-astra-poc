"""Offset/limit envelope returned alongside the case list."""

from pydantic import BaseModel


class Pagination(BaseModel):
    total_records: int
    limit: int
    offset: int
    next_page: str | None
