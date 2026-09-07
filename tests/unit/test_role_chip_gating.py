"""Unit tests for the two conditions 19F PR 7 put on
``build_role_chips``.

The chip strip is the second door onto a role. ``_dashboard.py`` had
carried the segment's gating since PR 2, but a chip is built by a
different function on a different surface, and it was still answering
from roster membership alone — so a reviewee with nothing granted, who
reached ``/collation`` as an observer, was told there that they are a
reviewee, and handed a link that 404s.

The integration tests in ``test_me_surface_role_chips.py`` pin what a
page renders. These pin the builder's own two conditions, one of which
(the archived observer) no participant surface can reach: archive
closes the reviewee grant, so ``/results`` 404s, and on ``/collation``
the observer chip is the *active* one and carries no link either way.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    Observer,
    Reviewee,
    ReviewSession,
    User,
)
from app.services import visibility_policies
from app.web.routes_reviewer._shared import build_role_chips


def _user(db: Session, *, email: str = "alice@example.edu") -> User:
    user = User(email=email, display_name="Alice")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str, status: str = "ready") -> ReviewSession:
    creator = User(email=f"{code}@example.edu", display_name="Creator")
    db.add(creator)
    db.flush()
    review_session = ReviewSession(
        name="S", code=code, status=status, created_by_user_id=creator.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _grant_reviewee_view(db: Session, review_session: ReviewSession) -> None:
    """Open an ``after_release`` grant for the reviewee audience.

    The integration suite's ``grant_reviewee_visibility`` fixture does
    this; it lives in ``tests/integration/conftest.py`` and the unit
    tree does not see it. Since 19F PR 2a the window needs the session
    ``expired`` as well as the anchor reached."""
    instrument = Instrument(session_id=review_session.id, name="I1", order=1)
    db.add(instrument)
    db.flush()
    granularity, identification = visibility_policies.MODE_LABELS["raw"]
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    review_session.status = "expired"
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    review_session.responses_release_until = None
    db.flush()


def _chip(chips: list[dict[str, object]], role: str) -> dict[str, object] | None:
    return next((c for c in chips if c["role"] == role), None)


def test_reviewee_chip_absent_without_a_grant(db: Session) -> None:
    user = _user(db)
    review_session = _session(db, code="chip-u-nogrant")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier=user.email,
        )
    )
    db.add(
        Observer(
            session_id=review_session.id,
            email=user.email,
            display_name="Alice",
        )
    )
    db.flush()
    chips = build_role_chips(
        db, user=user, review_session=review_session, active_role="observer"
    )
    # Absent, not disabled: a greyed chip still discloses the role.
    assert _chip(chips, "reviewee") is None
    assert _chip(chips, "observer") is not None


def test_reviewee_chip_present_once_a_grant_resolves(db: Session) -> None:
    user = _user(db)
    review_session = _session(db, code="chip-u-grant")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier=user.email,
        )
    )
    db.add(
        Observer(
            session_id=review_session.id,
            email=user.email,
            display_name="Alice",
        )
    )
    db.flush()
    _grant_reviewee_view(db, review_session)
    chips = build_role_chips(
        db, user=user, review_session=review_session, active_role="observer"
    )
    reviewee = _chip(chips, "reviewee")
    assert reviewee is not None
    assert reviewee["enabled"] is True
    assert reviewee["target"] == f"/me/sessions/{review_session.id}/results"


def test_observer_chip_greys_on_an_archived_session(db: Session) -> None:
    """Disabled, not dropped — the mirror image of the reviewee rule.

    Being an observer is not a disclosure about the observer (19F
    decision 4), so the chip stays visible; archive closes the grant, so
    the page behind it is empty and the link goes."""
    user = _user(db)
    review_session = _session(db, code="chip-u-arch", status="archived")
    db.add(
        Observer(
            session_id=review_session.id,
            email=user.email,
            display_name="Alice",
        )
    )
    db.flush()
    chips = build_role_chips(
        db, user=user, review_session=review_session, active_role="reviewer"
    )
    observer = _chip(chips, "observer")
    assert observer is not None
    assert observer["enabled"] is False


def test_observer_chip_live_on_an_unarchived_session(db: Session) -> None:
    user = _user(db)
    review_session = _session(db, code="chip-u-live")
    db.add(
        Observer(
            session_id=review_session.id,
            email=user.email,
            display_name="Alice",
        )
    )
    db.flush()
    chips = build_role_chips(
        db, user=user, review_session=review_session, active_role="reviewer"
    )
    observer = _chip(chips, "observer")
    assert observer is not None
    assert observer["enabled"] is True
