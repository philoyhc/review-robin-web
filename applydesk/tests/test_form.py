"""The Form page (segment AD1B, rung 2): the form's own title and
description, then a card per question, text block, section and page
break, each type with its own fields and a summary that reads as the
page's script computes it. Nothing is saved."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from applydesk import sample_data
from applydesk.sample_data import FormCard, card_summary, kept_size
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"
BLANK = "n5wg8tjr3e"
FORM = f"/applydesk/operator/exercises/{EX}/form"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _form(client: TestClient, path: str = FORM) -> str:
    """The card list alone: the page also carries the blank cards that
    + New, + Section and + Page break clone (`<template>`)."""
    text = client.get(path).text
    return text[text.index('id="fb-cards"') : text.index('<template id="fb-new-field">')]


def test_the_form_page_shows_its_title_and_every_card(client: TestClient) -> None:
    page = client.get(FORM).text
    assert 'data-fb="title" value="Application form"' in page
    assert sample_data.FORM_DESCRIPTION in page
    text = _form(client)
    kinds = [k for k, _ in re.findall(r'data-kind="(\w+)"(?: data-type="(\w+)")?', text)]
    expected = [c.kind for c in sample_data.SAMPLE_FORM]
    assert kinds == expected
    for c in sample_data.SAMPLE_FORM:
        if c.kind == "field":
            assert f'value="{c.label}"' in text
            assert card_summary(c) in text


def test_every_type_is_in_the_type_menu(client: TestClient) -> None:
    text = client.get(FORM).text
    for key, label in sample_data.CARD_TYPES:
        assert f'<option value="{key}"' in text and f">{label}</option>" in text


def test_cards_load_collapsed_and_carry_their_buttons(client: TestClient) -> None:
    text = _form(client)
    assert re.search(r'data-kind="field"[^>]*data-open', text) is None
    fields = text.count('data-kind="field"')
    assert text.count('data-fc-act="replicate"') == fields  # a section has none
    for act in ("new", "section", "pagebreak", "delete"):
        assert text.count(f'data-fc-act="{act}"') >= fields
    assert text.count('aria-label="Move: drag, or press the up and down arrow keys"') == len(
        sample_data.SAMPLE_FORM
    )


def test_every_card_has_its_own_visibility(client: TestClient) -> None:
    text = _form(client)
    fields = [c for c in sample_data.SAMPLE_FORM if c.kind == "field"]
    assert text.count('aria-label="Who sees it"') == len(fields)
    shown = sum(c.shown for c in fields)
    assert (
        text.count('<span class="chip chip-info" data-sum="shown">Shown to reviewers</span>')
        == shown
    )


def test_nothing_is_saved(client: TestClient) -> None:
    text = client.get(FORM).text
    assert 'disabled title="Saving comes with the database (segment AD2)">Save</button>' in text
    assert "<form" not in text.split("<main", 1)[1]


def test_a_blank_form_opens_its_one_card(client: TestClient) -> None:
    page = client.get(f"/applydesk/operator/exercises/{BLANK}/form").text
    text = _form(client, f"/applydesk/operator/exercises/{BLANK}/form")
    assert text.count('data-kind="field"') == 1
    assert re.search(r'data-kind="field" data-type="string" data-open', text)
    assert 'value="" placeholder="Untitled form"' in page


# Every summary the page's script must also give: test_form_browser.py
# replays these in Chromium.
SUMMARY_CASES: list[tuple[FormCard, str]] = [
    (FormCard("field", "string"), "String"),
    (FormCard("field", "string", max="120"), "String · up to 120 characters"),
    (FormCard("field", "string", min="9", max="9"), "String · exactly 9 characters"),
    (FormCard("field", "integer", min="1", max="6", step="1"), "Integer · 1 to 6, step 1"),
    (FormCard("field", "decimal", step="0.5"), "Decimal · step 0.5"),
    (FormCard("field", "list", options=" A, ,B "), "List · choose one · A, B"),
    (FormCard("field", "list", exclusive=False), "List · choose any · no options yet"),
    (FormCard("field", "photo", ratio_w="1", ratio_h="1"), "Photo · 1:1, kept 600 × 600"),
    (FormCard("field", "photo", ratio_w="16", ratio_h="9"), "Photo · 16:9, kept 600 × 338"),
    (FormCard("field", "photo", ratio_w="0", ratio_h="5"), "Photo · ratio not set"),
    (FormCard("field", "photo", ratio_w="16", ratio_h="7"), "Photo · 16:7, kept 600 × 263"),
    (FormCard("field", "photo", ratio_w="\uff14", ratio_h="5"), "Photo · ratio not set"),
    (FormCard("field", "string", min="3"), "String · at least 3 characters"),
    (
        FormCard("field", "decimal", min="0.00", max="5.00", step="0.01"),
        "Decimal · 0.00 to 5.00, step 0.01",
    ),
    (FormCard("field", "text"), "Title and Description · display only"),
]


@pytest.mark.parametrize(("card", "summary"), SUMMARY_CASES)
def test_a_card_s_summary(card: FormCard, summary: str) -> None:
    assert card_summary(card) == summary


def test_a_photo_is_kept_600_px_on_its_longer_side() -> None:
    assert kept_size("4", "5") == (480, 600)
    assert kept_size("3", "2") == (600, 400)
    assert kept_size("x", "5") is None
    # Half up, as the page's Math.round, and ASCII digits only.
    assert kept_size("16", "3") == (600, 113)
    assert kept_size("\uff14", "5") is None
