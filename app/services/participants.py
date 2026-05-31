"""Participant-model support helpers — Phase 1 dead-code stubs.

Lands the public surface (function names, signatures, return
types) the later participant-model slices will consume, so each
slice is a one-line wire-up rather than its own design call. No
caller in this PR; integration coverage arrives with the surfaces
in Phase 2 / Phase 3.

See ``guide/participant_model_upgrade.md`` §3.2, §5 and
``guide/participant_model_prep.md`` rows W1, W4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, Reviewee, User


# Same shape as the reviewer-side ``_EMAIL_RE`` in
# ``app/services/reviewers.py``. Duplicated rather than imported
# because the reviewer copy is a module-private (underscore-
# prefixed) constant. If the two ever need to diverge, the
# divergence is intentional; if not, this is a two-line drift
# risk worth accepting for the boundary cleanliness.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_email_identified(reviewee: Reviewee) -> bool:
    """Return True iff this reviewee's identifier parses as a
    valid email — the surface-gating predicate for
    ``/me/sessions/{id}/results``.

    A reviewee whose ``email_or_identifier`` value is a non-email
    identifier (or empty / whitespace) cannot authenticate
    against an inbox, so the results surface stays unavailable
    by construction. This is the helper §3.2 describes — no
    schema change required; the existing ``email_or_identifier``
    column already carries the value to test.
    """
    value = (reviewee.email_or_identifier or "").strip()
    return bool(_EMAIL_RE.fullmatch(value))


@dataclass(frozen=True)
class ParticipantSession:
    """One row of the unified ``/me/`` lobby table — a session
    the signed-in identity touches in one or more participant
    roles, with the role-pill flags driving the table render.

    Shape stable from Phase 1; the lobby slice (Phase 3 W18)
    populates instances by unioning reviewers / email-identified
    reviewees / observers for the user.
    """

    review_session: ReviewSession
    is_reviewer: bool
    is_reviewee: bool
    is_observer: bool


def sessions_for_user(
    user: User, db: Session
) -> list[ParticipantSession]:
    """Cross-role lobby query — returns every session the user
    touches as reviewer, reviewee, or observer, each row tagged
    with role-pill flags.

    Phase 1 stub returns an empty list; the real union query
    (reviewers / email-identified reviewees / observers, all
    matched case-insensitively on email) lands with the lobby
    slice (W18). The signature is stable from this point so the
    consumer can wire against it without rework.
    """
    # Intentional empty-list stub — callers should not exist
    # yet. The ``db`` parameter is kept on the signature so the
    # slice that lights this up doesn't need to change call
    # sites.
    del user, db
    return []
