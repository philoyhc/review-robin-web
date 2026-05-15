"""Relationships Setup page — locate-a-pair search/filter strip —
Segment 15F PR 5 stage 1.

Pins the operator-actions card's search-by-dimension dropdown +
search box + 200/500 cap. Per-row mutation (Edit / Add / bulk
with reviewer / reviewee pickers) lands in a later stage.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed(
    db: Session,
    session_id: int,
    *,
    reviewers: list[str],
    reviewees: list[str],
    pairs: list[tuple[int, int]],
) -> tuple[list[Reviewer], list[Reviewee], list[Relationship]]:
    rv = [
        Reviewer(
            session_id=session_id,
            name=name,
            email=f"{name.lower()}@example.edu",
        )
        for name in reviewers
    ]
    re_ = [
        Reviewee(
            session_id=session_id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
        )
        for name in reviewees
    ]
    db.add_all(rv + re_)
    db.flush()
    rels = [
        Relationship(
            session_id=session_id,
            reviewer_id=rv[i].id,
            reviewee_id=re_[j].id,
        )
        for i, j in pairs
    ]
    db.add_all(rels)
    db.commit()
    return rv, re_, rels


def test_plain_render_has_search_by_dropdown(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-plain")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Carol"],
        pairs=[(0, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert 'class="card operator-actions-card"' in body
    assert 'name="search_by"' in body
    assert '<option value="reviewer"' in body
    assert '<option value="reviewee"' in body
    # No active/inactive "All" status option on this page.
    assert '<option value="all"' not in body


def test_search_by_reviewer_dimension(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-rev")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Carol"],
        pairs=[(0, 0), (1, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
        "?search_by=reviewer&q=alice"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "alice@example.edu" in table
    assert "bob@example.edu" not in table


def test_search_by_reviewee_dimension(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-ree")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Carol", "Dan"],
        pairs=[(0, 0), (0, 1)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
        "?search_by=reviewee&q=dan"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "dan@example.edu" in table
    assert "carol@example.edu" not in table


def test_search_by_reviewer_does_not_match_reviewee_side(
    db: Session, client: TestClient
) -> None:
    """A reviewee named like a reviewer is not matched when the
    dropdown is set to the reviewer dimension."""
    review_session = _make_session(client, db, code="rel-f-dim")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Zeta"],
        pairs=[(0, 0)],
    )
    # Search the reviewer dimension for "zeta" — no reviewer matches.
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
        "?search_by=reviewer&q=zeta"
    ).text
    assert "No relationships match the current filter." in body


def test_empty_search_shows_all(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rel-f-empty")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Carol"],
        pairs=[(0, 0), (1, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?search_by=reviewer"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "alice@example.edu" in table
    assert "bob@example.edu" in table


def test_unfiltered_cap_is_200(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rel-f-cap")
    reviewers = [
        Reviewer(
            session_id=review_session.id,
            name=f"R{i:04d}",
            email=f"r{i:04d}@example.edu",
        )
        for i in range(250)
    ]
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Solo",
        email_or_identifier="solo@example.edu",
    )
    db.add_all([*reviewers, reviewee])
    db.flush()
    db.add_all(
        [
            Relationship(
                session_id=review_session.id,
                reviewer_id=rv.id,
                reviewee_id=reviewee.id,
            )
            for rv in reviewers
        ]
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert "Showing 200 of 250" in body


def test_clear_link_only_when_filtered(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-clear")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Carol"],
        pairs=[(0, 0)],
    )
    plain = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    filtered = client.get(
        f"/operator/sessions/{review_session.id}/relationships?q=alice"
    ).text
    assert ">Clear</a>" not in plain
    assert ">Clear</a>" in filtered


def test_both_dimension_datalists_render_with_correct_options(
    db: Session, client: TestClient
) -> None:
    """Both datalists ship every render — the dropdown swaps the
    input's ``list`` so autocomplete tracks Search-by without a
    reload. The reviewer datalist holds only reviewers; the
    reviewee datalist only reviewees."""
    review_session = _make_session(client, db, code="rel-f-datalist")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Carol"],
        pairs=[(0, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text

    rev_start = body.find('id="relationships-search-reviewer"')
    rev_block = body[rev_start : body.find("</datalist>", rev_start)]
    assert "Alice (alice@example.edu)" in rev_block
    assert "Carol (carol@example.edu)" not in rev_block

    ree_start = body.find('id="relationships-search-reviewee"')
    ree_block = body[ree_start : body.find("</datalist>", ree_start)]
    assert "Carol (carol@example.edu)" in ree_block
    assert "Alice (alice@example.edu)" not in ree_block


def test_search_input_list_tracks_search_by(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-listattr")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Carol"],
        pairs=[(0, 0)],
    )
    rev = client.get(
        f"/operator/sessions/{review_session.id}/relationships?search_by=reviewer"
    ).text
    assert 'list="relationships-search-reviewer"' in rev
    ree = client.get(
        f"/operator/sessions/{review_session.id}/relationships?search_by=reviewee"
    ).text
    assert 'list="relationships-search-reviewee"' in ree
