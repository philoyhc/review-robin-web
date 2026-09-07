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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer
from app.services.email_identity import looks_like_email, normalize_email

#: The three participant roles a person can hold on a session roster.
#: Names match the audience constants in ``app/web/views/_guide.py``;
#: they are the same vocabulary, and a rename has to move together.
REVIEWER = "reviewer"
OBSERVER = "observer"
REVIEWEE = "reviewee"


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


def roles_held_anywhere(db: Session, email: str | None) -> frozenset[str]:
    """Which participant roles this email holds in **any** session.

    The workspace-level counterpart to the three per-session gates in
    ``app/web/deps.py`` (``require_reviewer_in_session`` and siblings),
    which answer the same question for one session. Those gates decide
    access; this decides only what documentation a viewer is shown, so
    it is deliberately *not* a permission check and grants nothing.

    It applies the gates' rules, though, and must keep doing so: an
    active row, case-insensitive email equality, and — for reviewees —
    the :func:`is_email_identified` predicate, so a reviewee carried
    under a non-email identifier is no more a "reviewee" here than they
    are at the results gate they could never pass. Diverging would tell
    someone the app has a page for them that will 403.

    An empty or unparseable email holds nothing: a viewer the app cannot
    identify is not silently everyone.
    """
    normalized = normalize_email(email)
    if not normalized or not looks_like_email(normalized):
        return frozenset()

    held: set[str] = set()

    if db.execute(
        select(Reviewer.id)
        .where(func.lower(Reviewer.email) == normalized)
        .where(Reviewer.status == "active")
        .limit(1)
    ).first():
        held.add(REVIEWER)

    if db.execute(
        select(Observer.id)
        .where(func.lower(Observer.email) == normalized)
        .where(Observer.status == "active")
        .limit(1)
    ).first():
        held.add(OBSERVER)

    # Reviewees are filtered in Python rather than SQL because
    # ``is_email_identified`` is the gate's own predicate and the point
    # is to run *that*, not a re-derivation of it. The scan is over rows
    # already narrowed to this exact address, so it is a handful at most.
    reviewees = db.execute(
        select(Reviewee)
        .where(func.lower(Reviewee.email_or_identifier) == normalized)
        .where(Reviewee.status == "active")
    ).scalars()
    if any(is_email_identified(r) for r in reviewees):
        held.add(REVIEWEE)

    return frozenset(held)
