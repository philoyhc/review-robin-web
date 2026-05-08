"""Responses page row builder — Segment 11C Part 1's reviewee-
centric coverage view at ``/operator/sessions/{id}/responses``.

Slice 1 of the §12.B ladder (``guide/major_refactor.md``).

Owns the ``ResponsesRow`` dataclass and the ``build_responses_rows``
adapter that translates ``monitoring.per_reviewee_coverage(...)``
into the row tuples the template iterates over. Filter / search
helpers (`filter_responses_rows`, `responses_search_options`) and
the related `RESPONSES_STATUS_OPTIONS` constant live in
``_filters.py`` (PR 4) — they're shared between Responses and
Invitations.

Source range in pre-PR-1 ``_legacy.py``: lines 1537-1570.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession
from app.services import monitoring


@dataclass(frozen=True)
class ResponsesRow:
    reviewee: Reviewee
    coverage_state: str
    """``"complete"`` / ``"adequate"`` / ``"at risk"`` / ``"no responses"``"""
    reviewers_done: int
    reviewers_total: int
    last_response_at: datetime | None

    @property
    def is_at_risk(self) -> bool:
        return self.coverage_state in ("at risk", "no responses")


def build_responses_rows(
    db: Session, review_session: ReviewSession
) -> list[ResponsesRow]:
    coverage = monitoring.per_reviewee_coverage(db, review_session)
    return [
        ResponsesRow(
            reviewee=c.reviewee,
            coverage_state=c.pill_state,
            reviewers_done=c.completed_count,
            reviewers_total=c.reviewer_count,
            last_response_at=c.last_response_at,
        )
        for c in coverage
    ]
