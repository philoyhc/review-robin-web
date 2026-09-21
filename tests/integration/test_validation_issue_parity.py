"""The readiness report's issue list, pinned rule for rule (19R Item 5).

Item 5 rung 2 moved every input more than one check loaded into a
per-run `ValidationInputs` object, so twenty-two checks stopped each
deciding for themselves what "the session's instruments" means. That is
a refactor of *how* the report is computed and must not change *what*
it reports.

This file is the pin. `EXPECTED` was captured from the implementation
**before** the refactor (`_dump()` below, run against `origin/main`)
and committed unchanged, so a run that agrees with it is agreeing with
the pre-refactor behavior and not with itself. It stays useful
afterwards as the golden for every later change to a check.

Each scenario is built from ORM rows rather than the import endpoints:
the rules under test read the database, and going through the CSV
importers would pin their normalisation here too.

To re-capture after a deliberate copy or rule change:

    RRW_VALIDATION_PARITY_DUMP=/tmp/parity.json pytest \
        tests/integration/test_validation_issue_parity.py

then copy the file over `_validation_issue_parity.json`.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import select
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
from app.services.validation import validate_session_setup


# --------------------------------------------------------------------------- #
# Scenario builders
# --------------------------------------------------------------------------- #


def _owner(db: Session) -> User:
    """One operator row per scenario — `sessions.created_by_user_id` is
    NOT NULL, and nothing under test reads the user."""
    user = User(email="par@example.edu", display_name="Par")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str, **kwargs: object) -> ReviewSession:
    review_session = ReviewSession(
        name=code.title(),
        code=code,
        status="draft",
        created_by_user_id=_owner(db).id,
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


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #


#: ``(prefix as it appears in a `field` / `fix_anchor` string, the
#: model whose rows it numbers)``. Both spellings of each entity are
#: listed because `field` uses ``reviewer_id:3`` where `fix_anchor`
#: uses ``#reviewer-row-3``.
_ID_PREFIXES: tuple[tuple[str, type], ...] = (
    ("reviewer-row-", Reviewer),
    ("reviewer_id:", Reviewer),
    ("reviewee-row-", Reviewee),
    ("reviewee_id:", Reviewee),
    ("observer-row-", Observer),
    ("instrument-", Instrument),
    ("instrument_id:", Instrument),
)


def _ordinals(db: Session, review_session: ReviewSession) -> dict[tuple[str, int], int]:
    """Map each ``(prefix, row id)`` to the row's 1-based position in
    its own table for this session.

    Absolute ids cannot be pinned: SQLite hands back the ids an earlier
    rolled-back test released, Postgres sequences do not rewind, so the
    same scenario is `#reviewer-row-2` on one dialect and
    `#reviewer-row-9` on the other. The position is the thing the
    assertion actually means — *which* of this session's reviewers the
    issue points at — and it is the same number everywhere.
    """
    ordinals: dict[tuple[str, int], int] = {}
    for prefix, model in _ID_PREFIXES:
        rows = db.execute(
            select(model.id)
            .where(model.session_id == review_session.id)
            .order_by(model.id)
        ).scalars()
        for position, row_id in enumerate(rows, start=1):
            ordinals[(prefix, row_id)] = position
    return ordinals


def _to_ordinals(value: str | None, ordinals: dict[tuple[str, int], int]) -> str | None:
    if value is None:
        return None
    pattern = "|".join(re.escape(prefix) for prefix, _ in _ID_PREFIXES)
    return re.sub(
        rf"({pattern})(\d+)",
        lambda m: m.group(1) + str(ordinals[(m.group(1), int(m.group(2)))]),
        value,
    )


def _normalize(
    issues: list, db: Session, review_session: ReviewSession
) -> list[dict[str, object]]:
    """Issue order is part of the contract — the Validate page renders
    them in registry order — so this preserves it rather than sorting.

    Row references survive in `field` and `fix_anchor`, rewritten to
    positions by :func:`_ordinals`, because "which row" is exactly what
    a refactor of the loading can get wrong.
    """
    ordinals = _ordinals(db, review_session)
    return [
        {
            "rule_key": issue.rule_key,
            "severity": issue.severity.value,
            "source": issue.source,
            "field": _to_ordinals(issue.field, ordinals),
            "message": issue.message,
            "fix_anchor": _to_ordinals(issue.fix_anchor, ordinals),
        }
        for issue in issues
    ]


#: Captured from `origin/main` before the inputs object landed; see the
#: module docstring for how to re-capture it.
GOLDEN_PATH = Path(__file__).with_name("_validation_issue_parity.json")
EXPECTED: dict[str, list[dict[str, object]]] = json.loads(
    GOLDEN_PATH.read_text()
)

_DUMP_PATH = os.environ.get("RRW_VALIDATION_PARITY_DUMP")


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_issue_list_is_what_it_was_before_the_inputs_object(
    db: Session, name: str
) -> None:
    review_session = SCENARIOS[name](db)

    observed = _normalize(
        validate_session_setup(db, review_session), db, review_session
    )

    if _DUMP_PATH:
        _dump(name, observed)
        pytest.skip(f"dumped {name} to {_DUMP_PATH}")
    assert observed == EXPECTED[name]


def test_every_scenario_is_pinned() -> None:
    """A scenario added without a golden would otherwise pass by
    `KeyError`-ing in no test at all — the parametrize reads
    `SCENARIOS`, and a missing `EXPECTED` entry is the one failure
    shape that should not look like a fixture bug."""
    assert sorted(SCENARIOS) == sorted(EXPECTED)


def _dump(name: str, observed: list[dict[str, object]]) -> None:
    """Merge this scenario into the dump file, so one run over the
    whole parametrize builds the complete golden."""
    assert _DUMP_PATH is not None
    try:
        with open(_DUMP_PATH) as handle:
            existing = json.load(handle)
    except (OSError, json.JSONDecodeError):
        existing = {}
    existing[name] = observed
    with open(_DUMP_PATH, "w") as handle:
        json.dump(existing, handle, indent=4, sort_keys=True)
