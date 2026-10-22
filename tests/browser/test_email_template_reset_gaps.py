"""The two "Reset … to default" links sit the same distance below their
fields.

The body is a textarea, which is inline-block and left a descender's
space below it, so its reset link sat lower than the subject's (author,
2026-10-13). The editor's textarea is block now.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page

from .conftest import app_url


def _gap(page: Page, field: str) -> float:
    return page.evaluate(
        """(field) => {
            const box = document.getElementById('field-' + field);
            const reset = document.querySelector(
                'button[form="setupinvite-reset-' + field + '-form"]'
            );
            return reset.getBoundingClientRect().top
                - box.getBoundingClientRect().bottom;
        }""",
        field,
    )


def test_both_reset_links_sit_the_same_gap_below_their_field(
    page: Page, api: httpx.Client, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    response = api.post(
        f"/operator/sessions/{session_id}/setup-invite",
        data={
            "template": "invitation",
            "subject": "Peer review",
            "body": "Deadline = $deadline",
            "cc": "",
            "bcc": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    page.goto(app_url(f"/operator/sessions/{session_id}/setup-invite"))

    subject, body = _gap(page, "subject"), _gap(page, "body")
    # The row has no margin (author, 2026-10-13: closer is fine as long
    # as the two match); neither link overlaps its field.
    assert subject >= 0
    assert abs(subject - body) < 1, (subject, body)
