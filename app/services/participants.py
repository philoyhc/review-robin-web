"""Participant-model support helpers.

Owns the participant-side predicates that the route guards and
surfaces call into. Previously also held a shape-only
``sessions_for_user`` / ``ParticipantSession`` stub for the W4
cross-role lobby query — that retired 2026-06-01 when the W18
implementation chose to build the union inline in
``app/web/routes_reviewer/_dashboard.py`` rather than route
through the stub (see L1 in the participant-model remainder
doc, now closed).

See ``guide/archive/participant_model_upgrade.md`` §3.2 (and Appendix A
row W1).
"""

from __future__ import annotations

from app.db.models import Reviewee
from app.services.email_identity import looks_like_email


def is_email_identified(reviewee: Reviewee) -> bool:
    """Return True iff this reviewee's identifier parses as a
    valid email — the surface-gating predicate for
    ``/me/sessions/{id}/results``.

    A reviewee whose ``email_or_identifier`` value is a non-email
    identifier (or empty / whitespace) cannot authenticate
    against an inbox, so the results surface stays unavailable
    by construction. This is the helper §3.2 describes — no
    schema change required; the existing ``email_or_identifier``
    column already carries the value to test. Delegates to the
    canonical :func:`app.services.email_identity.looks_like_email`.
    """
    return looks_like_email(reviewee.email_or_identifier)
