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

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession
from app.services import visibility_policies
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


def disclosable_roles(db: Session, email: str | None) -> frozenset[str]:
    """Which participant roles may be *disclosed* to this viewer,
    across every session.

    **Renamed from ``roles_held_anywhere`` at Segment 19F PR 3**, and
    the rename is the point: the reviewee arm stopped answering "holds
    the role" and started answering "may be told they hold it". A name
    that promised the weaker thing while doing the stronger one is the
    trap this segment keeps finding.

    Used only to decide what documentation a viewer is shown on
    ``/guide``. It is deliberately **not** a permission check and grants
    nothing; the per-session gates in ``app/web/deps.py`` decide access.

    The three roles are treated asymmetrically, and the asymmetry is
    19F's decisions 2–4 rather than an inconsistency:

    * **reviewer** and **observer** — disclosable on an active roster
      row alone. Being asked to review, or appointed to observe, is not
      a disclosure *about* the person; they are entitled to know it
      before any window opens.
    * **reviewee** — disclosable only where a grant currently resolves
      (:func:`visibility_policies.reviewee_has_current_grant`) on at
      least one session they are on. For a reviewee, *membership itself
      is the disclosure*: telling them the app has a "For reviewees"
      page is telling them they are being reviewed. Someone with no
      current grant holds no reviewee role here, exactly as they now
      reach no ``/results``.

    The gates' other rules still apply throughout: active rows,
    case-insensitive email equality, and :func:`is_email_identified` for
    reviewees, so someone carried under a non-email identifier is no
    more a reviewee here than at the gate they could never pass.

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

    # Reviewees are filtered in Python rather than SQL for two reasons:
    # ``is_email_identified`` is the gate's own predicate and the point
    # is to run *that* rather than a re-derivation of it, and the grant
    # check is a per-session resolution the query cannot express. The
    # scan is over rows already narrowed to this exact address, so it is
    # a handful at most, and ``any`` short-circuits on the first session
    # that grants something.
    reviewee_rows = db.execute(
        select(Reviewee, ReviewSession)
        .join(ReviewSession, ReviewSession.id == Reviewee.session_id)
        .where(func.lower(Reviewee.email_or_identifier) == normalized)
        .where(Reviewee.status == "active")
    ).all()
    if any(
        is_email_identified(reviewee)
        and visibility_policies.reviewee_has_current_grant(
            db, review_session
        )
        for reviewee, review_session in reviewee_rows
    ):
        held.add(REVIEWEE)

    return frozenset(held)
