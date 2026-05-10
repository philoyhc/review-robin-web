from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AssignmentMode(str, Enum):
    manual = "manual"
    rule_based = "rule_based"


class ManualAssignmentRow(BaseModel):
    """Manual-CSV import row. 15D PR 6b retired the per-row
    ``pair_context_*`` / ``assignment_context_*`` slots alongside the
    ``Assignment.context`` JSON column drop. Per-pair tags now live
    on the ``relationships`` table; assignment-level context retired
    entirely (no remaining tenants)."""

    reviewer_id: int
    reviewee_id: int
    reviewer_email: str
    reviewer_name: str
    reviewee_identifier: str
    reviewee_name: str
    include: bool = True
