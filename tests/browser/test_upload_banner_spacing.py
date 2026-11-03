"""Segment 20I Item 3: the Upload card's banner stack sits as far below
the card's intro as the last banner sits above the form, 16px each, in a
real browser (the margins collapse, which no unit test sees)."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from .conftest import app_url


def test_the_gap_above_the_first_banner_equals_the_gap_below_the_last(
    page: Page, new_session: Callable[[], str], tmp_path
) -> None:
    session_id = new_session()
    bad = tmp_path / "bad.csv"
    bad.write_text("Name,Mail\nAnn,ann@example.edu\n")  # no required columns
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1#upload-csv"))
    form = page.locator("#upload-csv-form")
    form.locator('input[name="file"]').set_input_files(str(bad))
    with page.expect_navigation():
        form.evaluate("f => f.submit()")

    card = page.locator("#upload-csv")
    banner = card.locator(".banner").first
    expect(banner).to_be_visible()
    gaps = card.evaluate(
        """card => {
          const intro = card.querySelector('.form-help');
          const banners = card.querySelectorAll('.banner');
          const first = banners[0].getBoundingClientRect();
          const last = banners[banners.length - 1].getBoundingClientRect();
          const form = card.querySelector('#upload-csv-form').getBoundingClientRect();
          return {
            above: Math.round(first.top - intro.getBoundingClientRect().bottom),
            below: Math.round(form.top - last.bottom),
          };
        }"""
    )
    assert gaps == {"above": 16, "below": 16}


def test_the_directory_line_sits_8px_under_the_buttons(
    page: Page, new_session: Callable[[], str], tmp_path
) -> None:
    """Segment 20I Item 4: the directory line under the actions row sits
    as far below the buttons as its paragraphs sit apart (8px), whether
    the element before it is the upload form or the recheck's form."""
    session_id = new_session()
    roster = tmp_path / "r.csv"
    roster.write_text("ReviewerName,ReviewerEmail\nAnn,nobody@example.edu\n")
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1#upload-csv"))
    form = page.locator("#upload-csv-form")
    form.locator('input[name="file"]').set_input_files(str(roster))
    with page.expect_navigation():
        form.evaluate("f => f.submit()")
    card = page.locator("#upload-csv")
    expect(card.locator("[data-directory-recheck]")).to_be_visible()
    gap = card.evaluate(
        """card => Math.round(
          card.querySelector('[data-directory-check]').getBoundingClientRect().top
          - card.querySelector('.unlock-col-actions').getBoundingClientRect().bottom)"""
    )
    assert gap == 8
