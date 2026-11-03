"""The Upload card's spacing, in a real browser (margins collapse, which
no unit test sees). Segment 20I Item 3: the banner stack sits 16px below
the intro and 16px above the form. Item 4: the directory line, or the
countdown alone, sits 8px under the buttons."""

from __future__ import annotations

from collections.abc import Callable

import pytest

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


@pytest.mark.parametrize(
    ("addresses", "under"),
    [
        # A row unmatched: the recheck's form sits before the line.
        (["nobody@example.edu"], "[data-directory-check]"),
        # Every row matched: no recheck form, the upload form before it.
        (["jane.tan@example.edu"], "[data-directory-check]"),
        # No import yet: the countdown alone, once the script shows it.
        ([], "[data-directory-countdown]"),
    ],
    ids=["after-recheck-form", "after-upload-form", "countdown-alone"],
)
def test_the_directory_line_sits_8px_under_the_buttons(
    page: Page, new_session: Callable[[], str], tmp_path, addresses: list[str], under: str
) -> None:
    """Segment 20I Item 4: whatever comes first under the actions row sits
    8px below the buttons, as far as the line's paragraphs sit apart."""
    session_id = new_session()
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1#upload-csv"))
    if addresses:
        roster = tmp_path / "r.csv"
        roster.write_text(
            "ReviewerName,ReviewerEmail\n" + "".join(f"P,{a}\n" for a in addresses)
        )
        form = page.locator("#upload-csv-form")
        form.locator('input[name="file"]').set_input_files(str(roster))
        with page.expect_navigation():
            form.evaluate("f => f.submit()")
    card = page.locator("#upload-csv")
    expect(card.locator("[data-directory-recheck]")).to_have_count(
        1 if addresses == ["nobody@example.edu"] else 0
    )
    card.evaluate("c => { c.querySelector('[data-directory-countdown]').hidden = false; }")
    gap = card.evaluate(
        f"""card => Math.round(
          card.querySelector('{under}').getBoundingClientRect().top
          - card.querySelector('.unlock-col-actions').getBoundingClientRect().bottom)"""
    )
    assert gap == 8
