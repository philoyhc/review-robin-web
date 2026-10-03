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


def _zip_all_query(page: Page) -> dict[str, list[str]]:
    href = page.locator("#extract-data-zip-all").get_attribute("href")
    assert href
    return parse_qs(urlsplit(href).query)


def test_zip_all_carries_each_cards_chips(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}/extract-data")
    instrument_chip = page.locator(
        "[data-by-instrument-chip^='instrument-']"
    ).first
    instrument_id = instrument_chip.get_attribute(
        "data-by-instrument-chip"
    ).removeprefix("instrument-")

    query = _zip_all_query(page)
    assert query["by_instrument.instrument"] == [instrument_id]
    assert query["reviewer_metadata.instrument"] == [instrument_id]
    assert query["reviewee_metadata.instrument"] == [instrument_id]

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
