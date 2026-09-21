"""What one page render costs the readiness report (19R Item 5).

`guide/app_responsiveness.md` Finding 6 measured the Validate page
running `validation.validate_session_setup` — all 22 registered rules —
**twice** per render: once for the page's own issue table, and again
inside `views.build_workflow_card_context` for the Workflow card. The
two call sites did not know about each other, and nothing between them
mutates the session, so the second run could only ever reproduce the
first. Rung 1 hands the first run's result to the card.

The ceiling below is deliberately wider than the one page that was
wrong. Every Operations-row page hosts the same card, so any of them
could grow a second run the same way; asserting "at most one run per
render" on all of them is what stops the next one.

Rung 3 adds the other half: within one run, the report must not issue
the same statement with the same bound parameters twice. That is the
defect rung 2 fixed — twenty-two checks each loading for themselves —
stated as a rule rather than as a one-off cleanup, so the next check
added cannot quietly bring its own load back.

This file is about the report's *cost*, never its verdict — which
issues surface is `test_validation_issue_parity.py` and the rule tests.
"""

from __future__ import annotations

import re
import traceback
from collections.abc import Callable
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

import app as app_package
from app.db.models import ReviewSession
from app.schemas.validation import Severity, ValidationIssue
from app.services import validation
from app.web import views
from ._full_matrix import pin_full_matrix_on_all_instruments
from ._validation_scenarios import SCENARIOS


# Every page that renders `operator/partials/next_action_card.html`,
# as a URL suffix on `/operator/sessions/{id}`. Session Home is the
# empty suffix. Extract data is absent on purpose: it is gated on a
# `ready` session, and this fixture stops at `validated` — the state
# Finding 6 measured, and the only one in which the card runs the
# report at all.
CARD_PAGES = ["", "/assignments", "/validate", "/invitations", "/responses"]


def _seed_validated(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """A `validated` session with both rosters imported and every
    instrument pinned to Full Matrix. No assignments generated, so the
    report carries a warning and no errors — enough for `?validated=1`
    to flip the lifecycle."""
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nC,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    db.refresh(review_session)
    assert review_session.status == "validated"
    return review_session


@pytest.fixture()
def report_runs(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Session ids, one per `validate_session_setup` call.

    Both call sites reach the orchestrator through the `validation`
    module object, so patching the attribute there counts the route's
    run and the card builder's alike.
    """
    runs: list[int] = []
    real: Callable[[Session, ReviewSession], list[ValidationIssue]] = (
        validation.validate_session_setup
    )

    def counting(
        db: Session, review_session: ReviewSession
    ) -> list[ValidationIssue]:
        runs.append(review_session.id)
        return real(db, review_session)

    monkeypatch.setattr(validation, "validate_session_setup", counting)
    return runs


def test_the_validate_page_builds_the_readiness_report_once(
    client: TestClient, db: Session, report_runs: list[int]
) -> None:
    review_session = _seed_validated(client, db, code="rc1")
    report_runs.clear()

    response = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    )

    assert response.status_code == 200, response.text
    assert report_runs == [review_session.id]


@pytest.mark.parametrize("suffix", CARD_PAGES)
def test_no_workflow_card_page_builds_the_report_more_than_once(
    client: TestClient, db: Session, report_runs: list[int], suffix: str
) -> None:
    """The ceiling, not the floor: a page is free to run the report
    zero times (the card skips it outside `validated`), but never
    twice for one render."""
    review_session = _seed_validated(
        client, db, code="rc" + (suffix.strip("/") or "home")
    )
    report_runs.clear()

    response = client.get(
        f"/operator/sessions/{review_session.id}{suffix}"
    )

    assert response.status_code == 200, response.text
    assert len(report_runs) <= 1, (
        f"/operator/sessions/{{id}}{suffix} ran the readiness report "
        f"{len(report_runs)} times for one render"
    )


def test_the_card_reports_the_issues_it_was_handed(
    client: TestClient, db: Session
) -> None:
    """The hand-off is load-bearing, not decorative: the summary the
    card renders comes from the passed-in list, so a builder that
    quietly ran its own would show this session's real verdict (clean,
    activatable) instead of the error handed in."""
    review_session = _seed_validated(client, db, code="rc2")
    handed_in = [
        ValidationIssue(
            severity=Severity.error,
            source="test",
            message="Handed in, not recomputed.",
        )
    ]

    ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="validate",
        issues=handed_in,
    )

    summary = ctx["validation_summary"]
    assert summary is not None
    assert summary["error_count"] == 1
    assert summary["can_activate"] is False
    assert ctx["validation_issues_by_severity"]["errors"] == handed_in


def test_every_other_caller_still_builds_its_own_report(
    client: TestClient, db: Session, report_runs: list[int]
) -> None:
    """`issues` defaults to `None`, and the default still runs the
    orchestrator — the hand-off is one route's optimization, not a new
    obligation on the other four pages."""
    review_session = _seed_validated(client, db, code="rc3")
    report_runs.clear()

    views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )

    assert report_runs == [review_session.id]


# --------------------------------------------------------------------------- #
# The no-duplicate guard (rung 3)
# --------------------------------------------------------------------------- #

#: The report's own module. A statement issued from here is the report
#: loading something; a statement issued from anywhere else under
#: `app/` is a service the report called, loading for its own purposes.
REPORT_MODULE = "app/services/validation.py"

#: The one call the exception is for. `_check_instruments_stale_generated`
#: asks the assignments engine whether regenerating would change
#: anything, and the engine builds its own `_load_reconcile_inputs`,
#: re-reading the instruments and both rosters the report already
#: holds.
#:
#: The **call**, not the package. An earlier revision allowed anything
#: under `app/services/assignments/`, which was too wide to enforce the
#: rule it exists for: a check calling `included_count_per_instrument`
#: twice issues both from `_coverage.py`, so the guard below would skip
#: them as not the report's and this test would accept them as the
#: engine's. Matching the frame instead pins the exception to the one
#: path that was argued for (Codex, PR #2533).
STALENESS_CALL = "staleness_by_instrument"


#: Resolved from the package itself rather than from a path fragment.
#: A checkout whose directory name appears twice in its absolute path —
#: which is exactly what GitHub Actions produces,
#: `/home/runner/work/<repo>/<repo>/…` — defeats any split on the repo
#: name, and the failure is silent: every module comes back under a
#: name that matches nothing, so the guard below passes having
#: recognised nothing at all. `test_the_guard_can_see_the_report`
#: is what makes that loud.
_APP_DIR = Path(app_package.__file__).resolve().parent
_REPO_ROOT = _APP_DIR.parent


def _issuing_module() -> str:
    """The innermost `app/` frame on the stack, as a repo-relative
    module path. That is the code that actually asked for the query,
    rather than whichever of SQLAlchemy's internals ran it."""
    for frame in reversed(traceback.extract_stack()):
        path = Path(frame.filename).resolve()
        if _APP_DIR in path.parents:
            return path.relative_to(_REPO_ROOT).as_posix()
    return "?"


def _under_staleness() -> bool:
    """Whether this query is being issued inside the engine call the
    exception is for, rather than merely inside its package."""
    return any(
        frame.name == STALENESS_CALL for frame in traceback.extract_stack()
    )


def _capture(
    db: Session, review_session: ReviewSession
) -> list[tuple[tuple[str, str], str, bool]]:
    """Run the report, returning one entry per statement it issued:
    ``((normalized SQL, bound parameters), issuing module, whether it
    came from inside the staleness call)``.

    Parameters are part of the key on purpose. Twenty-two checks each
    loading *the same session's* instruments is the defect; two checks
    loading two different instruments' fields is not.
    """
    captured: list[tuple[tuple[str, str], str, bool]] = []
    recording = {"on": False}

    def before(conn, cursor, statement, parameters, context, many):  # noqa: ANN001
        if recording["on"]:
            key = (re.sub(r"\s+", " ", statement).strip(), repr(parameters))
            captured.append((key, _issuing_module(), _under_staleness()))

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", before)
    try:
        recording["on"] = True
        validation.validate_session_setup(db, review_session)
    finally:
        recording["on"] = False
        event.remove(bind, "before_cursor_execute", before)
    return captured


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_the_report_never_issues_one_of_its_own_queries_twice(
    db: Session, scenario: str
) -> None:
    """The guard. One run, one load of anything the report loads.

    This is rung 2's change stated as a rule. Before it, eight checks
    each re-SELECTed the session's instruments and the three rosters
    came back 5x / 4x / 4x; the fix was to load them once, and this is
    what keeps the next check from re-opening the hole.
    """
    review_session = SCENARIOS[scenario](db)

    own = Counter(
        key
        for key, module, _ in _capture(db, review_session)
        if module == REPORT_MODULE
    )

    assert own, (
        "the report issued no query this test could attribute to "
        f"{REPORT_MODULE} — the guard would pass by recognising nothing"
    )
    repeated = {key: count for key, count in own.items() if count > 1}
    assert not repeated, "\n".join(
        f"{count}x  {sql[:110]}  params={params}"
        for (sql, params), count in repeated.items()
    )


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_remaining_repeat_belongs_to_the_staleness_call(
    db: Session, scenario: str
) -> None:
    """The boundary, pinned rather than quietly excluded.

    `_check_instruments_stale_generated` asks
    `assignments.staleness_by_instrument` whether regenerating would
    change anything, and that engine builds its own
    `_load_reconcile_inputs` — re-reading the instruments and both
    rosters the report already holds. Three statements per run.

    Rung 3's decision (19R Item 5) was to leave it. Handing the engine
    a roster loaded elsewhere is exactly the snapshot this item spent
    two rungs refusing to build: `staleness_by_instrument` is not a
    pure read — it caches each verdict and flushes — and its value is
    that it cannot drift from what Generate would do. A parameter
    saying "trust me, these rows are current" is how that guarantee
    starts to rot, and three indexed reads do not buy it.

    So the rule is narrower than "no repeats at all", and this test is
    what stops that narrowness from becoming a blanket excuse: a repeat
    the report causes on its own fails the guard above, and a repeat
    involving any *other* service fails here. If the engine ever stops
    re-loading, this passes vacuously and can go.
    """
    review_session = SCENARIOS[scenario](db)

    captured = _capture(db, review_session)
    counts = Counter(key for key, _, _ in captured)
    issues_by_key: dict[tuple[str, str], list[tuple[str, bool]]] = {}
    for key, module, under_staleness in captured:
        issues_by_key.setdefault(key, []).append((module, under_staleness))

    for key, count in counts.items():
        if count == 1:
            continue
        others = [
            (module, under_staleness)
            for module, under_staleness in issues_by_key[key]
            if module != REPORT_MODULE
        ]
        assert others, f"repeat entirely inside the report: {key[0][:110]}"
        assert all(under_staleness for _, under_staleness in others), (
            f"{key[0][:110]}\n  repeated from "
            f"{sorted({m for m, u in others if not u})} outside "
            f"`{STALENESS_CALL}`, which is not the exception this rung "
            "argued for"
        )
