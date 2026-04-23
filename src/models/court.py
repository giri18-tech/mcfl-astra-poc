"""Court / jurisdiction block on a case (`cases[].court`)."""

from pydantic import BaseModel

from models.court_state import CourtState


class Court(BaseModel):
    courtId: int
    name: str
    isFederal: bool
    # State is omitted for some federal-only dockets; keep optional for flexibility.
    state: CourtState | None = None
