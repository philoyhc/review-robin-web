"""What the Invitations and Responses rollups are allowed to cost.

The file is named for 19K.3, which is where it started: both pages read
every response row in the session one assignment at a time —
``responses/_core.py`` inside ``_state_from_assignments`` for the
reviewer side, ``monitoring.py`` inside ``_assignment_complete`` for
the reviewee side. Measured 2026-09-12 through the real routes at a
200x200 roster (40,000 assignments), rendering each page once cost
**40,433 and 80,432 queries**. ``responses_by_assignment`` replaced
that with one query per session.

**19R Item 3 then removed the loops themselves**, so both rollups are
aggregate queries and neither reads response rows for a per-reviewee
instrument at all. That moved what needs guarding, and the file now
holds three kinds of check rather than 19K.3's two:

* **Equivalence** — the prefetched path returns the same answer as the
  per-assignment path, the risk in any caching change. These call
  ``_assignment_complete`` directly, which only the parity oracle
  ``_per_reviewee_coverage_python`` still reaches; they are about the
  prefetch, not about what the pages now run.
* **Query count flat in the roster** — the 19K.3 guards, right for an
  N+1 and structurally blind to 19R Item 3: the old rollups issued few
  queries and built every row as an object.
* **ORM instances loaded** — the 19R Item 3 guards, which is where that
  cost is visible. ``spec/operations_pages.md`` "What these pages cost
  to render" carries the figures; the tests pin the shape (flat, and
  bounded), never the numbers, because a legitimately added query
  should not fail a test while the contract still holds.

The last group needs a fixture with **both instrument kinds**:
``per_reviewer_progress`` keeps a Python path for group-scoped
instruments, and ``_seeded`` makes none, so ``_mixed`` at the end of
this file is what reaches it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    ReviewSession,
    Reviewee,
    Reviewer,
    User,
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


def _count_orm_rows(db: Session, fn) -> int:
    """How many ORM instances ``fn`` loads.

    The 19K.3 guards above count *queries*, which is the right measure
    for an N+1. 19R Item 3 removed a different cost that a query count
    cannot see: the rollups issued few queries and then built every
    ``Assignment`` and ``Response`` in the session as an object —
    408,027 of them for one render at a 1,000 x 1,000 roster
    (``guide/app_responsiveness.md``). A rewrite that went back to
    loading rows and counting them in Python would keep the query count
    flat and put the seconds straight back.
    """
    total = 0

    def cb(session, instance):
        nonlocal total
        total += 1

    event.listen(db, "loaded_as_persistent", cb)
    try:
        fn()
    finally:
        event.remove(db, "loaded_as_persistent", cb)
    return total


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


def test_the_rollups_do_not_load_a_row_per_assignment(
    client: TestClient, db: Session
) -> None:
    """The 19R Item 3 guard, and the one the query counts above cannot
    give.

    Both rollups became aggregate queries, so the row count they load
    must be flat in the roster's *square*: quadrupling the assignments
    must not quadruple the objects. The reviewer side keeps a Python
    path for group-scoped instruments — the fixture here has none, so
    what is measured is the aggregate path that carries almost every
    real session. The mixed-session pair at the end of this file is
    what covers the other path.
    """
    small = _seeded(client, db, 4, code="ORMSM")
    large = _seeded(client, db, 8, code="ORMLG")

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

    for name, rollup in (
        ("per_reviewee_coverage", monitoring.per_reviewee_coverage),
        ("per_reviewer_progress", monitoring.per_reviewer_progress),
    ):
        db.expunge_all()
        small_rows = _count_orm_rows(db, lambda: rollup(db, small))
        db.expunge_all()
        large_rows = _count_orm_rows(db, lambda: rollup(db, large))
        # The reviewee / reviewer objects themselves still load, and
        # those grow with the roster — linearly. The assignments and
        # responses must not.
        assert large_rows < small_rows * 3, (
            f"{name} loaded {small_rows} -> {large_rows} ORM rows for "
            f"{large_assignments / small_assignments:.0f}x the "
            "assignments — it is materialising rows again"
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


# --------------------------------------------------------------------------- #
# SI-07 — the query budget in spec/operations_pages.md, pinned by a guard
# --------------------------------------------------------------------------- #


def test_the_assignments_page_query_count_is_flat_in_the_roster(
    client: TestClient, db: Session
) -> None:
    """`spec/operations_pages.md` prints a budget table and says
    *"Assignments stays flat at 43 at every size — its ``LIMIT 200`` and
    its indexes are what hold it there, so a change that drops either
    belongs in this table."*

    Until now nothing pinned that. The relative-growth guards above cover
    the two pages that scale with the roster; the Assignments page's
    claim is stronger — **flat, not linear** — and a stronger claim needs
    its own check.

    **Flatness is what this asserts, not the number 43.** A figure
    self-stales: any legitimately added query would fail a test pinned to
    43 while the contract still held. What cannot change without the
    contract breaking is that the count does not move with the roster at
    all. If this fails, either the `LIMIT 200` or an index has gone — and
    the spec's table wants re-measuring either way.
    """
    small = _seeded(client, db, 4, code="QBSM")
    large = _seeded(client, db, 8, code="QBLG")

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
        db,
        lambda: client.get(f"/operator/sessions/{small.id}/assignments"),
    )
    large_q = _count_queries(
        db,
        lambda: client.get(f"/operator/sessions/{large.id}/assignments"),
    )

    assert small_q == large_q, (
        f"the Assignments page is no longer flat in the roster: "
        f"{small_q} queries at {small_assignments} assignments against "
        f"{large_q} at {large_assignments}. spec/operations_pages.md "
        f"claims flat at every size, held by LIMIT 200 plus indexes — "
        f"check whether one of those has gone, and re-measure the "
        f"budget table there."
    )


def _mixed(db: Session, n: int, code: str) -> ReviewSession:
    """A session carrying **both** instrument kinds, which `_seeded`
    does not.

    One per-reviewee instrument and one group-scoped one, every
    reviewer x reviewee pair assigned on both, and an answered
    ``Response`` row on every assignment. The group boundary is
    ``tag_1`` over two fixed values, so the *group* count stays at two
    while the roster grows — the shape that tells the grouped half's
    own cost apart from the roster's.
    """
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code, code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    sid = review_session.id

    reviewers = [
        Reviewer(session_id=sid, name=f"R{i}", email=f"r{i}-{code}@example.edu")
        for i in range(n)
    ]
    reviewees = [
        Reviewee(
            session_id=sid,
            name=f"E{i}",
            email_or_identifier=f"e{i}-{code}@example.edu",
            tag_1=f"Team {i % 2}",
        )
        for i in range(n)
    ]
    db.add_all([*reviewers, *reviewees])

    plain = Instrument(
        session_id=sid, name="Plain", order=0, session_seq=1, group_kind=None
    )
    grouped = Instrument(
        session_id=sid, name="Grouped", order=1, session_seq=2, group_kind="r1"
    )
    db.add_all([plain, grouped])
    db.flush()

    fields = {
        instrument.id: InstrumentResponseField(
            instrument_id=instrument.id,
            field_key="q1",
            label="Q1",
            required=True,
            order=0,
        )
        for instrument in (plain, grouped)
    }
    db.add_all(fields.values())
    db.flush()

    for instrument in (plain, grouped):
        for reviewer in reviewers:
            for reviewee in reviewees:
                assignment = Assignment(
                    session_id=sid,
                    instrument_id=instrument.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    include=True,
                )
                db.add(assignment)
                db.flush()
                db.add(
                    Response(
                        assignment_id=assignment.id,
                        response_field_id=fields[instrument.id].id,
                        value="answered",
                    )
                )
    db.flush()
    return review_session


def test_the_grouped_half_reads_only_grouped_work(
    client: TestClient, db: Session
) -> None:
    """Codex P1 on the rung-3 diff, and the gap the guard above admits.

    ``per_reviewer_progress`` keeps a Python path for group-scoped
    instruments. One group instrument in a session must not drag the
    *per-reviewee* instruments' rows back through the ORM: the
    aggregate half has already counted those in SQL, and a mixed
    session at roster scale is exactly where this rewrite is supposed
    to pay. The guard above cannot see it — its fixture has no grouped
    instrument at all, so the Python path never runs.
    """
    session = _mixed(db, 4, code="MIXORM")
    grouped_assignment_ids = set(
        db.execute(
            select(Assignment.id)
            .join(Instrument, Instrument.id == Assignment.instrument_id)
            .where(
                Assignment.session_id == session.id,
                Instrument.group_kind.is_not(None),
            )
        ).scalars()
    )
    plain_assignment_ids = set(
        db.execute(
            select(Assignment.id)
            .join(Instrument, Instrument.id == Assignment.instrument_id)
            .where(
                Assignment.session_id == session.id,
                Instrument.group_kind.is_(None),
            )
        ).scalars()
    )
    assert grouped_assignment_ids and plain_assignment_ids, "fixture is not mixed"

    loaded: list[Response] = []

    def cb(_session, instance):
        if isinstance(instance, Response):
            loaded.append(instance)

    db.expunge_all()
    event.listen(db, "loaded_as_persistent", cb)
    try:
        monitoring.per_reviewer_progress(db, session)
    finally:
        event.remove(db, "loaded_as_persistent", cb)

    assert loaded, "no responses loaded at all; the assertion below is vacuous"
    strays = {
        r.assignment_id for r in loaded
    } - grouped_assignment_ids
    assert not strays, (
        f"{len(strays)} per-reviewee assignments' responses were loaded as "
        "ORM rows by the grouped half. The aggregate half already counted "
        "them in SQL — pass group_scoped_only=True to "
        "responses_by_assignment."
    )


def test_the_grouped_dedupe_does_not_lazy_load_a_reviewee_at_a_time(
    client: TestClient, db: Session
) -> None:
    """Codex P2 on the rung-3 diff.

    ``responses.group_keys`` reads ``assignment.reviewee`` for the
    boundary tags. The loop this rung replaced fetched its assignments
    with ``joinedload(Assignment.reviewee)``; the new grouped query has
    to carry the same option or the dedupe issues one SELECT per
    distinct reviewee, which grows with the roster.
    """
    small = _mixed(db, 4, code="MIXQSM")
    large = _mixed(db, 8, code="MIXQLG")

    db.expunge_all()
    small_q = _count_queries(db, lambda: monitoring.per_reviewer_progress(db, small))
    db.expunge_all()
    large_q = _count_queries(db, lambda: monitoring.per_reviewer_progress(db, large))

    assert small_q == large_q, (
        f"per_reviewer_progress is no longer flat in the roster on a "
        f"session with group-scoped work: {small_q} queries at 4x4 "
        f"against {large_q} at 8x8. The likeliest cause is a lazy load "
        f"per reviewee in the group dedupe — check the joinedload on "
        f"the grouped assignment query."
    )
