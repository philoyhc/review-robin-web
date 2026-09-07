"""Unit tests for ``visibility_policies.reviewee_has_current_grant``.

The Segment 19F predicate: *is there anything for a reviewee to see in
this session right now?* It gates their ``/me`` row (PR 2) and, from
PR 4, their ``/results`` surface — so the two agree by construction
rather than by two readings of the same rule.

The integration tests in ``test_me_dashboard_cross_role.py`` pin what a
reviewee *sees*; these pin the predicate's own edges, which a page test
would only reach indirectly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    ReviewSession,
    User,
)
from app.services import visibility_policies


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


def _instrument(db: Session, review_session: ReviewSession, *, order: int = 1) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id, name=f"I{order}", order=order
    )
    db.add(instrument)
    db.flush()
    return instrument


def _reviewee_policy(
    db: Session, instrument: Instrument, *, mode: str | None = "raw"
) -> InstrumentViewPolicy:
    granularity = identification = None
    if mode is not None:
        granularity, identification = visibility_policies.MODE_LABELS[mode]
    row = InstrumentViewPolicy(
        instrument_id=instrument.id,
        audience="reviewee",
        after_release_granularity=granularity,
        after_release_identification=identification,
    )
    db.add(row)
    db.flush()
    return row


def _open_release_window(review_session: ReviewSession) -> None:
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    review_session.responses_release_until = None


def test_no_instruments_means_no_grant(db: Session) -> None:
    review_session = _session(db, code="cg-empty")
    _open_release_window(review_session)
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_an_open_window_without_a_policy_row_is_not_a_grant(
    db: Session,
) -> None:
    """A missing row means "this audience cannot view this instrument",
    not "inherit something"."""
    review_session = _session(db, code="cg-norow")
    _instrument(db, review_session)
    _open_release_window(review_session)
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_a_policy_row_without_an_open_window_is_not_a_grant(
    db: Session,
) -> None:
    """Decision 1 — *currently* resolving, not ever-configured. This is
    the case the whole segment turns on: the operator has decided what
    reviewees will see, and has not yet let them see it."""
    review_session = _session(db, code="cg-nowindow")
    _reviewee_policy(db, _instrument(db, review_session))
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_one_open_instrument_out_of_several_is_enough(db: Session) -> None:
    """Per session, not per instrument. Ten instruments and one open
    grant is one visible row — the surface re-resolves per instrument
    when it renders, so the predicate does not need to say which."""
    review_session = _session(db, code="cg-any")
    _reviewee_policy(db, _instrument(db, review_session, order=1), mode=None)
    _reviewee_policy(db, _instrument(db, review_session, order=2), mode=None)
    _reviewee_policy(db, _instrument(db, review_session, order=3), mode="raw")
    _open_release_window(review_session)
    assert visibility_policies.reviewee_has_current_grant(db, review_session)


def test_every_instrument_off_is_not_a_grant(db: Session) -> None:
    review_session = _session(db, code="cg-alloff")
    for order in (1, 2):
        _reviewee_policy(
            db, _instrument(db, review_session, order=order), mode=None
        )
    _open_release_window(review_session)
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_archive_closes_the_grant(db: Session) -> None:
    """The archive override forces every non-operator audience off
    (``spec/visibility_policy.md``). It short-circuits ahead of the
    policy table, so an archived session answers False even with a row
    and an open window — which is what drops an archived session's
    reviewee row off ``/me``."""
    review_session = _session(db, code="cg-arch")
    _reviewee_policy(db, _instrument(db, review_session))
    _open_release_window(review_session)
    assert visibility_policies.reviewee_has_current_grant(db, review_session)

    review_session.status = "archived"
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_a_closed_release_window_retires_the_grant(db: Session) -> None:
    """An operator who stops the release takes the row back with it."""
    review_session = _session(db, code="cg-closed")
    _reviewee_policy(db, _instrument(db, review_session))
    now = datetime.now(timezone.utc)
    review_session.responses_release_at = now - timedelta(days=2)
    review_session.responses_release_until = now - timedelta(days=1)
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_another_audiences_grant_does_not_count(db: Session) -> None:
    """An observer grant on the same instrument is not a reviewee
    grant. Obvious, and worth pinning: the query filters on `audience`,
    and dropping that filter would pass every other test here."""
    review_session = _session(db, code="cg-otheraud")
    instrument = _instrument(db, review_session)
    granularity, identification = visibility_policies.MODE_LABELS["raw"]
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="observer",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    db.flush()
    _open_release_window(review_session)
    assert not visibility_policies.reviewee_has_current_grant(
        db, review_session
    )


def test_another_sessions_grant_does_not_count(db: Session) -> None:
    """The join filters on `Instrument.session_id`; without it a grant
    anywhere in the workspace would light up every reviewee row."""
    granted = _session(db, code="cg-elsewhere")
    _reviewee_policy(db, _instrument(db, granted))
    _open_release_window(granted)

    bare = _session(db, code="cg-bare")
    _instrument(db, bare)
    _open_release_window(bare)
    assert not visibility_policies.reviewee_has_current_grant(db, bare)
