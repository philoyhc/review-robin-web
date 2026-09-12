"""The response prefetch behind the Invitations and Responses pages (19K.3).

Both pages read every response row in the session. They used to read
them one assignment at a time: ``responses/_core.py`` inside
``_state_from_assignments`` for the reviewer side, ``monitoring.py``
inside ``_assignment_complete`` for the reviewee side. Measured
2026-09-12 through the real routes at a 200x200 roster (40,000
assignments), rendering each page once cost **40,433 and 80,432
queries** — and the Responses page paid both passes, its second one
(``summary_counts``) accounting for exactly half while contributing a
single integer to the page.

``responses_service.responses_by_assignment`` replaces that with one
query per session, passed down through an optional parameter so that
every caller which does *not* loop is unchanged.

Two things need guarding, and they are different things:

* that the prefetched path returns **the same answer** as the
  per-assignment path — the risk in any caching change; and
* that the page **does not go back** to scaling with the assignment
  count — the risk this item exists to remove, which no equivalence
  test can see.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    ReviewSession,
)
from app.services import monitoring
from app.services import responses as responses_service
from app.services.monitoring import _assignment_complete

from ._full_matrix import (
    generate_via_page_button,
    mark_band1_touched_on_all_instruments,
    pin_full_matrix_on_all_instruments,
)


def _roster(kind: str, n: int) -> bytes:
    if kind == "reviewers":
        return b"ReviewerName,ReviewerEmail\n" + b"".join(
            f"R{i},r{i}@example.edu\n".encode() for i in range(n)
        )
    return b"RevieweeName,RevieweeEmail\n" + b"".join(
        f"E{i},e{i}@example.edu\n".encode() for i in range(n)
    )


def _activate_and_respond(
    client: TestClient, db: Session, session: ReviewSession, make_client, n: int
) -> None:
    """Put real ``responses`` rows behind the fixture.

    Without this the equivalence tests below compare an empty list
    against an empty list for every assignment and pass whatever the
    prefetch does — which is how the first version of this file was
    written, and it passed against a mutation that returned ``{}``.
    Half the reviewers submit and half do not, so the completeness
    branches are exercised in both directions.
    """
    client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/workflow/activate",
        follow_redirects=False,
    )
    for index in range(max(1, n // 2)):
        email = f"r{index}@example.edu"
        reviewer_client = make_client(
            AuthenticatedUser(
                principal_id=f"r{index}-oid",
                email=email,
                name=f"R{index}",
                provider="aad",
            )
        )
        assignment_ids = [
            a.id
            for a in db.execute(
                select(Assignment).where(Assignment.session_id == session.id)
            ).scalars()
        ]
        data: dict[str, str] = {}
        for aid in assignment_ids:
            data[f"response[{aid}][rating]"] = "5"
            data[f"response[{aid}][comments]"] = "fine"
        reviewer_client.post(
            f"/me/sessions/{session.id}/1/save", data=data, follow_redirects=False
        )
        if index % 2 == 0:
            reviewer_client.post(
                f"/me/sessions/{session.id}/submit", follow_redirects=False
            )


def _seeded(client: TestClient, db: Session, n: int, code: str) -> ReviewSession:
    assert client.post(
        "/operator/sessions",
        data={"name": f"Pre{n}", "code": code, "description": "d"},
        follow_redirects=False,
    ).status_code == 303
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    for kind in ("reviewers", "reviewees"):
        client.post(
            f"/operator/sessions/{session.id}/{kind}/import",
            files={"file": (f"{kind}.csv", _roster(kind, n), "text/csv")},
            follow_redirects=False,
        )
    mark_band1_touched_on_all_instruments(db, session.id)
    pin_full_matrix_on_all_instruments(db, session.id)
    generate_via_page_button(client, session.id)
    return session


def _count_queries(db: Session, fn) -> int:
    total = 0

    def cb(conn, cursor, statement, params, context, many):
        nonlocal total
        total += 1

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", cb)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", cb)
    return total


def test_the_prefetched_path_agrees_with_the_per_assignment_path(
    client: TestClient, db: Session, make_client
) -> None:
    """Equivalence, assignment by assignment. A prefetch that is fast
    and wrong is worse than the loop it replaced, and the failure mode
    is silent: a coverage pill reads "complete" for a reviewee whose
    responses were never submitted.
    """
    session = _seeded(client, db, 4, code="PREFEQ")
    _activate_and_respond(client, db, session, make_client, 4)
    assert db.execute(select(Response)).scalars().first() is not None, (
        "fixture produced no responses; the comparison below would be vacuous"
    )
    prefetched = responses_service.responses_by_assignment(
        db, session_id=session.id
    )
    assignments = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == session.id)
        ).scalars()
    )
    assert assignments, "fixture produced no assignments"

    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    for field in db.execute(select(InstrumentResponseField)).scalars():
        fields_by_instrument.setdefault(field.instrument_id, []).append(field)

    for assignment in assignments:
        fields = fields_by_instrument.get(assignment.instrument_id, [])
        assert _assignment_complete(db, assignment, fields) == _assignment_complete(
            db, assignment, fields, prefetched
        ), f"assignment {assignment.id} disagrees"


def test_an_assignment_with_no_responses_reads_the_same_either_way(
    client: TestClient, db: Session
) -> None:
    """The case the dict cannot represent directly: an assignment with
    no rows is absent from it, and `.get(id, [])` has to return what the
    query returned — an empty list, not a KeyError and not None."""
    session = _seeded(client, db, 3, code="PREFEMPTY")
    prefetched = responses_service.responses_by_assignment(
        db, session_id=session.id
    )
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalars().first()
    assert assignment.id not in prefetched, "fixture has responses; test is void"
    assert _assignment_complete(db, assignment, []) == _assignment_complete(
        db, assignment, [], prefetched
    )


def test_coverage_does_not_scale_with_the_assignment_count(
    client: TestClient, db: Session
) -> None:
    """The regression guard, and the one an equivalence test cannot give.

    Doubling the roster quadruples the assignments (n x n). If the query
    count quadrupled with it we would be back to the N+1 — which is what
    40,433 queries at 200x200 was. It must grow with the *roster*, not
    with its square.
    """
    small = _seeded(client, db, 4, code="PRESM")
    large = _seeded(client, db, 8, code="PRELG")

    small_assignments = len(
        db.execute(
            select(Assignment).where(Assignment.session_id == small.id)
        ).scalars().all()
    )
    large_assignments = len(
        db.execute(
            select(Assignment).where(Assignment.session_id == large.id)
        ).scalars().all()
    )
    assert large_assignments >= small_assignments * 3, "fixture is not quadratic"

    small_q = _count_queries(
        db, lambda: monitoring.per_reviewee_coverage(db, small)
    )
    large_q = _count_queries(
        db, lambda: monitoring.per_reviewee_coverage(db, large)
    )
    growth = large_q / small_q
    assert growth < 2.5, (
        f"query count grew {growth:.1f}x for {large_assignments / small_assignments:.0f}x "
        f"the assignments ({small_q} -> {large_q}) — the prefetch is not holding"
    )


def test_reviewer_progress_does_not_scale_with_the_assignment_count(
    client: TestClient, db: Session
) -> None:
    """The same guard on the reviewer side, which is what the
    Invitations page renders and what `summary_counts` runs a second
    time for the Responses page."""
    small = _seeded(client, db, 4, code="PRGSM")
    large = _seeded(client, db, 8, code="PRGLG")
    small_q = _count_queries(
        db, lambda: monitoring.per_reviewer_progress(db, small)
    )
    large_q = _count_queries(
        db, lambda: monitoring.per_reviewer_progress(db, large)
    )
    growth = large_q / small_q
    assert growth < 2.5, (
        f"query count grew {growth:.1f}x ({small_q} -> {large_q})"
    )


def test_the_prefetch_loads_only_this_session(
    client: TestClient, db: Session, make_client
) -> None:
    """Scoping, guarded as the performance property it is.

    Dropping the ``session_id`` filter is not a correctness bug —
    assignment ids are globally unique, so a superset keyed by
    assignment id still answers every ``.get`` correctly, and the
    equivalence tests above pass against that mutation. What it costs is
    the whole point of the change: on a server hosting many sessions the
    prefetch would read every response row in the database to render one
    session's page.
    """
    mine = _seeded(client, db, 3, code="SCOPEA")
    other = _seeded(client, db, 3, code="SCOPEB")
    # The other session needs *rows* to leak, or dropping the filter
    # leaks nothing and this test passes on the mutation it exists for.
    _activate_and_respond(client, db, other, make_client, 3)
    assert db.execute(select(Response)).scalars().first() is not None

    other_assignment_ids = {
        a.id
        for a in db.execute(
            select(Assignment).where(Assignment.session_id == other.id)
        ).scalars()
    }
    assert other_assignment_ids, "fixture is void"

    prefetched = responses_service.responses_by_assignment(
        db, session_id=mine.id
    )
    assert not (set(prefetched) & other_assignment_ids), (
        "the prefetch reached into another session's assignments"
    )
