"""The Delete-confirm pairing: delegated, capture-bound, and still
carrying its load-time pass.

`data-delete-confirm="{key}"` enables its paired `data-delete-btn="{key}"`
only while ticked. Nine templates use it.

Three properties, each load-bearing for a different reason:

1. **Delegated**, so a pair injected after load works with no
   registration. 19P.1 rung 2b builds a confirm and a Delete inside the
   row expander in JS; a listener bound at load could never reach them.
2. **Capture-bound**, because four roster pages re-run the gate by hand
   with `dispatchEvent(new Event("change"))` and `new Event` does not
   bubble. A bubble-phase delegated listener misses those entirely: the
   tick clears while `Delete` stays enabled — a destructive control
   whose disabled state lies. Reproduced in Chromium before the fix.
3. **The load-time pass**, because it sets each button's starting
   state. `reviewer/results.html`'s Acknowledge ships without
   `disabled` and is closed only by that pass; it also re-syncs a
   checkbox the browser restored on reload or bfcache, which no
   dispatch accompanies.

The suite has no JS runtime, so these cannot observe behavior — they
pin the SOURCE-LEVEL contract, and the previous version of this file
was three assertions that a regression sailed straight through. What
makes the difference is `test_every_programmatic_dispatch_is_reachable`,
which is a cross-file check rather than a substring: it is the one that
would have caught it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app/web/templates"
BASE = TEMPLATES / "base.html"


@pytest.fixture(scope="module")
def pairing() -> str:
    """The pairing IIFE, located by what it does rather than by layout.

    Anchoring on `<script>\\s*\\(function \\(\\) \\{` pinned source
    formatting: a reformat of `base.html` would have reported the
    script "gone".
    """
    source = BASE.read_text(encoding="utf-8")
    blocks = [
        m.group(1)
        for m in re.finditer(r"<script>(.*?)</script>", source, re.S)
        if "data-delete-btn" in m.group(1)
    ]
    assert len(blocks) == 1, (
        f"expected one script to own the pairing, found {len(blocks)}"
    )
    return blocks[0]


def _without_comments(source: str) -> str:
    """Block, line and Jinja comments removed.

    Not optional: `base.html`'s own comment quotes
    `deleteConfirm.dispatchEvent(new Event("change"))` to explain why
    the capture binding exists, and a scan that reads comments counts
    that prose as a fifth caller. Same trap as a CSS rule-scanner that
    matches inside the comment describing it.
    """
    source = re.sub(r"\{#.*?#\}", "", source, flags=re.S)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", source)


def test_responding_to_a_tick_is_delegated(pairing: str) -> None:
    handler = re.search(
        r'document\.addEventListener\(\s*"change",(.*?)\}\s*,?\s*(true)?\s*\);',
        pairing,
        re.S,
    )
    assert handler, "the pairing is not delegated on `document`"
    # ...and the handler must actually DO something. An empty-bodied
    # listener passed the previous version of this test.
    assert "sync(cb)" in handler.group(1), (
        "the delegated listener never calls `sync`, so a tick changes "
        "nothing"
    )


def test_the_delegated_listener_is_capture_bound(pairing: str) -> None:
    """Bubble-phase delegation misses every non-bubbling dispatch."""
    assert re.search(
        r'document\.addEventListener\(\s*"change",.*?\}\s*,\s*true\s*\);',
        pairing,
        re.S,
    ), (
        "the pairing listens in the bubble phase, so the four roster "
        "pages' non-bubbling `new Event(\"change\")` never reaches it "
        "and `Delete` stays enabled after the tick is cleared"
    )


def test_every_programmatic_dispatch_is_reachable(pairing: str) -> None:
    """The cross-file contract, and the check that would have caught it.

    Every template that re-runs this gate by hand must either dispatch
    a bubbling event or rely on the capture binding. Enumerated from
    the templates, not asserted about one file.
    """
    capture_bound = bool(re.search(
        r'document\.addEventListener\(\s*"change",.*?\}\s*,\s*true\s*\);',
        pairing,
        re.S,
    ))
    dispatches = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        markup = _without_comments(
            path.read_text(encoding="utf-8", errors="replace")
        )
        for m in re.finditer(
            r'(\w+)\.dispatchEvent\(\s*new Event\(\s*"change"([^)]*)\)', markup
        ):
            var, opts = m.group(1), m.group(2)
            # Only the ones aimed at a confirm checkbox matter here.
            if "confirm" not in var.lower():
                continue
            dispatches.append(
                (path.name, var, "bubbles" in opts)
            )

    # Three, not four: Reviewers gave its `Operator actions` selection
    # script up at 19P.1 rung 2b, and the expander rebuilds the panel
    # wholesale on every selection change rather than re-running a
    # gate on a surviving one. The floor moves with the fact; it is
    # here so that the enumeration cannot pass by finding nothing.
    assert len(dispatches) >= 3, (
        f"vacuity: found only {dispatches}; the unmigrated roster pages "
        "each re-run this gate and should be here"
    )
    unreachable = [d for d in dispatches if not d[2] and not capture_bound]
    assert not unreachable, (
        "these dispatch a non-bubbling `change` at a confirm checkbox "
        "while the pairing is bubble-bound, so the gate silently does "
        f"not re-run: {unreachable}"
    )


def test_the_load_time_pass_survives(pairing: str) -> None:
    """Not redundant with the delegation: it sets initial state."""
    assert re.search(
        r'forEach\.call\(\s*\n?\s*document\.querySelectorAll\('
        r'"\[data-delete-confirm\]"\)\s*,\s*sync\s*\)',
        pairing,
    ), (
        "the initial pass is gone or no longer calls `sync`; a paired "
        "button that does not ship `disabled` would render enabled"
    )


def _paired_buttons() -> list[tuple[str, str]]:
    out = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        if path.name == "base.html":
            continue
        markup = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"<button[^>]*data-delete-btn=[^>]*>", markup):
            out.append((path.name, m.group(0)))
    return out


def _ships_disabled(tag: str) -> bool:
    """`"disabled" in tag` is wrong: it matches `aria-disabled` too."""
    return re.search(r"(?<![-\w])disabled(?=[\s=>])", tag) is not None


def test_the_one_button_that_depends_on_the_load_pass_still_does() -> None:
    """Vacuity guard for the test above. If every paired button shipped
    `disabled`, dropping the load pass would be nearly harmless and
    that test would guard much less."""
    acks = [
        (name, tag) for name, tag in _paired_buttons()
        if 'data-delete-btn="ack-results"' in tag
    ]
    assert len(acks) == 1, f"expected one Acknowledge button, got {acks}"
    assert not _ships_disabled(acks[0][1]), (
        "Acknowledge now ships `disabled`; if every pair does, say so in "
        "`base.html` and this test can go"
    )


def test_every_other_paired_button_ships_disabled() -> None:
    """The rule an injected pair has to follow, stated as a test.

    Nothing syncs an injected pair until its first tick, so its button
    must ship `disabled` or it renders live.
    """
    buttons = _paired_buttons()
    assert len(buttons) >= 19, f"vacuity: only found {len(buttons)}"
    offenders = [
        f"{name}: {tag[:70]}" for name, tag in buttons
        if not _ships_disabled(tag)
        and 'data-delete-btn="ack-results"' not in tag
    ]
    assert not offenders, offenders
