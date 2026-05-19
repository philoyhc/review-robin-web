"""Reviewers Setup page — search/filter + cap rendering —
Segment 15F PR 2.

Pins the right-side operator-actions card scaffold's search +
status filter end-to-end (view-adapter → route → template) plus
the 200/500 cap on the row table. Mutation routes + per-row edit
UI ship in PR 3; PR 2's tests cover the find-a-row machinery and
the inert button placeholders that lock in the layout.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession


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


def _seed_reviewers_via_orm(
    db: Session, session_id: int, count: int
) -> None:
    """Bypass the CSV importer for fast bulk seeding (the importer
    caps at 5000 rows but per-import perf isn't what we're testing
    here). Uses zero-padded names so the alphabetical sort is
    deterministic."""
    for i in range(count):
        db.add(
            Reviewer(
                session_id=session_id,
                name=f"R{i:04d}",
                email=f"r{i:04d}@example.edu",
            )
        )
    db.commit()


# --------------------------------------------------------------------------- #
# Filter parsing — 4 combinations.
# --------------------------------------------------------------------------- #


def test_no_filter_renders_all_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-f-none")
    _seed_reviewers_via_orm(db, review_session.id, 3)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    table = body[body.find('id="reviewers-table"') :]
    assert "R0000" in table
    assert "R0001" in table
    assert "R0002" in table


def test_status_only_filter_narrows_to_inactive(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-f-stat")
    _seed_reviewers_via_orm(db, review_session.id, 4)
    # Flip R0001 + R0003 to inactive.
    for r in db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id,
            Reviewer.name.in_(["R0001", "R0003"]),
        )
    ).scalars():
        r.status = "inactive"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?status=inactive"
    ).text
    table = body[body.find('id="reviewers-table"') :]
    assert "R0001" in table
    assert "R0003" in table
    assert "R0000" not in table
    assert "R0002" not in table


def test_search_only_filter_substring_match(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-f-search")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
        )
    )
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Beta",
            email="beta@example.edu",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=alph"
    ).text
    table = body[body.find('id="reviewers-table"') :]
    assert "Alpha" in table
    assert "Beta" not in table


def test_status_and_search_filters_compose(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-f-both")
    alice_active = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    alice_inactive = Reviewer(
        session_id=review_session.id,
        name="Aliceanne",
        email="aliceanne@example.edu",
        status="inactive",
    )
    bob_inactive = Reviewer(
        session_id=review_session.id,
        name="Bob",
        email="bob@example.edu",
        status="inactive",
    )
    db.add_all([alice_active, alice_inactive, bob_inactive])
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        "?status=inactive&q=alice"
    ).text
    table = body[body.find('id="reviewers-table"') :]
    # Only Aliceanne matches both filters.
    assert "Aliceanne" in table
    assert "Alice@" not in table  # active Alice excluded
    assert "Bob" not in table  # inactive Bob excluded by search


# --------------------------------------------------------------------------- #
# Cap application — 200 unfiltered / 500 filtered.
# --------------------------------------------------------------------------- #


def test_unfiltered_cap_is_200(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rev-cap-200")
    _seed_reviewers_via_orm(db, review_session.id, 250)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    table = body[body.find('id="reviewers-table"') :]
    # First 200 rendered (R0000-R0199).
    assert "R0000" in table
    assert "R0199" in table
    assert "R0200" not in table  # past the cap
    # "Showing N of M" message present.
    assert "Showing 200 of 250" in body


def test_filtered_cap_lifts_to_500(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-cap-500")
    _seed_reviewers_via_orm(db, review_session.id, 600)

    # status=active narrows to all 600 (default status); the cap
    # lifts to 500.
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?status=active"
    ).text
    table = body[body.find('id="reviewers-table"') :]
    assert "R0000" in table
    assert "R0499" in table
    assert "R0500" not in table
    assert "Showing 500 of 600" in body


# --------------------------------------------------------------------------- #
# Layout regression — operator-actions card scaffold.
# --------------------------------------------------------------------------- #


def test_operator_actions_card_renders_inert_buttons(
    db: Session, client: TestClient
) -> None:
    """The four action buttons render as inert placeholders this PR;
    PR 3 lights them up with selection-driven enable/disable."""
    review_session = _make_session(client, db, code="rev-layout-buttons")
    _seed_reviewers_via_orm(db, review_session.id, 3)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert 'class="card operator-actions-card"' in body
    # All four action affordances present.
    for label in (
        ">Edit</button>",
        ">Inactivate</button>",
        ">Activate</button>",
        ">Add new row</a>",
    ):
        assert label in body
    # The three buttons (Edit / Inactivate / Reactivate) start
    # disabled — JS enables them on selection. They now sit inline
    # in the filter-actions row, before the Search submit.
    buttons_section = body[
        body.find('class="filter-actions"') :
    ][:2000]
    assert buttons_section.count("disabled") >= 3


def test_search_filter_form_renders_status_options_and_datalist(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-layout-filter")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
            status="inactive",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Status select carries the two REVIEWERS_STATUS_OPTIONS plus All.
    assert '<option value="all"' in body
    assert '<option value="active"' in body
    assert '<option value="inactive"' in body
    # Datalist carries both rosters' names + emails.
    assert 'id="reviewers-search-options"' in body
    assert "Alice (alice@example.edu)" in body
    assert "Bob (bob@example.edu)" in body


def test_datalist_capped_at_200(db: Session, client: TestClient) -> None:
    """Decision 14: datalist autocomplete capped at 200
    alphabetically; server-side filter handles anything the operator
    types beyond that."""
    review_session = _make_session(client, db, code="rev-datalist-cap")
    _seed_reviewers_via_orm(db, review_session.id, 300)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    datalist_start = body.find('id="reviewers-search-options"')
    datalist_end = body.find("</datalist>", datalist_start)
    datalist = body[datalist_start:datalist_end]
    option_count = datalist.count("<option")
    assert option_count == 200


# --------------------------------------------------------------------------- #
# "Showing N of M" line.
# --------------------------------------------------------------------------- #


def test_no_filter_no_cap_hides_showing_line(
    db: Session, client: TestClient
) -> None:
    """When displayed == total, the muted line stays hidden so the
    operator's screen reads quiet."""
    review_session = _make_session(client, db, code="rev-showing-hidden")
    _seed_reviewers_via_orm(db, review_session.id, 3)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert "Showing 3 of 3" not in body


def test_clear_link_only_renders_when_filter_active(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-clear-link")
    _seed_reviewers_via_orm(db, review_session.id, 3)

    body_unfiltered = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    body_filtered = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=foo"
    ).text
    # Clear button only present on the filtered render.
    assert ">Clear</a>" not in body_unfiltered
    assert ">Clear</a>" in body_filtered


def test_filter_no_match_shows_empty_state_with_table_count_preserved(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-no-match")
    _seed_reviewers_via_orm(db, review_session.id, 3)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=nomatchpls"
    ).text
    assert "No reviewers match the current filter." in body
    # The Danger Zone still renders since the total > 0.
    assert "Delete all reviewers" in body
