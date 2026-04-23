"""Multi-district or consolidated proceeding metadata (`cases[].mdl`)."""

from pydantic import BaseModel


class MDL(BaseModel):
    mdlId: int
    name: str
    role: str
