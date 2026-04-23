"""Named plaintiff row (`cases[].plaintiffs[]`), ordered by `order`."""

from pydantic import BaseModel


class Plaintiff(BaseModel):
    plaintiffId: int
    firstName: str
    middleName: str | None = None
    lastName: str
    order: int
