"""Readiness-report fixtures, shared by the parity golden and the
duplicate-query guard (19R Item 5).

A `_`-prefixed helper imported relatively, per the convention
`_full_matrix.py` sets: a bare `pytest` run puts nothing on `sys.path`,
so an absolute `from tests.…` import fails collection.

Each scenario builds one session from ORM rows rather than through the
import endpoints — the rules under test read the database, and going
through the CSV importers would pin their normalisation here too.
Between them the six cover 19 of the 22 registered rules; the three
they miss are the two `session.*` checks, which read no database, and
the inert `instruments.no_rule_pinned`.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)



def _owner(db: Session, code: str) -> User:
    """One operator row per scenario — `sessions.created_by_user_id` is
    NOT NULL, and nothing under test reads the user. The email carries
    the session code so that a caller building several scenarios in one
    transaction does not trip `users.email`'s uniqueness."""
    user = User(email=f"{code}@example.edu", display_name="Par")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str, **kwargs: object) -> ReviewSession:
    review_session = ReviewSession(
        name=code.title(),
        code=code,
        status="draft",
        created_by_user_id=_owner(db, code).id,
        **kwargs,
    )
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(db: Session, session_id: int, name: str, order: int = 0) -> Instrument:
    instrument = Instrument(session_id=session_id, name=name, order=order)
    db.add(instrument)
    db.flush()
    return instrument


def _response_field(
    db: Session, instrument_id: int, *, key: str = "score", visible: bool = True
) -> None:
    db.add(
        InstrumentResponseField(
            instrument_id=instrument_id,
            field_key=key,
            label=key.title(),
            visible=visible,
        )
    )


def _display_field(db: Session, instrument_id: int) -> None:
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument_id,
            label="Name",
            source_type="reviewee",
            source_field="name",
        )
    )


def _build_bare_draft(db: Session) -> ReviewSession:
    """Nothing set up at all — every empty-roster error fires."""
    return _session(db, code="par-bare")


def _build_no_help_contact_only(db: Session) -> ReviewSession:
    """Rosters and one fully configured instrument, never generated."""
    review_session = _session(db, code="par-clean", help_contact="help@example.edu")
    db.add(Reviewer(session_id=review_session.id, name="Ana", email="ana@example.edu"))
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Ben",
            email_or_identifier="ben@example.edu",
        )
    )
    db.flush()
    instrument = _instrument(db, review_session.id, "I1")
    _response_field(db, instrument.id)
    _display_field(db, instrument.id)
    db.flush()
    return review_session


def _build_duplicates_and_identity(db: Session) -> ReviewSession:
    """Duplicate emails on two rosters, one cross-roster name
    disagreement, and a reviewee with no deliverable email."""
    review_session = _session(db, code="par-dupes")
    db.add_all(
        [
            Reviewer(session_id=review_session.id, name="Ana", email="ana@example.edu"),
            Reviewer(session_id=review_session.id, name="Ana", email="ANA@example.edu"),
            Reviewer(session_id=review_session.id, name="Cal", email="cal@example.edu"),
        ]
    )
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Cal Other",
                email_or_identifier="cal@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Anon",
                email_or_identifier="anon-0042",
            ),
            # Also unreachable, but inactive — so the W8 warning must
            # not count it. The only row in any scenario whose
            # `status` is not the default, and the reason
            # `ValidationInputs.active_reviewees` filters rather than
            # handing the whole roster over.
            Reviewee(
                session_id=review_session.id,
                name="Gone",
                email_or_identifier="anon-0043",
                status="inactive",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Dee",
                email_or_identifier="dee@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Dee",
                email_or_identifier="DEE@example.edu",
            ),
        ]
    )
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="obs@example.edu",
                display_name="Obs",
            ),
            # Differing only in case: `uq_observer_session_email` is
            # case-sensitive on the stored column, `normalize_email`
            # is not — which is the gap the duplicate rule exists to
            # report.
            Observer(
                session_id=review_session.id,
                email="OBS@example.edu",
                display_name="Obs",
            ),
            # Disagrees with the reviewer of the same mailbox, so the
            # observers side of the cross-roster rule fires too.
            Observer(
                session_id=review_session.id,
                email="ana@example.edu",
                display_name="Ana Other",
            ),
        ]
    )
    db.flush()
    instrument = _instrument(db, review_session.id, "I1")
    _response_field(db, instrument.id)
    _display_field(db, instrument.id)
    db.flush()
    return review_session


def _build_instrument_field_gaps(db: Session) -> ReviewSession:
    """One instrument with no response fields, one with response fields
    but no display fields, one whose only response field is hidden."""
    review_session = _session(db, code="par-fields", help_contact="h@example.edu")
    db.add(Reviewer(session_id=review_session.id, name="Ana", email="ana@example.edu"))
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Ben",
            email_or_identifier="ben@example.edu",
        )
    )
    db.flush()
    _instrument(db, review_session.id, "No fields", order=0)
    with_response = _instrument(db, review_session.id, "No display", order=1)
    _response_field(db, with_response.id)
    hidden = _instrument(db, review_session.id, "Hidden only", order=2)
    _response_field(db, hidden.id, visible=False)
    _display_field(db, hidden.id)
    db.flush()
    return review_session


def _build_single_instrument_generated(db: Session) -> ReviewSession:
    """One instrument, two reviewers, rows for only one of them."""
    review_session = _session(
        db,
        code="par-single",
        help_contact="h@example.edu",
        assignment_mode="rule_based",
    )
    covered = Reviewer(
        session_id=review_session.id, name="Ana", email="ana@example.edu"
    )
    missing = Reviewer(
        session_id=review_session.id, name="Cal", email="cal@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Ben",
        email_or_identifier="ben@example.edu",
    )
    db.add_all([covered, missing, reviewee])
    db.flush()
    instrument = _instrument(db, review_session.id, "I1")
    _response_field(db, instrument.id)
    _display_field(db, instrument.id)
    db.flush()
    db.add(
        Assignment(
            session_id=review_session.id,
            reviewer_id=covered.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="rule_based",
        )
    )
    db.flush()
    return review_session


def _build_multi_instrument_gaps(db: Session) -> ReviewSession:
    """Three instruments: one with rows, one with rows nobody includes,
    one with no rows at all."""
    review_session = _session(
        db,
        code="par-multi",
        help_contact="h@example.edu",
        assignment_mode="rule_based",
    )
    reviewer = Reviewer(
        session_id=review_session.id, name="Ana", email="ana@example.edu"
    )
    # No rows anywhere, so the per-instrument reviewer-missing rule
    # fires on every instrument that does have rows.
    db.add(
        Reviewer(
            session_id=review_session.id, name="Cal", email="cal@example.edu"
        )
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Ben",
        email_or_identifier="ben@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    included = _instrument(db, review_session.id, "Included", order=0)
    excluded = _instrument(db, review_session.id, "Excluded", order=1)
    empty = _instrument(db, review_session.id, "Empty", order=2)
    for instrument in (included, excluded, empty):
        _response_field(db, instrument.id)
        _display_field(db, instrument.id)
    db.flush()
    db.add_all(
        [
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=included.id,
                include=True,
                created_by_mode="rule_based",
            ),
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=excluded.id,
                include=False,
                created_by_mode="rule_based",
            ),
        ]
    )
    db.flush()
    return review_session


SCENARIOS: dict[str, Callable[[Session], ReviewSession]] = {
    "bare_draft": _build_bare_draft,
    "configured_never_generated": _build_no_help_contact_only,
    "duplicates_and_identity": _build_duplicates_and_identity,
    "instrument_field_gaps": _build_instrument_field_gaps,
    "single_instrument_generated": _build_single_instrument_generated,
    "multi_instrument_gaps": _build_multi_instrument_gaps,
}