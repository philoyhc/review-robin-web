from __future__ import annotations

from pydantic import BaseModel


class ResponseUpsert(BaseModel):
    """A single (assignment, field) cell from a reviewer's saved form."""

    assignment_id: int
    field_key: str
    value: str
