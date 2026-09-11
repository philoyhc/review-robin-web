"""The Assignments sort, moved into the query — Segment 19J.5 rung 4.

Until this rung the page fetched 200 rows and sorted *those* in
Python. That was invisible while 200 was all an operator could see;
paging makes it a lie, because page 2 would be sorted within page 2.

So the sort moved into SQL — and the thing to prove is not that it
sorts, but that it sorts **the way the Python one did**. An operator's
rows must not reshuffle on the day this lands. Four rules carry that:

1. an empty string is not a value — it collapses to NULL;
2. NULL sorts last in *both* directions;
3. text compares by code point, as Python's ``<`` does;
4. the order is total, so a page boundary cannot drop or double a row.

Rule 3 is the one with teeth, and the reason these run against
Postgres in CI as well as SQLite: under a locale-aware collation the
same names order differently, and the ``ci-postgres`` container's
``C.UTF-8`` would not have caught it.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, Reviewer
from app.services import assignments as assignments_service
from app.web.views import apply_cookie_sort

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


# Deliberately adversarial: mixed case, a leading underscore, and a
# pair differing only in case — the set that separates code-point
# ordering from a locale-aware one.
NAMES = [
    "alpha",
    "Bravo",
    "charlie",
    "Delta",
    "_edge",
    "Ana Lim",
    "ana lim",
]


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    rows = b"".join(
        f"{name},r{i}@example.edu\n".encode() for i, name in enumerate(NAMES)
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": ("r.csv", b"ReviewerName,ReviewerEmail\n" + rows, "text/csv")
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nOnly E,e0@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    return review_session


def _sql_order(db: Session, session_id: int, spec) -> list[str]:
    pairs = assignments_service.list_pairs(
        db, session_id, limit=1000, sort=spec
    )
    return [a.reviewer.name for a in pairs]


def _python_order(db: Session, session_id: int, spec) -> list[str]:
    """What ``apply_cookie_sort`` would have produced over the same
    rows — the contract this rung had to preserve."""
    pairs = assignments_service.list_pairs(db, session_id, limit=1000)

    def resolver(assignment, key: str):
        if key == "reviewer":
            return assignment.reviewer.name if assignment.reviewer else None
        if key.startswith("reviewer_tag_"):
            slot = key.rsplit("_", 1)[-1]
            return getattr(assignment.reviewer, f"tag_{slot}", None)
        if key == "include":
            return "yes" if assignment.include else "no"
        return None

    return [
        a.reviewer.name
        for a in apply_cookie_sort(pairs, spec, value_resolver=resolver)
    ]


def test_the_sql_sort_matches_the_python_one_it_replaced(
    client: TestClient, db: Session
) -> None:
    """Rule 3, and the whole point: same rows, same order."""
    review_session = _seed(client, db, code="sortsql-parity")
    for direction in ("asc", "desc"):
        spec = [("reviewer", direction)]
        assert _sql_order(db, review_session.id, spec) == _python_order(
            db, review_session.id, spec
        ), direction


def test_case_is_significant_and_underscore_sorts_after_capitals(
    client: TestClient, db: Session
) -> None:
    """The assertion a locale-aware collation fails. Spelled out rather
    than left to the parity test, so a reader can see what order this
    app promises without running Python."""
    review_session = _seed(client, db, code="sortsql-codepoint")
    assert _sql_order(db, review_session.id, [("reviewer", "asc")]) == [
        "Ana Lim",
        "Bravo",
        "Delta",
        "_edge",
        "alpha",
        "ana lim",
        "charlie",
    ]


def test_an_empty_tag_sorts_as_absent_not_as_the_empty_string(
    client: TestClient, db: Session
) -> None:
    """Rule 1. ``''`` sorts first under both collations and last under
    the Python rule, so this is the branch a naive ORDER BY inverts."""
    review_session = _seed(client, db, code="sortsql-empty")
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    for reviewer in reviewers:
        reviewer.tag_1 = "" if reviewer.name == "Bravo" else reviewer.name
    db.commit()

    order = _sql_order(db, review_session.id, [("reviewer_tag_1", "asc")])
    assert order[-1] == "Bravo"


def test_null_sorts_last_in_both_directions(
    client: TestClient, db: Session
) -> None:
    """Rule 2 — not what either dialect does by default, which is why
    every clause is wrapped in ``NULLS LAST`` rather than only the
    ascending ones."""
    review_session = _seed(client, db, code="sortsql-nulls")
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    for reviewer in reviewers:
        reviewer.tag_1 = None if reviewer.name == "Delta" else reviewer.name
    db.commit()

    for direction in ("asc", "desc"):
        order = _sql_order(
            db, review_session.id, [("reviewer_tag_1", direction)]
        )
        assert order[-1] == "Delta", direction


def test_pair_tags_sort_through_the_relationship_join(
    client: TestClient, db: Session
) -> None:
    """``pair_tag_*`` was the key my own recommendation proposed leaving
    out of the SQL sort. It joins cleanly, so it went in — and an
    assignment with no active relationship sorts as absent, which is
    what the Python resolver returned for it."""
    from app.db.models import Relationship

    review_session = _seed(client, db, code="sortsql-pair")
    pairs = assignments_service.list_pairs(db, review_session.id, limit=1000)
    tagged = {"Bravo": "aaa", "Delta": "zzz"}
    for assignment in pairs:
        label = tagged.get(assignment.reviewer.name)
        if label is None:
            continue
        db.add(
            Relationship(
                session_id=review_session.id,
                reviewer_id=assignment.reviewer_id,
                reviewee_id=assignment.reviewee_id,
                tag_1=label,
                status="active",
            )
        )
    db.commit()

    order = _sql_order(db, review_session.id, [("pair_tag_1", "asc")])
    assert order[0] == "Bravo"
    assert order[1] == "Delta"
    # Everything else has no active relationship: absent, so last.
    assert set(order[2:]) == set(NAMES) - set(tagged)


def test_an_inactive_relationship_contributes_no_pair_tag(
    client: TestClient, db: Session
) -> None:
    """The rule engine only reads active relationships, and the Python
    resolver agreed. The join carries the same condition."""
    from app.db.models import Relationship

    review_session = _seed(client, db, code="sortsql-pair-inactive")
    pairs = assignments_service.list_pairs(db, review_session.id, limit=1000)
    target = next(a for a in pairs if a.reviewer.name == "Bravo")
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=target.reviewer_id,
            reviewee_id=target.reviewee_id,
            tag_1="aaa",
            status="inactive",
        )
    )
    db.commit()

    order = _sql_order(db, review_session.id, [("pair_tag_1", "asc")])
    assert order[0] != "Bravo"


def test_the_order_is_total_so_paging_neither_drops_nor_doubles_a_row(
    client: TestClient, db: Session
) -> None:
    """Rule 4. Every reviewer here shares one reviewee and one
    instrument, so the sort key alone does not separate them — the
    pair-order tie-break is what makes the window deterministic."""
    review_session = _seed(client, db, code="sortsql-total")
    spec = [("include", "asc")]  # every row ties on this
    seen: list[int] = []
    for offset in (0, 3, 6):
        page = assignments_service.list_pairs(
            db, review_session.id, limit=3, offset=offset, sort=spec
        )
        seen.extend(a.id for a in page)
    assert len(seen) == len(set(seen)) == len(NAMES)


def test_the_page_carries_the_sort_cookie_into_the_query(
    client: TestClient, db: Session
) -> None:
    """End to end: the cookie the header writes reaches the ORDER BY,
    which is what makes page 2 a page of the *sorted* roster."""
    review_session = _seed(client, db, code="sortsql-route")
    client.cookies.set(
        f"rrw-sort-assignments-{review_session.id}",
        json.dumps([{"key": "reviewer", "dir": "desc"}]),
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    table = body[body.index('id="assignments-table"') :]
    # Descending code point: `charlie` first, `Ana Lim` last.
    assert table.index("charlie") < table.index("Ana Lim")
    client.cookies.clear()
