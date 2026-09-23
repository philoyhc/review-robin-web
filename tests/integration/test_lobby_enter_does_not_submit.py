"""Enter in a lobby expander field must not archive the session.

The row and bulk expanders are injected inside ``#sessions-list-form``.
Enter in a text field submits its form through the form's first submit
button, which was the row expander's **Purge and archive** (the bulk
expander's: **All tags to all**). So Enter in Name, Code, Deadline or
Tags archived the ticked session (found 2026-09-23 on the dev slot).

Two guards, each pinned here because a browser test cannot run in the
suite (both were driven in Chromium when written):

- a **disabled first submit button**, which makes the browser skip
  implicit submission for text fields, including the tag box, whose
  Enter must stay free to pick a typeahead suggestion;
- a **keydown guard on date-time inputs**, because Chromium's
  date-time field submits on Enter past a disabled first button.
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


def test_the_forms_first_submit_button_is_disabled(client: TestClient) -> None:
    form = _form(_lobby(client))
    first = re.search(r'<button type="submit"[^>]*>', form)

    assert first is not None
    assert "disabled" in first.group(0), (
        "a live first submit button is what Enter in an expander field "
        "fires — it was Purge and archive"
    )
    assert "data-no-implicit-submit" in first.group(0)


def test_the_expanders_sit_after_it_in_the_same_form(client: TestClient) -> None:
    """The guard only works if the expanders are injected inside this
    form, after the disabled button — the premise of the fix."""
    body = _lobby(client)

    assert body.index("data-no-implicit-submit") < body.index(
        'formaction="/operator/sessions/bulk-archive"'
    )
    assert "sessions-list-select-row" in _form(body)


def test_date_time_inputs_have_an_enter_guard(client: TestClient) -> None:
    form = _form(_lobby(client))

    assert 'getElementById("sessions-list-form")' in form
    assert 'event.key === "Enter"' in form
    assert "input[type=\"datetime-local\"]" in form
    assert "event.preventDefault()" in form
