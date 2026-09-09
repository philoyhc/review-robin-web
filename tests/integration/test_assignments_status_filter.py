"""The Assignments strip can filter by the status its buttons set.

Segment 19I Item 9 PR 1. `Assignment.include` is the boolean the
strip's **Inactivate** / **Activate** buttons flip, and rows with
`include=False` already render dimmed — the state was visible and
**unfilterable**, so an operator could bulk-inactivate fifty rows and
have no way to list them back.

The filter is the roster pages' shape (All / Active / Inactive) and
composes with the search into `Showing N of M`, as
`views/_filters.py` puts it: *"Filters compose: status + search"*.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment
from app.services import assignments

from ._assignment_states import seed_session_with_assignment as _seed


def _one_inactive(db: Session, session_id: int) -> int:
    """Flip the first pair to `include=False`, leaving the second
    active. Returns the inactivated row's id."""
    row = db.execute(
        select(Assignment)
        .where(Assignment.session_id == session_id)
        .order_by(Assignment.id)
    ).scalars().first()
    row.include = False
    db.commit()
    return row.id


@pytest.mark.parametrize(
    ("status", "expected"),
    (("all", 2), ("active", 1), ("inactive", 1), ("nonsense", 2)),
)
def test_count_pairs_filters_by_status(
    db: Session, client: TestClient, status: str, expected: int
) -> None:
    """`all` and anything unrecognised fall through to everything, as
    the roster pages do."""
    s = _seed(client, db, code=f"asf-count-{status}")
    _one_inactive(db, s.id)

    assert assignments.count_pairs(db, s.id, status=status) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    (("all", 2), ("active", 1), ("inactive", 1)),
)
def test_list_pairs_agrees_with_the_count(
    db: Session, client: TestClient, status: str, expected: int
) -> None:
    s = _seed(client, db, code=f"asf-list-{status}")
    _one_inactive(db, s.id)

    rows = assignments.list_pairs(db, s.id, status=status)
    count = assignments.count_pairs(db, s.id, status=status)

    assert len(rows) == expected
    assert count == expected


def test_status_returns_the_row_it_names(
    db: Session, client: TestClient
) -> None:
    """Not just the right number — the right row."""
    s = _seed(client, db, code="asf-which")
    inactive_id = _one_inactive(db, s.id)

    assert [r.id for r in assignments.list_pairs(db, s.id, status="inactive")] == [
        inactive_id
    ]
    assert inactive_id not in [
        r.id for r in assignments.list_pairs(db, s.id, status="active")
    ]


def test_status_and_search_compose(
    db: Session, client: TestClient
) -> None:
    """`Team B` matches one pair (the reviewee's tag). Narrowing that
    to `inactive` must intersect, not replace."""
    s = _seed(client, db, code="asf-compose")
    _one_inactive(db, s.id)

    both = assignments.count_pairs(
        db, s.id, search="Team B", search_by="all", status="all"
    )
    assert both == 1

    # The `Team B` pair is the first one, which `_one_inactive` flipped.
    assert (
        assignments.count_pairs(
            db, s.id, search="Team B", search_by="all", status="inactive"
        )
        == 1
    )
    assert (
        assignments.count_pairs(
            db, s.id, search="Team B", search_by="all", status="active"
        )
        == 0
    )


def test_the_page_renders_the_status_select(
    db: Session, client: TestClient
) -> None:
    s = _seed(client, db, code="asf-page")

    body = client.get(f"/operator/sessions/{s.id}/assignments").text

    assert '<select name="status">' in body
    assert ">Active</option>" in body
    assert ">Inactive</option>" in body


def test_the_hint_counts_both_filters(
    db: Session, client: TestClient
) -> None:
    s = _seed(client, db, code="asf-hint")
    _one_inactive(db, s.id)

    body = client.get(
        f"/operator/sessions/{s.id}/assignments?status=active"
    ).text

    assert "Showing 1 of 2 assignments." in body


def test_the_column_chips_ignore_the_status_filter(
    db: Session, client: TestClient
) -> None:
    """`col_data_sample` is built unfiltered on purpose — the chips'
    enabled state must not flip because the operator narrowed the
    view. The template comment says so for the search; the status
    filter inherits the same rule.

    Asserts the **enabled** chip set (`is-selected`), and that it is
    non-empty: an earlier draft matched `data-col-chip`, an attribute
    that does not exist, so it compared `[] == []` and would have
    passed whatever the code did.
    """
    import re

    s = _seed(client, db, code="asf-chips")
    _one_inactive(db, s.id)

    def enabled_chips(body: str) -> list[str]:
        return sorted(
            re.findall(
                r'class="pill pill-count tag-chip is-selected"\s+data-col-toggle="([^"]+)"',
                body,
            )
        )

    active_only = enabled_chips(
        client.get(f"/operator/sessions/{s.id}/assignments?status=active").text
    )
    unfiltered = enabled_chips(
        client.get(f"/operator/sessions/{s.id}/assignments").text
    )

    assert unfiltered, "fixture must leave some chip enabled or this proves nothing"
    assert active_only == unfiltered


def test_an_unrecognised_status_is_normalised_before_it_round_trips(
    db: Session, client: TestClient
) -> None:
    """The service falls through on an unknown status, so filtering is
    safe either way — but the value also rides the bulk form's hidden
    `filter_status` field and comes back on the next request. Without
    the route-level normalisation the junk persists in the form.

    Pinned because removing that normalisation changed nothing else:
    the whole file passed with it gone.
    """
    s = _seed(client, db, code="asf-junk")

    body = client.get(
        f"/operator/sessions/{s.id}/assignments?status=nonsense"
    ).text

    assert '<input type="hidden" name="filter_status" value="all">' in body
    assert "nonsense" not in body
