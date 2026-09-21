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

The six scenarios live in `_validation_scenarios.py`, shared with the
duplicate-query guard in `test_readiness_report_cost.py`.

To re-capture after a deliberate copy or rule change:

    RRW_VALIDATION_PARITY_DUMP=/tmp/parity.json pytest \
        tests/integration/test_validation_issue_parity.py

then copy the file over `_validation_issue_parity.json` — the dump is
written in that file's own format, so a re-capture is a content diff
rather than a reformat.

`RRW_VALIDATION_PARITY_DUMP` turns every assertion below into a skip,
so it is a capture switch and never something CI sets.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services.validation import validate_session_setup
from ._validation_scenarios import SCENARIOS




# --------------------------------------------------------------------------- #
# Normalization
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
        json.dump(existing, handle, indent=2, sort_keys=True)
        handle.write("\n")
