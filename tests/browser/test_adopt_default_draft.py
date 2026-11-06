"""14C Item 3: the composer's default as a draft to adopt.

In an empty subject or body, Right arrow fills the box with its default
(the placeholder) as ordinary text, caret at the start, and the form
reads unsaved, in each of the three templates. A box with text, a
modified arrow, or a field with no default (Cc) is left alone.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from .conftest import app_url


def _composer(page: Page, session_id: str, template: str = "invitation") -> None:
    page.goto(app_url(f"/operator/sessions/{session_id}/setup-invite?template={template}"))


@pytest.mark.parametrize("template", ["invitation", "reminder", "responses_received"])
def test_right_arrow_adopts_the_default_in_subject_and_body(
    page: Page, new_session: Callable[[], str], template: str
) -> None:
    _composer(page, new_session(), template)
    save = page.locator("#setupinvite-save-button")
    expect(save).to_be_disabled()
    for field_id in ("#field-subject", "#field-body"):
        field = page.locator(field_id)
        default = field.get_attribute("placeholder")
        assert default
        expect(field).to_have_value("")
        field.focus()
        field.press("ArrowRight")
        expect(field).to_have_value(default)
        assert field.evaluate("el => el.selectionStart") == 0
    expect(save).to_be_enabled()


def test_nothing_is_adopted_where_there_is_text_or_no_default(
    page: Page, new_session: Callable[[], str]
) -> None:
    _composer(page, new_session())
    subject = page.locator("#field-subject")
    subject.fill("Mine")
    subject.press("Home")
    subject.press("ArrowRight")
    expect(subject).to_have_value("Mine")

    body = page.locator("#field-body")
    body.focus()
    body.press("Shift+ArrowRight")
    expect(body).to_have_value("")

    cc = page.locator("#field-cc")
    cc.focus()
    cc.press("ArrowRight")
    expect(cc).to_have_value("")
