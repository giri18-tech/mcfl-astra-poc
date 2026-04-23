"""Lead defense counsel summary (`cases[].attorney`)."""

from pydantic import BaseModel


class Attorney(BaseModel):
    attorneyId: int
    name: str
    city: str
    state: str
