"""The roster upload cards' banners stack in one place (author,
2026-11-03; `spec/setup_pages.md` "The Upload card's banners"): under
the card's intro, above the form, in the order problems, directory
renew, group clear; the directory-check line and the countdown sit below
the form's actions (segment 20I Item 1, reversing 20G). A control inside one
names the form with `form=`, since it sits outside it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates" / "operator"
ORDER = (
    '{% include "operator/partials/_upload_problems.html" %}',
    '{% include "operator/partials/_directory_renew.html" %}',
    "data-group-clear-banner",
)
#: What each card carries: Relationships runs no directory check, and
#: Observers has no group answers to clear.
CARDS = {
    "reviewers": ORDER,
    "reviewees": ORDER,
    "observers": ORDER[:2],
    "relationships": (ORDER[0], ORDER[2]),
}


def _upload_card(kind: str) -> str:
    text = (TEMPLATES / f"session_{kind}.html").read_text(encoding="utf-8")
    start = text.index('id="upload-csv"')
    return text[start : text.index("</section>", start)]


@pytest.mark.parametrize("kind", sorted(CARDS))
def test_the_banners_stack_above_the_form_in_one_order(kind: str) -> None:
    card = _upload_card(kind)
    form = card.index('id="upload-csv-form"')
    intro = card.index('class="form-help"')
    positions = [card.index(marker) for marker in CARDS[kind]]
    assert all(intro < at < form for at in positions), kind
    assert positions == sorted(positions), kind
    if "_directory_check.html" in card:
        form_end = card.index("</form>", form)
        line = card.index("_directory_check.html")
        assert card.index("unlock-col-actions", form) < form_end < line, kind
        # The upload's countdown (20H Item 6) sits under the directory line.
        assert line < card.index("_directory_countdown.html"), kind


@pytest.mark.parametrize("kind", ["reviewers", "reviewees", "observers"])
def test_the_recheck_button_sits_left_of_upload(kind: str) -> None:
    """20I Item 1: first in the actions row, a plain button rather than a
    submit, shown only while a row is unmatched."""
    card = _upload_card(kind)
    actions = card.index("unlock-col-actions", card.index('id="upload-csv-form"'))
    recheck = card.index("data-directory-recheck")
    assert actions < recheck < card.index(">Upload</button>"), kind
    assert card.rindex("{% if directory_unmatched %}", 0, recheck) > actions, kind
    assert '<button class="btn secondary" type="button" data-directory-recheck>' in card, kind


@pytest.mark.parametrize("kind", ["reviewers", "reviewees", "relationships"])
def test_the_group_clear_controls_name_the_form(kind: str) -> None:
    card = _upload_card(kind)
    start = card.index("data-group-clear-banner")
    banner = card[start : card.index("{% endif %}\n", card.index("banner-actions", start))]
    assert re.search(r'<input type="checkbox" form="upload-csv-form"', banner), kind
    assert 'class="btn secondary" form="upload-csv-form"' in banner, kind


@pytest.mark.parametrize("kind", ["reviewers", "reviewees", "observers"])
def test_the_renew_banner_names_the_form(kind: str) -> None:
    """Outside the form, the renew banner's Dismiss submits nothing unless
    the include names `upload-csv-form` (the partial's `form=` hook)."""
    card = _upload_card(kind)
    include = card.index(ORDER[1])
    with_line = card[card.rindex("{% with", 0, include) : include]
    assert 'directory_renew_form = "upload-csv-form"' in with_line, kind
