"""US state metadata nested under `cases[].court.state`."""

from pydantic import BaseModel


class CourtState(BaseModel):
    name: str
    abbreviation: str
