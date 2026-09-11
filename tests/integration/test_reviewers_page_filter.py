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
    assert "R0200" not in table  # past the page

    # 19J.5 rung 2: the cap is a page size now, so the sentence that
    # used to say 50 rows were withheld is gone — nothing is withheld.
    # Asserted on the rendered element: the bare class name also
    # appears in ``base.html``'s inline CSS, which ships on every page.
    assert '<p class="muted table-showing-hint">' not in body
    assert "more not shown" not in body
    # What replaced it, and the proof it is not a lie: the range is
    # linked, and the row past the page is one click away.
    assert "201–250" in body
    page_two = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?offset=200"
    ).text
    table_two = page_two[page_two.find('id="reviewers-table"') :]
    assert "R0200" in table_two
    assert "R0249" in table_two
    assert "R0199" not in table_two


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
    # A filtered view carries no pager, so the 500 cap still
    # truncates for real and still says so — in 19J.5's wording.
    assert "Showing 500 of 600 reviewers, 100 more not shown." in body


def test_capped_and_filtered_counts_against_the_matching_set(
    db: Session, client: TestClient
) -> None:
    """The state nothing covered before Segment 19I Item 10.

    `test_filtered_cap_lifts_to_500` above looks like it covers it,
    but every one of its 600 rows matches `status=active`, so the
    matching set and the whole roster are the same number and the
    two readings of the denominator coincide. Here they differ: 600
    reviewers, 550 matching, 500 rendered.

    The denominator must be 550, not 600 — the cap withheld 50 rows,
    not 100. Counting the 50 the *filter* excluded would overstate
    what lifting the cap would reveal.
    """
    review_session = _make_session(client, db, code="rev-cap-and-filter")
    for i in range(600):
        db.add(
            Reviewer(
                session_id=review_session.id,
                name=f"R{i:04d}",
                email=f"r{i:04d}@example.edu",
                tag_1="Keep" if i < 550 else "Drop",
            )
        )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=Keep"
    ).text

    assert "Showing 500 of 550 reviewers, 50 more not shown." in body
    # The two numbers a wrong denominator would produce.
    assert "of 600" not in body
    assert "100 more not shown" not in body
    # 19J.5 dropped the qualifier: with the roster total gone, `of 550`
    # can only mean the matching set, so `matching` disambiguates
    # nothing.
    assert "matching reviewers" not in body


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
    # All five action affordances present. ``Add new row`` shortened
    # to ``Add`` in 19I Item 2 to make room for ``Delete``.
    for label in (
        ">Edit</button>",
        ">Inactivate</button>",
        ">Activate</button>",
        ">Add</a>",
        ">Delete</button>",
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


def test_delete_all_button_gated_by_confirm_checkbox(
    db: Session, client: TestClient
) -> None:
    """The destructive "Delete all reviewers" button conforms to
    the confirm-checkbox-gates-button standard — it ships
    `disabled` and is paired to the confirm checkbox by the
    `data-delete-confirm` / `data-delete-btn` attributes."""
    review_session = _make_session(client, db, code="rev-delete-gate")
    _seed_reviewers_via_orm(db, review_session.id, 2)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert 'data-delete-confirm="delete-all"' in body
    button = body[body.find('data-delete-btn="delete-all"') :][:200]
    assert "disabled" in button


# --------------------------------------------------------------------------- #
# Tag search + tag suggestions — Segment 19I Item 1.
#
# The predicates are unit-tested in tests/unit/test_roster_search_filters.py;
# these pin that the route hands them the whole roster and renders both
# halves of the suggestion list, which a correct predicate cannot do alone.
# --------------------------------------------------------------------------- #


def _tagged(session_id: int, name: str, tag: str) -> Reviewer:
    return Reviewer(
        session_id=session_id,
        name=name,
        email=f"{name.lower()}@example.edu",
        tag_1=tag,
    )


def test_searching_a_tag_value_narrows_the_table(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-f-tag")
    db.add_all(
        [
            _tagged(review_session.id, "Ana", "TW01"),
            _tagged(review_session.id, "Ben", "TW02"),
        ]
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=TW01"
    ).text
    table = body[body.find('id="reviewers-table"') :]

    assert "Ana" in table
    assert "Ben" not in table


def test_the_datalist_offers_distinct_tag_values(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-f-tag-list")
    db.add_all(
        [
            _tagged(review_session.id, "Ana", "TW01"),
            _tagged(review_session.id, "Ben", "TW01"),
            _tagged(review_session.id, "Cai", "TW02"),
        ]
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    datalist = body[body.find('id="reviewers-search-options"') :]
    datalist = datalist[: datalist.find("</datalist>")]

    assert datalist.count('<option value="TW01">') == 1, "one option per value"
    assert '<option value="TW02">' in datalist
    assert '<option value="Ana (ana@example.edu)">' in datalist


def test_a_tag_is_offered_even_when_its_rows_fall_past_the_cap(
    db: Session, client: TestClient
) -> None:
    """The reachability case at page level: 600 rows exceed the 500
    filtered cap and the 200 unfiltered one, so the operator cannot
    scroll to the rare row — but its group is in the list, and picking
    it brings the row into the window."""
    review_session = _make_session(client, db, code="rev-f-tag-cap")
    _seed_reviewers_via_orm(db, review_session.id, 600)
    db.add(_tagged(review_session.id, "Zed", "Rare"))
    db.commit()

    unfiltered = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    datalist = unfiltered[unfiltered.find('id="reviewers-search-options"') :]
    datalist = datalist[: datalist.find("</datalist>")]
    assert '<option value="Rare">' in datalist

    picked = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=Rare"
    ).text
    table = picked[picked.find('id="reviewers-table"') :]
    assert "Zed" in table
