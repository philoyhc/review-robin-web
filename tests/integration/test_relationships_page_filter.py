"""Relationships Setup page — search/filter strip — Segment 15F PR 5
stage 1, rationalized in Segment 19I Item 1.

Pins the operator-actions card's Status dropdown + search box +
200/500 cap. The ``Search by`` side-picker the page shipped from 15F
to 19I is gone: the search now matches both sides of the pair plus
the row's own pair-context tags, which is the shape the other three
roster pages use. Per-row mutation (Edit / Add / bulk with reviewer /
reviewee pickers) lives in ``test_relationships_page_mutate.py``.
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
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()
    return review_session


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


def test_plain_render_has_status_dropdown(
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
    assert '<select name="status">' in body
    assert '<option value="all"' in body
    assert '<option value="active"' in body
    assert '<option value="inactive"' in body
    # The retired side-picker leaves nothing behind (19I Item 1).
    assert "search_by" not in body


def test_search_matches_the_reviewer_side(
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
        f"/operator/sessions/{review_session.id}/relationships?q=alice"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "alice@example.edu" in table
    assert "bob@example.edu" not in table


def test_search_matches_the_reviewee_side(
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
        f"/operator/sessions/{review_session.id}/relationships?q=dan"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "dan@example.edu" in table
    assert "carol@example.edu" not in table


def test_one_needle_matches_either_side(
    db: Session, client: TestClient
) -> None:
    """The 15F behavior this replaces: searching "zeta" with the
    dropdown on the reviewer dimension found nothing, because Zeta is
    a reviewee. With the side-picker gone one needle reaches both
    sides, and a row whose *reviewee* alone matches is kept."""
    review_session = _make_session(client, db, code="rel-f-dim")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Zeta", "Yara"],
        pairs=[(0, 0), (1, 1)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?q=zeta"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "zeta@example.edu" in table
    assert "yara@example.edu" not in table


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
        f"/operator/sessions/{review_session.id}/relationships?q="
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


def test_one_datalist_carries_both_sides(
    db: Session, client: TestClient
) -> None:
    """One suggestion list, not two. The page used to ship a reviewer
    datalist and a reviewee datalist and swap the input's ``list=``
    from the dropdown; with the search matching both sides the
    suggestions do too (19I Item 1)."""
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

    assert 'list="relationships-search-options"' in body
    assert 'id="relationships-search-reviewer"' not in body
    assert 'id="relationships-search-reviewee"' not in body

    start = body.find('id="relationships-search-options"')
    block = body[start : body.find("</datalist>", start)]
    assert "Alice (alice@example.edu)" in block
    assert "Carol (carol@example.edu)" in block


# --------------------------------------------------------------------------- #
# Status filter + pair-context tag search — Segment 19I Item 1.
#
# The predicate is unit-tested in tests/unit/test_roster_search_filters.py;
# these pin that the route hands it the whole roster, the status the
# operator picked, and renders both halves of the suggestion list.
# --------------------------------------------------------------------------- #


def test_status_filter_hides_the_other_status(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-status")
    _, _, rels = _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Carol"],
        pairs=[(0, 0), (1, 0)],
    )
    rels[1].status = "inactive"
    db.commit()

    active = client.get(
        f"/operator/sessions/{review_session.id}/relationships?status=active"
    ).text
    table = active[active.find('id="relationships-table"') :]
    assert "alice@example.edu" in table
    assert "bob@example.edu" not in table

    inactive = client.get(
        f"/operator/sessions/{review_session.id}/relationships?status=inactive"
    ).text
    table = inactive[inactive.find('id="relationships-table"') :]
    assert "bob@example.edu" in table
    assert "alice@example.edu" not in table


def test_status_all_shows_both(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rel-f-status-all")
    _, _, rels = _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Carol"],
        pairs=[(0, 0), (1, 0)],
    )
    rels[1].status = "inactive"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?status=all"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "alice@example.edu" in table
    assert "bob@example.edu" in table


def test_searching_a_pair_context_tag_narrows_the_table(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-tag")
    _, _, rels = _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Carol"],
        pairs=[(0, 0), (1, 0)],
    )
    rels[0].tag_1 = "TW01"
    rels[1].tag_1 = "TW02"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?q=TW01"
    ).text
    table = body[body.find('id="relationships-table"') :]
    assert "alice@example.edu" in table
    assert "bob@example.edu" not in table


def test_the_datalist_offers_pair_context_tag_values(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-f-tag-list")
    _, _, rels = _seed(
        db,
        review_session.id,
        reviewers=["Alice", "Bob"],
        reviewees=["Carol"],
        pairs=[(0, 0), (1, 0)],
    )
    rels[0].tag_1 = "TW01"
    rels[1].tag_1 = "TW01"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    start = body.find('id="relationships-search-options"')
    block = body[start : body.find("</datalist>", start)]

    assert block.count('<option value="TW01">') == 1, "one option per value"
    assert '<option value="Alice (alice@example.edu)">' in block
    # Tags lead the list, people follow.
    assert block.find('value="TW01"') < block.find("Alice (alice@example.edu)")


def test_clear_link_appears_for_a_status_only_filter(
    db: Session, client: TestClient
) -> None:
    """Status joins ``q`` in what counts as filtered — without this
    the operator could narrow to Inactive with no way back."""
    review_session = _make_session(client, db, code="rel-f-clear-status")
    _seed(
        db,
        review_session.id,
        reviewers=["Alice"],
        reviewees=["Carol"],
        pairs=[(0, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?status=inactive"
    ).text
    assert ">Clear</a>" in body
