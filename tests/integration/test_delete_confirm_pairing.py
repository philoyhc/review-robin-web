"""The Delete-confirm pairing is delegated, and keeps its load-time pass.

`data-delete-confirm="{key}"` enables its paired `data-delete-btn="{key}"`
only while ticked. Nine templates use it.

Two properties, and they are not the same property:

1. **Delegated**, so a pair injected after load works with no
   registration. 19P.1 rung 2b builds a confirm and a Delete inside the
   row expander in JS; a listener bound at load could never reach them
   and that Delete would ship `disabled` and stay so forever.
2. **The load-time pass stays**, because it sets each button's starting
   state. Most ship `disabled` in markup — `reviewer/results.html`'s
   Acknowledge does not, and is disabled only by that pass. It gates a
   reviewer confirming they have read their results, so dropping the
   pass would ship that gate open.

The suite has no JS runtime, so these pin the MECHANISM. The behaviour
was verified in Chromium against the real rendered page: static pair
ticks and unticks correctly, an injected pair ticks and unticks
correctly, and a button with no `disabled` in markup is disabled on
load.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app/web/templates"
BASE = TEMPLATES / "base.html"


@pytest.fixture(scope="module")
def script() -> str:
    css = BASE.read_text(encoding="utf-8")
    m = re.search(
        r"<script>\s*\(function \(\) \{\s*function sync\(cb\)(.*?)</script>",
        css,
        re.S,
    )
    assert m, "the delete-confirm pairing script is gone"
    return m.group(1)


def test_responding_to_a_tick_is_delegated(script: str) -> None:
    """Bound on `document`, so a pair that did not exist at load works."""
    assert re.search(
        r'document\.addEventListener\(\s*"change"', script
    ), (
        "the pairing binds per element again, so a confirm injected "
        "after load — the row expander's — is never wired"
    )
    assert 'hasAttribute("data-delete-confirm")' in script, (
        "the delegated listener does not filter on the pairing attribute"
    )


def test_the_load_time_pass_survives(script: str) -> None:
    """It is not redundant with the delegation: it sets initial state."""
    assert re.search(
        r'querySelectorAll\("\[data-delete-confirm\]"\)', script
    ), (
        "the initial pass is gone; a paired button that does not ship "
        "`disabled` in markup would render enabled"
    )


def test_the_one_button_that_depends_on_the_load_pass_still_does() -> None:
    """Vacuity guard for the test above, and a real invariant.

    If every paired button shipped `disabled`, dropping the load pass
    would be harmless and the test above would be guarding nothing. It
    is guarding this file.
    """
    results = (TEMPLATES / "reviewer/results.html").read_text(encoding="utf-8")
    m = re.search(r'<button[^>]*data-delete-btn="ack-results"[^>]*>', results)
    assert m, "the Acknowledge button is gone or was renamed"
    assert "disabled" not in m.group(0), (
        "Acknowledge now ships `disabled`; if every pair does, say so in "
        "`base.html` and this test can go"
    )


def test_every_other_paired_button_ships_disabled() -> None:
    """The rule an injected pair has to follow, stated as a test.

    Nothing syncs an injected pair until its first tick, so its button
    must ship `disabled` or it renders live. Acknowledge is the one
    documented exception and it is not injected.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        if path.name == "base.html":
            continue
        markup = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"<button[^>]*data-delete-btn=[^>]*>", markup):
            if "disabled" not in m.group(0):
                offenders.append(f"{path.name}: {m.group(0)[:70]}")
    assert offenders == [
        'results.html: <button type="submit" class="btn" '
        'data-delete-btn="ack-results">'
    ], offenders
