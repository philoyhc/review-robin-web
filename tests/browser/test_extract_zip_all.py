"""The Extract data page's Zip all follows the other cards' chips (D28).

The intro card's Zip all is a pass-through: each of its chips that is
on adds what that card's own button downloads, as the card's chips set
it. The route side is pinned in
``tests/integration/test_extracts_responses_bundle_route.py``; this
drives the page script that composes the link from the chips, which
the template tests cannot run.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.sync_api import Page

from ._builder import add_instrument


def _zip_all_query(page: Page) -> dict[str, list[str]]:
    href = page.locator("#extract-data-zip-all").get_attribute("href")
    assert href
    return parse_qs(urlsplit(href).query)


def test_zip_all_carries_each_cards_chips(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}/extract-data")

    # Every instrument chip on: no id lists, so the link stays short
    # however many instruments the session has (Codex on #2769).
    query = _zip_all_query(page)
    assert not any(key.endswith(".instrument") for key in query)
    assert query["reviewer_metadata.all_instruments"] == ["1"]
    assert query["reviewee_metadata.all_instruments"] == ["1"]

    page.locator("[data-by-instrument-chip='include-metadata']").click()
    page.locator(
        "[data-self-review-handling-chip='reviewer-metadata']"
    ).click()
    page.locator("[data-extract-all-chip='reviewee-metadata']").click()
    page.locator("[data-extract-all-chip='data-shaper']").click()

    query = _zip_all_query(page)
    assert query["by_instrument.meta"] == ["0"]
    assert query["reviewer_metadata.self_review_handling"] == [
        "exclude_self"
    ]
    assert query["reviewee_metadata"] == ["0"]
    assert not any(key.startswith("reviewee_metadata.") for key in query)
    assert query["data_shapes"] == ["0"]

    href = page.locator("#extract-data-zip-all").get_attribute("href")
    response = api.get(href)
    assert response.status_code == 200, response.text
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert any(name.endswith("_responses.csv") for name in names)
    assert any(name.endswith("_reviewer_metadata_noself.csv") for name in names)
    assert not any("reviewee_metadata" in name for name in names)
    assert sum("_by_instrument_" in name for name in names) == 1


def test_a_by_instrument_card_with_nothing_chosen_rides_as_off(
    page: Page, new_session: Callable[[], int]
) -> None:
    """The card's own Zip all greys out with no instrument chip on;
    the intro's Zip all leaves its files out rather than asking for
    every instrument, which is what an omitted list means."""
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}/extract-data")
    page.locator("[data-by-instrument-chip^='instrument-']").first.click()

    card_zip = page.locator("#extract-data-by-instrument-zip")
    assert card_zip.get_attribute("aria-disabled") == "true"
    query = _zip_all_query(page)
    assert query["by_instrument"] == ["0"]
    assert not any(key.startswith("by_instrument.") for key in query)


def test_a_partial_selection_lists_its_ids(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """With two instruments and one chip off, each card lists the one
    left on, both on its own link and in Zip all; with both on again,
    no list rides (second D28 URL-bound read)."""
    session_id = new_session()
    add_instrument(api, session_id)
    page.goto(f"/operator/sessions/{session_id}/extract-data")
    for card in ("by-instrument", "reviewer-metadata", "reviewee-metadata"):
        chips = page.locator(f"[data-{card}-chip^='instrument-']")
        assert chips.count() == 2
        chips.nth(0).click()
    kept = (
        page.locator("[data-by-instrument-chip^='instrument-']")
        .nth(1)
        .get_attribute("data-by-instrument-chip")
        .removeprefix("instrument-")
    )

    query = _zip_all_query(page)
    for flag in ("by_instrument", "reviewer_metadata", "reviewee_metadata"):
        assert query[f"{flag}.instrument"] == [kept]
        assert f"{flag}.all_instruments" not in query
    for card, path in (
        ("by-instrument", "by_instrument_bundle.zip"),
        ("reviewer-metadata", "reviewer_metadata.csv"),
        ("reviewee-metadata", "reviewee_metadata.csv"),
    ):
        href = page.locator(f"#extract-data-{card}-zip").get_attribute("href")
        assert path in href
        assert parse_qs(urlsplit(href).query)["instrument"] == [kept]

    for card in ("by-instrument", "reviewer-metadata", "reviewee-metadata"):
        page.locator(f"[data-{card}-chip^='instrument-']").nth(0).click()
    query = _zip_all_query(page)
    assert not any(key.endswith(".instrument") for key in query)
    href = page.locator("#extract-data-reviewer-metadata-zip").get_attribute("href")
    assert parse_qs(urlsplit(href).query) == {"all_instruments": ["1"]}
