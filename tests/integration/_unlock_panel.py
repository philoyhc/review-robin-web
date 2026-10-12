"""Shared checks on the roster pages' Unlock panel (participant info Item 2).

Every roster page ends the panel's right column, while the panel is open,
with `Lock`: 20px under the column's last card, or at the column's foot
when it holds none (the column stretches to the row; base.html's
`.unlock-right > .roster-card-actions:first-child` rule). One helper so
the four pages assert it one way.
"""

from __future__ import annotations

import re


def div_block(html: str, marker: str) -> str:
    """The element opened by ``marker``, div-balanced.

    `.*?</div>` stops at the first close tag, which inside a column is a
    card's; balancing is the only boundary that does not move when the
    contents change.
    """
    start = html.index(marker)
    depth, i = 1, start + len(marker)
    for tag in re.finditer(r"<div\b|</div>", html[i:]):
        depth += 1 if tag.group(0) != "</div>" else -1
        if depth == 0:
            return html[start:i + tag.end()]
    raise AssertionError(f"{marker} never closes")


def panel_columns(html: str) -> tuple[str, str, str]:
    """The open panel, its left stack and its right stack."""
    m = re.search(r'<div\b[^>]*id="roster-unlock-panel"[^>]*>', html)
    assert m, "Unlock panel not found"
    panel = div_block(html, m.group(0))
    left = div_block(panel, '<div class="unlock-stack">')
    right = div_block(panel, '<div class="unlock-stack unlock-right">')
    return panel, left, right


def assert_lock_ends_right_column(html: str) -> None:
    """Open, the one `Lock` control is the right column's direct last
    child — not in the left column, not wrapped, and not a row of its own
    after the columns (that left a gap under a shorter right column)."""
    panel, left, right = panel_columns(html)
    assert html.count('id="roster-unlock-btn"') == 1, "two Lock controls"
    assert 'class="roster-card-actions"' not in left, (
        "Lock sits in the left column"
    )
    marker = '<div class="roster-card-actions">'
    assert marker in right, "Lock is not in the right column"
    tail = right[right.index(marker):]
    actions = div_block(tail, marker)
    rest = re.sub(r"<!--.*?-->", "", tail[len(actions):], flags=re.S)
    assert rest.strip() == "</div>", "Lock is not the right column's last child"
    after = panel[panel.index(right) + len(right):]
    assert re.sub(r"<!--.*?-->", "", after, flags=re.S).strip() == "</div>", (
        "something follows the right column inside the panel"
    )
