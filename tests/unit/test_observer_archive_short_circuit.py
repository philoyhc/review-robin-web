"""The observer collation view's archive short-circuit (19F PR 5).

**Why this file exists, given the outcome is already guaranteed
elsewhere.** Until 19F PR 2a, `build_observer_collation_context`
resolved a *live* grant on an archived session — the divergence
`spec/role_landing_and_visibility.md` §6 recorded, verified returning
`"raw"`. PR 2a closed it by a different route: the after-release window
now requires `status = "expired"`, and archived is not expired, so both
window booleans come back False without the short-circuit doing
anything.

That makes the archive rule **emergent** — it holds only while two
*other* predicates keep refusing archived sessions, which is a property
of `session_lifecycle`, not of this view. The short-circuit states it
locally so it survives a future relaxation of either.

The second test below is the one that can actually fail if the
short-circuit is deleted: it simulates exactly that relaxation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    Observer,
    ReviewSession,
    User,
)
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
from app.web.views import _observer_collation
from app.web.views._observer_collation import (
    build_observer_collation_context,
)


def _seeded(db: Session, *, status: str) -> tuple[Observer, ReviewSession]:
    creator = User(email=f"obs-{status}@example.edu", display_name="Op")
    db.add(creator)
    db.flush()
    review_session = ReviewSession(
        name="S", code=f"obs-arch-{status}", status=status,
        created_by_user_id=creator.id,
        responses_release_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(review_session)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id, name="Form", order=1
    )
    db.add(instrument)
    db.flush()
    granularity, identification = visibility_policies.MODE_LABELS["raw"]
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="observer",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    observer = Observer(
        session_id=review_session.id,
        email="obs@example.edu",
        display_name="Obs",
        # A *non-empty* rule matters: `observer_has_rule` returns
        # False on an empty `rules` list and the view returns before
        # the archive branch, which would make every test here pass
        # vacuously. (It did, on the first draft.)
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "cohort-a",
                }
            ],
        },
    )
    db.add(observer)
    db.flush()
    return observer, review_session


def test_an_archived_session_yields_no_sections(db: Session) -> None:
    """The contract, whichever mechanism enforces it. Passes today with
    or without the short-circuit — that is the point of the next test,
    not a flaw in this one."""
    observer, review_session = _seeded(db, status="archived")
    context = build_observer_collation_context(
        db, observer=observer, review_session=review_session
    )
    assert context.sections == []


def test_the_short_circuit_holds_even_if_a_window_predicate_relaxes(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The short-circuit's actual job, and the only way to see it fail.

    Simulate the future in which someone relaxes a window predicate so
    that it admits an archived session — exactly the change the
    short-circuit is insurance against. With it, the view still refuses;
    without it, an archived session resolves `"raw"` again and §6's
    divergence comes back.
    """
    observer, review_session = _seeded(db, status="archived")
    monkeypatch.setattr(
        lifecycle, "is_response_release_window_open", lambda s, **kw: True
    )
    monkeypatch.setattr(
        _observer_collation.lifecycle,
        "is_response_release_window_open",
        lambda s, **kw: True,
    )
    context = build_observer_collation_context(
        db, observer=observer, review_session=review_session
    )
    assert context.sections == []


def test_archive_does_not_claim_the_cohort_is_unconfigured(
    db: Session,
) -> None:
    """The short-circuit returns ``cohort_empty=False``, and the value
    matters: ``True`` makes the template render *"No cohort is
    configured for you yet — the session operator assigns observers to
    cohorts…"*, which blames the operator for something that **is**
    configured. With ``False`` the page falls through to *"No
    instruments are visible to observers in the current session
    window"*, which is true of an archived session.

    The positive control for "non-archived still works" is the
    integration test
    ``test_observer_collation_body.py::test_collation_renders_after_release_section_when_window_open``
    — it builds a real cohort with real assignments, which is what a
    rendering section needs and what this unit file deliberately does
    not rebuild.
    """
    observer, review_session = _seeded(db, status="archived")
    context = build_observer_collation_context(
        db, observer=observer, review_session=review_session
    )
    assert context.cohort_empty is False
