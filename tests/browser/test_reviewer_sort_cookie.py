"""A response-column sort persisted in the cookie orders the rows on load
(ruling A27).

The server cannot sort by response values. When the reviewer's cookie
holds a ``response:N`` key it renders the operator default instead, and
the on-load script redraws the badges and re-sorts the rows through the
click path's ``_rrwApplySort``. Without that step a reload shows ``1↑``
over rows in server order; with it, but over any order other than the
operator default, rows tied on the sort land differently after a reload
than after a click.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.parse import quote

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from ._builder import REVIEWER_EMAIL, activate
from .conftest import LiveServer

#: Listed out of name and score order, so the roster's (assignment) order
#: is none of the orders asserted below.
REVIEWEES_CSV = (
    b"RevieweeName,RevieweeEmail\n"
    b"Bravo,bravo@example.edu\n"
    b"Delta,delta@example.edu\n"
    b"Alpha,alpha@example.edu\n"
    b"Charlie,charlie@example.edu\n"
    b"Echo,echo@example.edu\n"
)


def _seed(api: httpx.Client, session_id: int) -> None:
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\n"),
        ("reviewees", REVIEWEES_CSV),
    ):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


def _save_ratings(
    database_url: str,
    session_id: int,
    ratings: dict[str, str],
    *,
    operator_default_name_dir: str | None = None,
) -> tuple[int, int]:
    """Write the default instrument's Integer 1-5 "Rating" answers (and,
    if asked, an operator-default sort by reviewee name) directly, as
    ``_builder.pin_full_matrix`` writes its pin. A reviewee missing from
    ``ratings`` has a blank cell. Returns (instrument id, Rating field id).
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import (
        Assignment,
        Instrument,
        InstrumentDisplayField,
        InstrumentResponseField,
        Response,
    )

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(Instrument.session_id == session_id)
            ).scalar_one()
            rating = db.execute(
                select(InstrumentResponseField).where(
                    InstrumentResponseField.instrument_id == instrument.id,
                    InstrumentResponseField.field_key == "rating",
                )
            ).scalar_one()
            assignments = db.execute(
                select(Assignment).where(Assignment.instrument_id == instrument.id)
            ).scalars()
            for assignment in assignments:
                value = ratings.get(assignment.reviewee.name)
                if value is not None:
                    db.add(
                        Response(
                            assignment_id=assignment.id,
                            response_field_id=rating.id,
                            value=value,
                        )
                    )
            if operator_default_name_dir is not None:
                name_field = db.execute(
                    select(InstrumentDisplayField).where(
                        InstrumentDisplayField.instrument_id == instrument.id,
                        InstrumentDisplayField.source_field == "name",
                    )
                ).scalar_one()
                instrument.sort_display_fields = [
                    {"display_field_id": name_field.id, "dir": operator_default_name_dir}
                ]
            db.commit()
            return instrument.id, rating.id
    finally:
        engine.dispose()


def _row_names(reviewer: Page) -> list[str]:
    return reviewer.locator("tbody.rrw-rows td.rs-reviewee").evaluate_all(
        "cells => cells.map(td => td.getAttribute('data-sort-value'))"
    )


def _badge(reviewer: Page, rating_id: int) -> Locator:
    return reviewer.locator(
        f"th[data-sort-key='response:{rating_id}'] .rrw-sort-badge"
    )


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("asc", ["Charlie", "Bravo", "Alpha", "Echo", "Delta"]),
        ("desc", ["Alpha", "Bravo", "Charlie", "Echo", "Delta"]),
    ],
)
def test_a_response_only_sort_cookie_orders_rows_on_load(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
    direction: str,
    expected: list[str],
) -> None:
    """A cookie set the way the primitive writes it (percent-encoded):
    rows follow the Rating with blank cells last, the blanks (Delta,
    Echo) in operator-default order (name descending). The default pins
    the tie: the roster's own order is not stable across runs."""
    session_id = new_session()
    _seed(api, session_id)
    activate(api, live_server.database_url, session_id)
    instrument_id, rating_id = _save_ratings(
        live_server.database_url,
        session_id,
        {"Alpha": "5", "Bravo": "4", "Charlie": "2"},
        operator_default_name_dir="desc",
    )

    reviewer = page_as(REVIEWER_EMAIL)
    url = f"/me/sessions/{session_id}/1"
    reviewer.goto(url)
    assert _row_names(reviewer) == ["Echo", "Delta", "Charlie", "Bravo", "Alpha"]

    reviewer.context.add_cookies(
        [
            {
                "name": f"rrw-sort-rs-{session_id}-{instrument_id}",
                "value": quote(
                    json.dumps([{"key": f"response:{rating_id}", "dir": direction}]),
                    safe="",
                ),
                "url": f"{live_server.base_url}/me/sessions/{session_id}",
            }
        ]
    )
    reviewer.goto(url)
    expect(_badge(reviewer, rating_id)).to_have_text("1↑" if direction == "asc" else "1↓")
    assert _row_names(reviewer) == expected


@pytest.mark.parametrize(
    ("clicks", "expected"),
    [
        (1, ["Charlie", "Bravo", "Alpha", "Echo", "Delta"]),
        (2, ["Bravo", "Alpha", "Charlie", "Echo", "Delta"]),
    ],
)
def test_a_reload_orders_tied_rows_as_the_click_did(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
    clicks: int,
    expected: list[str],
) -> None:
    """Alpha and Bravo tie on 4, and Delta and Echo are both blank. A
    click breaks those ties by the operator default (name descending),
    the order it found the rows in; so must the reload the click's
    cookie leads to."""
    session_id = new_session()
    _seed(api, session_id)
    activate(api, live_server.database_url, session_id)
    _, rating_id = _save_ratings(
        live_server.database_url,
        session_id,
        {"Alpha": "4", "Bravo": "4", "Charlie": "2"},
        operator_default_name_dir="desc",
    )

    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.goto(f"/me/sessions/{session_id}/1")
    assert _row_names(reviewer) == ["Echo", "Delta", "Charlie", "Bravo", "Alpha"]
    button = reviewer.locator(f"th[data-sort-key='response:{rating_id}'] .rrw-sort-btn")
    for _ in range(clicks):
        button.click()
    badge_text = "1↑" if clicks == 1 else "1↓"
    expect(_badge(reviewer, rating_id)).to_have_text(badge_text)
    assert _row_names(reviewer) == expected

    reviewer.reload()
    expect(_badge(reviewer, rating_id)).to_have_text(badge_text)
    assert _row_names(reviewer) == expected
