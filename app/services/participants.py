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

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession
from app.services import visibility_policies
from app.services.email_identity import (
    looks_like_email,
    normalize_email,
    normalize_object_id,
    same_identity,
)
from app.services.session_lifecycle import SessionStatus

_ARCHIVED = SessionStatus.archived.value

#: The three participant roles a person can hold on a session roster.
#: Names match the audience constants in ``app/web/views/_guide.py``;
#: they are the same vocabulary, and a rename has to move together.
REVIEWER = "reviewer"
OBSERVER = "observer"
REVIEWEE = "reviewee"


@dataclass(frozen=True)
class Viewer:
    """Who a roster row is matched against (segment 21F): the signed-in
    person's mail, folded, and the principal ID of **this request's**
    sign-in, folded, never the one stored on ``users``: a row found by
    email can carry an earlier holder's (Codex, #3424). ``None`` for no
    principal, and for the fake user, whose ID is one shared constant."""

    email: str
    principal_id: str | None = None

    @classmethod
    def of(cls, user: Any) -> Viewer:
        """The viewer behind a ``users`` row, with the principal ID
        `get_or_create_user` stamped on it for this request."""
        return cls.from_parts(
            getattr(user, "email", None), getattr(user, "signed_in_principal_id", None)
        )

    @classmethod
    def from_parts(cls, email: str | None, principal_id: str | None = None) -> Viewer:
        principal = normalize_object_id(principal_id) or None
        return cls(email=normalize_email(email), principal_id=principal)

    def matches(self, row: Any, address: str | None) -> bool:
        """Whether ``row`` (its ``address`` as written) is this viewer's.
        A row bound to a directory account is the account's alone; any
        other row matches by mail, as before segment 21F."""
        bound = normalize_object_id(getattr(row, "directory_object_id", None))
        if bound:
            return self.principal_id is not None and bound == self.principal_id
        return bool(self.email) and normalize_email(address) == self.email

    def clause(self, model: Any, address_column: Any) -> Any:
        """`matches` as a SQL condition on ``model``'s rows."""
        by_mail = and_(
            model.directory_object_id.is_(None),
            func.lower(func.trim(address_column)) == normalize_email(self.email),
        )
        if self.principal_id is None:
            return by_mail
        by_account = func.lower(model.directory_object_id) == self.principal_id
        return or_(by_account, by_mail)


def same_person(a: Any, a_address: str | None, b: Any, b_address: str | None) -> bool:
    """Whether two roster rows name one person: `email_identity.same_identity`
    on their accounts and addresses (segment 21F)."""
    return same_identity(
        getattr(a, "directory_object_id", None), a_address, getattr(b, "directory_object_id", None), b_address
    )


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


def disclosable_roles(
    db: Session,
    email: str | None,
    *,
    principal_id: str | None = None,
    session_id: int | None = None,
) -> frozenset[str]:
    """Which participant roles may be *disclosed* to this viewer,
    across every session, or on one session when ``session_id`` is
    given.

    **Renamed from ``roles_held_anywhere`` at Segment 19F PR 3**, and
    the rename is the point: the reviewee arm stopped answering "holds
    the role" and started answering "may be told they hold it". A name
    that promised the weaker thing while doing the stronger one is the
    trap this segment keeps finding.

    Used to decide what documentation a viewer is shown on ``/guide``
    and, per session, whether a back link may name a session
    (``permissions.may_name_session``). It is deliberately **not** a permission
    check and grants nothing; the per-session gates in
    ``app/web/deps.py`` decide access.

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
    # Segment 21F: a row bound to a directory account matches that
    # account's principal; any other row, the mail.
    viewer = Viewer.from_parts(email, principal_id)

    held: set[str] = set()

    # An archived session is off limits to every participant (author's
    # ruling 2026-10-16), so it discloses no role: the Guide skips its
    # cards and a back link never names it. (Reviewees already drop out
    # there: archive closes every grant.)
    reviewer_query = (
        select(Reviewer.id)
        .join(ReviewSession, ReviewSession.id == Reviewer.session_id)
        .where(viewer.clause(Reviewer, Reviewer.email))
        .where(Reviewer.status == "active")
        .where(ReviewSession.status != _ARCHIVED)
    )
    observer_query = (
        select(Observer.id)
        .join(ReviewSession, ReviewSession.id == Observer.session_id)
        .where(viewer.clause(Observer, Observer.email))
        .where(Observer.status == "active")
        .where(ReviewSession.status != _ARCHIVED)
    )
    if session_id is not None:
        reviewer_query = reviewer_query.where(Reviewer.session_id == session_id)
        observer_query = observer_query.where(Observer.session_id == session_id)

    if db.execute(reviewer_query.limit(1)).first():
        held.add(REVIEWER)

    if db.execute(observer_query.limit(1)).first():
        held.add(OBSERVER)

    # Reviewees are filtered in Python rather than SQL for two reasons:
    # ``is_email_identified`` is the gate's own predicate and the point
    # is to run *that* rather than a re-derivation of it, and the grant
    # check is a per-session resolution the query cannot express. The
    # scan is over rows already narrowed to this exact address, so it is
    # a handful at most, and ``any`` short-circuits on the first session
    # that grants something.
    reviewee_query = (
        select(Reviewee, ReviewSession)
        .join(ReviewSession, ReviewSession.id == Reviewee.session_id)
        .where(viewer.clause(Reviewee, Reviewee.email_or_identifier))
        .where(Reviewee.status == "active")
    )
    if session_id is not None:
        reviewee_query = reviewee_query.where(Reviewee.session_id == session_id)
    reviewee_rows = db.execute(reviewee_query).all()
    if any(
        is_email_identified(reviewee)
        and visibility_policies.reviewee_has_current_grant(
            db, review_session
        )
        for reviewee, review_session in reviewee_rows
    ):
        held.add(REVIEWEE)

    return frozenset(held)
