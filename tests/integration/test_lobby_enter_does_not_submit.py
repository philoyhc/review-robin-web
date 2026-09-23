"""Enter in a lobby expander field must not archive the session.

The row and bulk expanders are injected inside ``#sessions-list-form``.
Enter in a text field submits its form through the form's first submit
button, which was the row expander's **Purge and archive** (the bulk
expander's: **All tags to all**). So Enter in Name, Code, Deadline or
Tags — or on a ticked row, purge or "Yes, delete" checkbox — archived
the ticked session, with a ticked purge box irreversibly (found
2026-09-23 on the dev slot; the checkboxes by the fix's cold read).

Two guards, each pinned here because a browser test cannot run in the
suite (both were driven in Chromium on every field and checkbox):

- a **disabled first submit button**, which stops implicit submission
  from text fields. It is what protects the tag boxes, whose Enter must
  stay free to pick a typeahead suggestion;
- a **keydown guard on every other input** in the form, because
  Chromium lets checkboxes and date-time fields submit past a disabled
  first button, and Safari may skip a disabled default button entirely.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient


def _lobby(client: TestClient) -> str:
    response = client.post(
        "/operator/sessions",
        data={"name": "Enter", "code": "ENTER-1", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return client.get("/operator/sessions").text


def _form(body: str) -> str:
    start = body.index('id="sessions-list-form"')
    return body[start : body.index("</form>", start)]


#: Any submit button, however written: a ``<button>`` that is not
#: ``type="button"`` or ``"reset"`` (``submit`` is the default), or an
#: ``<input type="submit">``.
SUBMIT = re.compile(
    r'<button\b(?![^>]*type="(?:button|reset)")[^>]*>|<input[^>]*type="submit"[^>]*>'
)


def test_the_forms_first_submit_button_is_disabled(client: TestClient) -> None:
    form = _form(_lobby(client))
    first = SUBMIT.search(form)

    assert first is not None
    assert "disabled" in first.group(0), (
        "a live first submit button is what Enter in an expander field "
        "fires — it was Purge and archive"
    )
    assert "data-no-implicit-submit" in first.group(0)


def test_the_expanders_are_injected_into_this_form(client: TestClient) -> None:
    """The guards only reach the expanders because the script injects
    them into this form's table, after the disabled button, and the row
    checkboxes are the form's own."""
    body = _lobby(client)

    assert 'document.querySelector("#sessions-list-form table")' in body
    assert "sessions-list-select-row" in _form(body)


def test_every_input_but_the_tag_box_has_an_enter_guard(
    client: TestClient,
) -> None:
    """Checkboxes and date-time fields submit past a disabled first
    button in Chromium, so the guard covers every input — except the
    tag boxes, which the disabled button already covers and whose Enter
    picks a typeahead suggestion."""
    form = _form(_lobby(client))

    assert 'getElementById("sessions-list-form")' in form
    assert 'event.key === "Enter"' in form
    assert 'matches("input:not([data-tag-typeahead])")' in form
    assert "event.preventDefault()" in form
