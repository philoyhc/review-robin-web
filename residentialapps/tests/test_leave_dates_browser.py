"""Apply's live check of the dates (author, 2026-11-09), in a real
Chromium: keying in dates fills Days of leave and its message from the
server's check, and Submit opens only once they pass. And Leave records'
period, applied on choosing it (author, 2026-11-10). Served as the sort
tests are; without a Chromium build the test skips, saying why, and
`RRW_REQUIRE_BROWSER=1` fails it."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from residentialapps.tests.test_sort_persistence_browser import (  # noqa: F401  (the fixture)
    ORIGIN,
    page,
)


def test_keyed_in_dates_are_checked_and_open_submit(page: Page) -> None:  # noqa: F811
    # At the default, By invitation, Chloe Lim is not invited: more than her
    # balance is refused.
    page.goto(ORIGIN + "/ra-leave/apply")
    submit = page.locator("#send")
    expect(submit).to_be_disabled()
    # 7 Dec – 11 Dec: Chloe covers no one then (she covers Ethan Wong on
    # 4 Dec – 6 Dec and Hana Ito on 14 Dec – 15 Dec).
    page.fill("#first", "2026-12-07")
    page.fill("#last", "2026-12-06")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days-note")).to_have_text("The last day is before the first day.")
    expect(submit).to_be_disabled()
    page.fill("#last", "2026-12-11")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days")).to_have_text("5 days")
    expect(page.locator("#days-note")).to_have_text(
        "3 days more than your Personal leave (2 available): shorten it."
    )
    page.fill("#last", "2026-12-08")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days")).to_have_text("2 days")
    expect(page.locator("#days-note")).to_have_text("")
    expect(submit).to_be_enabled()
    # Dates she covers someone on are refused (author, 2026-11-10).
    page.fill("#first", "2026-12-04")
    page.fill("#last", "2026-12-05")
    page.locator("#last").dispatch_event("change")
    expect(page.locator("#days-note")).to_have_text(
        "You are covering Ethan Wong on 4 Dec – 6 Dec: you cannot be on leave then."
    )
    expect(submit).to_be_disabled()


def test_leave_records_apply_a_period_on_choosing_it_and_stay_at_the_top(
    page: Page,  # noqa: F811
) -> None:
    """Author, 2026-11-10: no Show period button; choosing a period reloads
    with it, the chips' state kept, at the top of the page, as a chip does."""
    page.set_viewport_size({"width": 1366, "height": 600})
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee&hide=Rejected")
    expect(page.locator("#period-form button")).to_have_count(0)  # noscript only
    page.evaluate("window.scrollTo(0, 300)")
    with page.expect_navigation():
        page.select_option("#period", "whole")
    assert "period=whole" in page.url and "Rejected" in page.url
    assert page.evaluate("window.scrollY") == 0
    expect(page.locator("#period")).to_have_value("whole")
    page.locator("#rec-filters > summary").click()  # Filters starts closed
    page.evaluate("window.scrollTo(0, 300)")
    with page.expect_navigation():
        page.locator(".rec-filters").nth(2).locator("a", has_text="Clear all").click()  # Precinct
    assert page.evaluate("window.scrollY") == 0
    assert "period=whole" in page.url


def test_leave_records_wait_for_a_forward_range(page: Page) -> None:  # noqa: F811
    """Codex, 2026-11-10: a From moved past To waits for To instead of
    submitting a backwards range; a forward one applies."""
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    page.fill("#from", "2026-12-01")
    page.locator("#from").dispatch_event("change")
    page.wait_for_timeout(300)
    assert "period=custom" not in page.url  # no reload: To still 3 Nov
    with page.expect_navigation():
        page.fill("#to", "2026-12-31")
        page.locator("#to").dispatch_event("change")
    assert "from=2026-12-01" in page.url and "to=2026-12-31" in page.url


def test_leave_records_filters_start_closed_and_columns_hide_and_stay(
    page: Page,  # noqa: F811
) -> None:
    """Author, 2026-11-10: the chips sit in a Filters expander, closed
    until opened, its summary naming what is off; a column chip hides its
    column at once, and the browser keeps both choices."""
    page.goto(ORIGIN + "/ra-leave/admin/records?hide=Rejected")
    assert not page.evaluate("document.getElementById('rec-filters').open")
    expect(page.locator("#rec-off")).to_have_text(" · 1 off: Rejected")
    page.locator("#rec-filters > summary").click()
    page.locator('[data-col-toggle="submitted"]').click()
    expect(page.locator("#rec-off")).to_have_text(" · 2 off: Rejected; column Submitted")
    expect(page.locator('#rec-table th[data-col="submitted"]')).to_be_hidden()
    page.reload()
    assert not page.evaluate("document.getElementById('rec-filters').open")  # starts closed
    expect(page.locator('#rec-table th[data-col="submitted"]')).to_be_hidden()
    page.locator("#rec-filters > summary").click()
    page.locator('[data-cols-all="false"]').click()
    expect(page.locator('#rec-table th[data-col="precinct"]')).to_be_hidden()
    page.locator('[data-cols-all="true"]').click()
    expect(page.locator('#rec-table th[data-col="submitted"]')).to_be_visible()


def test_leave_records_keep_the_period_and_chips_in_the_browser(
    page: Page,  # noqa: F811
) -> None:
    """Author, 2026-11-10: the selectors are kept in the browser. Only a
    choice made on the page is kept, per viewer; a visit naming no filter
    takes it back; a link naming its own (a tile, a back link) is shown as
    it is and does not overwrite it (the cold read)."""
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    with page.expect_navigation():
        page.select_option("#period", "term")
    page.locator("#rec-filters > summary").click()
    with page.expect_navigation():
        page.locator(".rec-filters").first.locator("a", has_text="Rejected").click()
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    page.wait_for_url("**period=term**")
    assert "Rejected" in page.url
    # A link naming its own filters shows them and keeps the choice.
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee&period=whole")
    expect(page.locator("#period")).to_have_value("whole")
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee")
    page.wait_for_url("**period=term**")
    # Another viewer keeps their own.
    page.goto(ORIGIN + "/ra-leave/staff/records")
    expect(page.locator("#period")).to_have_value("week")


def test_the_cover_tile_drill_down_is_not_kept(page: Page) -> None:  # noqa: F811
    """The cold read: a chip clicked on the tile's one-off view is kept
    without its `cover=unconfirmed`, so a later bare visit shows every
    application, the chip's choice kept."""
    page.goto(ORIGIN + "/ra-leave/admin/records?cover=unconfirmed&period=whole")
    page.locator("#rec-filters > summary").click()
    with page.expect_navigation():
        page.locator(".rec-filters").first.locator("a", has_text="Withdrawn").click()
    page.goto(ORIGIN + "/ra-leave/admin/records")
    page.wait_for_url("**hide=Withdrawn**")
    assert "cover=" not in page.url


def test_leave_records_name_box_narrows_rows_and_count(page: Page) -> None:  # noqa: F811
    """Author, 2026-11-10: the Name box keeps the rows whose RA or cover
    matches, the count following; Enter does not reload; no match says so;
    clearing it brings every row back."""
    page.goto(ORIGIN + "/ra-leave/staff/records?as=Sam%20Lee&period=whole")
    count = page.locator("#rec-h .count")
    total = count.inner_text()
    page.fill("#rec-who", "elise")
    expect(count).to_have_text("· 3")
    expect(page.locator("#rec-table tr[data-row]:visible")).to_have_count(3)
    url = page.url
    page.press("#rec-who", "Enter")
    assert page.url == url
    page.fill("#rec-who", "zzz")
    expect(page.locator("#rec-table tr[data-none]")).to_be_visible()
    page.fill("#rec-who", "")
    expect(count).to_have_text(total)
    expect(page.locator("#rec-table tr[data-none]")).to_be_hidden()
