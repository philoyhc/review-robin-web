from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AssignmentMode(str, Enum):
    full_matrix = "full_matrix"
    manual = "manual"
    rule_based = "rule_based"


class ManualAssignmentRow(BaseModel):
    reviewer_id: int
    reviewee_id: int
    reviewer_email: str
    reviewer_name: str
    reviewee_identifier: str
    reviewee_name: str
    include: bool = True
    context_1: str | None = None
    context_2: str | None = None
    context_3: str | None = None
