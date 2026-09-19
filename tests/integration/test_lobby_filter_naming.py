"""The lobby and Archive controls are filters, and now say so.

19O Item 7 entry 15. The author asked why the search box had no search
button; it had none because it is not a search box. Both controls hide
rows already rendered, live on every keystroke, and never query or
navigate — so there is nothing to submit, and the `Cancel` that sat
beside a `Search` heading was cancelling nothing.

These cases pin the naming, not the matching. What the filter *matches*
is rung 2's.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _create(client: TestClient, name: str, code: str) -> None:
    client.post(
        "/operator/sessions",
        data={"name": name, "code": code},
        follow_redirects=False,
    )


def _archive(db: Session, code: str) -> None:
    row = (
        db.query(ReviewSession).filter(ReviewSession.code == code).one()
    )
    row.status = "archived"
    db.flush()


LOBBY = "/operator/sessions"
ARCHIVE = "/operator/sessions/archived"


@pytest.mark.parametrize("path", [LOBBY, ARCHIVE])
def test_the_card_is_headed_filter_not_search(
    client: TestClient, db: Session, path: str
) -> None:
    """Both pages carry the same control and now give it the same name."""
    _create(client, "Spring Review", "spring-1")
    _create(client, "Archived One", "arch-1")
    _archive(db, "arch-1")

    body = client.get(path).text
    assert "<h2>Filter</h2>" in body
    assert "<h2>Search</h2>" not in body


@pytest.mark.parametrize("path", [LOBBY, ARCHIVE])
def test_the_input_says_filter_in_its_placeholder_and_label(
    client: TestClient, db: Session, path: str
) -> None:
    """The placeholder and the accessible name are what a screen-reader
    user and a sighted user respectively meet first."""
    _create(client, "Spring Review", "spring-2")
    _create(client, "Archived Two", "arch-2")
    _archive(db, "arch-2")

    body = client.get(path).text
    assert "Filter by name, code, or tag" in body
    assert "Search by name, code, or tag" not in body
    assert 'aria-label="Filter' in body
    assert 'aria-label="Search' not in body


@pytest.mark.parametrize("path", [LOBBY, ARCHIVE])
def test_the_button_clears_rather_than_cancels(
    client: TestClient, db: Session, path: str
) -> None:
    """`Cancel` implies something in flight to abandon. A live filter has
    nothing in flight; the button empties the box, which is `Clear` —
    the same word the tag chips' own reset already uses."""
    _create(client, "Spring Review", "spring-3")
    _create(client, "Archived Three", "arch-3")
    _archive(db, "arch-3")

    body = client.get(path).text
    # Scoped to the filter card's own button. Both pages carry legitimate
    # `Cancel` controls elsewhere — the row expander's, which abandons an
    # edit in flight and is correctly named. A blanket assertion here
    # matched those and failed for the right reason.
    assert "data-filter-clear>Clear</button>" in body
    assert "data-search-cancel" not in body


def test_the_disabled_lobby_control_is_also_named_clear(
    client: TestClient,
) -> None:
    """An empty lobby renders the card with the control inert rather than
    absent, because the card also holds the ways out of an empty lobby.
    The inert copy has to match the live copy or the name changes under
    the operator when their first session lands."""
    body = client.get(LOBBY).text

    assert "<h2>Filter</h2>" in body
    assert 'aria-disabled="true">Clear</span>' in body
    assert 'aria-disabled="true">Cancel</span>' not in body


def test_an_empty_lobby_filter_names_the_archive(
    client: TestClient, db: Session
) -> None:
    """A filter reports on the rows it was given, and the lobby is given
    non-archived sessions only. So an empty result is ambiguous between
    "no such session" and "it is archived" — and the Archive is the one
    place an operator would not think to look.

    Naming it is all a *filter* owes. A search would have owed the
    matching rows themselves.
    """
    _create(client, "Spring Review", "spring-4")

    body = client.get(LOBBY).text
    assert "Archived sessions are not listed here" in body
    assert 'href="/operator/sessions/archived"' in body


def test_the_archive_does_not_point_back_at_the_lobby(
    client: TestClient, db: Session
) -> None:
    """The asymmetry is deliberate. The Archive's own empty *page* copy
    already says where its rows come from ("Sessions you archive from
    the lobby appear here"), and an operator on the Archive knows they
    left the lobby to get there. The lobby's operator has no such cue."""
    _create(client, "Archived Four", "arch-4")
    _archive(db, "arch-4")

    body = client.get(ARCHIVE).text
    assert "No sessions match." in body
    assert "check the Archive" not in body
