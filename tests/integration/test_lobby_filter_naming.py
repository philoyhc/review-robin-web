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
from app.services import session_tags


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


# --------------------------------------------------------------------------- #
# The typeahead (19O Item 7 entry 15 rung 2)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path,list_id",
    [(LOBBY, "lobby-filter-options"), (ARCHIVE, "archived-filter-options")],
)
def test_the_filter_input_is_bound_to_a_datalist(
    client: TestClient, db: Session, path: str, list_id: str
) -> None:
    """A `<datalist>` present but unbound suggests nothing, and nothing
    in the rendered page would look wrong."""
    _create(client, "Spring Review", "spring-9")
    _create(client, "Archived Nine", "arch-9")
    _archive(db, "arch-9")

    body = client.get(path).text
    assert f'list="{list_id}"' in body
    assert f'<datalist id="{list_id}">' in body


def test_the_lobby_datalist_offers_names_codes_and_tags(
    client: TestClient, db: Session
) -> None:
    """All three of the fields the placeholder names.

    The tag comes back lower-cased: `session_tags.normalize_tag` trims
    and lowercases on write, so `Cohort A` is stored, displayed on the
    chips and suggested here as `cohort a`. That is why the filter's
    whole-value tag comparison lowercases the typed term — the stored
    side is already lower, but the operator's typing is not.
    """
    _create(client, "Spring Review", "spring-10")
    row = (
        db.query(ReviewSession)
        .filter(ReviewSession.code == "spring-10")
        .one()
    )
    session_tags.set_tags(
        db,
        review_session=row,
        user=row.created_by_user,
        tags=["Cohort A"],
    )
    db.flush()

    body = client.get(LOBBY).text
    assert '<option value="Spring Review">' in body
    assert '<option value="spring-10">' in body
    assert '<option value="cohort a">' in body


def test_the_datalists_do_not_cross_the_archive_boundary(
    client: TestClient, db: Session
) -> None:
    """Each page filters its own half, so each page suggests its own
    half. A lobby suggestion naming an archived session would be a
    suggestion that matches no row on the page offering it."""
    _create(client, "Live One", "live-11")
    _create(client, "Archived Eleven", "arch-11")
    _archive(db, "arch-11")

    lobby = client.get(LOBBY).text
    archive = client.get(ARCHIVE).text

    assert '<option value="Live One">' in lobby
    assert '<option value="Archived Eleven">' not in lobby
    assert '<option value="Archived Eleven">' in archive
    assert '<option value="Live One">' not in archive
