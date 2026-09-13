"""The two pieces that left ``instruments_delete``'s route body.

`NF-22` asked whether route handlers holding SQL breaks the layering
rule. Most sites turned out to be scoped entity lookups — a route
resolving its own path parameter, which is not a business rule —
though not all of them: see `NF-25` for the ones that are neither
lookups nor fixed here. This route was the clearest case, carrying
both a domain rule (a session keeps at least one instrument) and a
navigation choice (where to land afterwards) inline.

The rule moved to ``instruments.delete_instrument``, so **any**
caller gets it rather than only the one that happened to check. The
navigation moved to the view seam, where `CLAUDE.md` puts anything
between a business rule and markup.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.services.instruments import (
    LastInstrumentError,
    delete_instrument,
    ensure_default_instrument,
)
from app.web import views


def _user(db: Session) -> User:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User, *, code: str = "del-seam") -> ReviewSession:
    s = ReviewSession(name="Test", code=code, created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _add_instrument(db: Session, session: ReviewSession, order: int) -> Instrument:
    instrument = Instrument(
        session_id=session.id,
        name=f"instrument_{order}",
        order=order,
        accepting_responses=False,
        responses_visible_when_closed=False,
    )
    db.add(instrument)
    db.flush()
    return instrument


# --------------------------------------------------------------------- #
# The floor rule now belongs to the service
# --------------------------------------------------------------------- #


def test_delete_instrument_refuses_the_last_one(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    only = ensure_default_instrument(db, session)
    db.flush()

    with pytest.raises(LastInstrumentError):
        delete_instrument(db, instrument=only, actor=user)


def test_the_refused_delete_mutates_nothing(db: Session) -> None:
    """The floor is checked before anything moves — notably before
    ``invalidate_if_validated``, which would otherwise flip a
    validated session back to draft on a delete that never happened.
    """
    user = _user(db)
    session = _session(db, user, code="del-seam-2")
    session.status = "validated"
    only = ensure_default_instrument(db, session)
    db.flush()

    with pytest.raises(LastInstrumentError):
        delete_instrument(db, instrument=only, actor=user)

    assert session.status == "validated"
    assert db.get(Instrument, only.id) is not None


def test_delete_instrument_allows_it_when_a_sibling_remains(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="del-seam-3")
    first = ensure_default_instrument(db, session)
    second = _add_instrument(db, session, order=1)
    db.flush()

    deleted_id = delete_instrument(db, instrument=second, actor=user)

    assert deleted_id == second.id
    assert db.get(Instrument, first.id) is not None


# --------------------------------------------------------------------- #
# The landing anchor now belongs to the view seam
# --------------------------------------------------------------------- #


def test_landing_id_is_the_next_sibling(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="land-1")
    first = ensure_default_instrument(db, session)
    second = _add_instrument(db, session, order=1)
    third = _add_instrument(db, session, order=2)
    db.flush()

    assert (
        views.instrument_delete_landing_id(
            db, session_id=session.id, instrument_id=first.id
        )
        == second.id
    )
    assert (
        views.instrument_delete_landing_id(
            db, session_id=session.id, instrument_id=second.id
        )
        == third.id
    )


def test_landing_id_falls_back_to_the_previous_sibling_at_the_end(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="land-2")
    first = ensure_default_instrument(db, session)
    last = _add_instrument(db, session, order=1)
    db.flush()

    assert (
        views.instrument_delete_landing_id(
            db, session_id=session.id, instrument_id=last.id
        )
        == first.id
    )


def test_landing_id_is_none_for_a_lone_instrument(db: Session) -> None:
    """No neighbour to land on. The route renders the page top rather
    than an ``#instrument-None`` anchor — and this case is only
    reachable if the floor rule is ever relaxed."""
    user = _user(db)
    session = _session(db, user, code="land-3")
    only = ensure_default_instrument(db, session)
    db.flush()

    assert (
        views.instrument_delete_landing_id(
            db, session_id=session.id, instrument_id=only.id
        )
        is None
    )


def test_landing_id_is_none_for_an_id_outside_the_session(
    db: Session,
) -> None:
    """A stale id gets the page top, not an IndexError. The route
    body's old ``sibling_ids.index(instrument_id)`` would have
    raised."""
    user = _user(db)
    session = _session(db, user, code="land-4")
    ensure_default_instrument(db, session)
    other = _session(db, user, code="land-4-other")
    stranger = ensure_default_instrument(db, other)
    db.flush()

    assert (
        views.instrument_delete_landing_id(
            db, session_id=session.id, instrument_id=stranger.id
        )
        is None
    )
