"""A timezone change keeps the stored instants (findings L8, author's ruling).

Changing the Timezone field, on Create and on Session Home's details card,
re-renders every date box as the same instant in the new zone, so a Save
stores what the boxes showed before the change. The no-script half, the
server keeping a box still holding its old-zone text, is
``tests/integration/test_display_timezone.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, timedelta

import httpx
from playwright.sync_api import Page, expect

_CREATE_BOXES = (
    "#scheduled_activate_at",
    "#deadline",
    "#responses_release_at",
    "#responses_release_until",
)
_HOME_BOXES = ("#mock-start", "#mock-end", "#mock-release-from", "#mock-release-until")


def test_create_re_renders_every_box_and_stores_the_instants(page: Page) -> None:
    code = f"z{uuid.uuid4().hex[:8]}"
    page.goto("/operator/sessions/new")
    page.locator("#name").fill(f"Zone {code}")
    page.locator("#code").fill(code)
    page.locator("#display_timezone").fill("UTC")
    utc = ("2027-03-01T09:00", "2027-03-01T12:00", "2027-03-02T09:00", "2027-03-05T09:00")
    for box, value in zip(_CREATE_BOXES, utc):
        page.locator(box).fill(value)

    page.locator("#display_timezone").fill("GMT+8 Asia/Singapore")

    singapore = ("2027-03-01T17:00", "2027-03-01T20:00", "2027-03-02T17:00", "2027-03-05T17:00")
    for box, value in zip(_CREATE_BOXES, singapore):
        expect(page.locator(box)).to_have_value(value)
    # The ordering script's bounds moved with the boxes: Start's max is
    # End's new text, not its old one, or the submit would be blocked.
    expect(page.locator("#scheduled_activate_at")).to_have_attribute(
        "max", "2027-03-01T20:00"
    )
    with page.expect_navigation():
        page.locator("#create-session-submit").click()
    page.wait_for_load_state("load")

    assert "/operator/sessions/" in page.url and "/new" not in page.url
    expect(page.locator("#mock-timezone")).to_have_value("GMT+8 Asia/Singapore")
    for box, value in zip(_HOME_BOXES, utc):
        expect(page.locator(box)).to_have_attribute("data-tz-utc", value)


def _second_half_hour_after_fall_back() -> tuple[str, str]:
    """The second 01:30 in New York on next year's fall-back day (the
    first Sunday of November), as UTC and as New York wall-clock."""
    first = date(date.today().year + 1, 11, 1)
    sunday = first + timedelta(days=(6 - first.weekday()) % 7)
    return f"{sunday}T06:30", f"{sunday}T01:30"


def test_session_home_re_renders_from_the_stored_instant(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Seeded in the repeated hour after a DST fall-back, a box's text
    names two instants; the conversion starts from the stored one."""
    session_id = new_session()
    code = (
        api.get(f"/operator/sessions/{session_id}?editing=1")
        .text.split('id="mock-code"', 1)[1]
        .split('value="', 1)[1]
        .split('"', 1)[0]
    )
    in_utc, in_new_york = _second_half_hour_after_fall_back()

    def save(zone: str) -> None:
        response = api.post(
            f"/operator/sessions/{session_id}/config",
            data={"name": "Zones", "code": code, "display_timezone": zone,
                  "deadline": in_utc},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text

    save("UTC")
    save("America/New_York")  # the UTC text, untouched: the instant stays
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    end = page.locator("#mock-end")
    expect(end).to_have_value(in_new_york)
    expect(end).to_have_attribute("data-tz-utc", in_utc)

    zone = page.locator("#mock-timezone")
    zone.fill("UTC")
    # Read from its text, 01:30 would be the first one, 05:30 UTC.
    expect(end).to_have_value(in_utc)

    # Cancel resets the boxes and the zone, and the script with them;
    # Unlock reopens the card in place.
    page.locator("[data-config-cancel]").click()
    page.locator("[data-config-lock-toggle]").click()
    expect(end).to_have_value(in_new_york)
    converted = page.locator('input[name="tz_converted"]')
    expect(converted).to_have_value("")
    zone.fill("Asia/Tokyo")
    tokyo = in_utc.replace("T06:30", "T15:30")
    expect(end).to_have_value(tokyo)
    # The form names the boxes the script re-rendered, so the server reads
    # old-zone text typed back into one as an edit (the read of #3113).
    expect(converted).to_have_value("deadline")

    with page.expect_navigation():
        page.locator("[data-config-save]").click()
    page.wait_for_load_state("load")
    expect(end).to_have_attribute("data-tz-utc", in_utc)
    expect(end).to_have_value(tokyo)


def test_create_reads_a_skipped_day_as_the_server_does(page: Page) -> None:
    """Pacific/Apia skipped 2011-12-30 whole; a box naming a time on it
    reads, as ``parse_local_datetime`` does, at the offset before the
    jump (08:00 UTC on the 31st), not a day off (the read of #3113)."""
    page.goto("/operator/sessions/new")
    page.locator("#display_timezone").fill("Pacific/Apia")
    page.locator("#responses_release_at").fill("2011-12-30T22:00")
    page.locator("#display_timezone").fill("UTC")
    expect(page.locator("#responses_release_at")).to_have_value("2011-12-31T08:00")
