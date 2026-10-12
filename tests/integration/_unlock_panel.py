"""Shared checks on the roster pages' Unlock panel (participant info Item 2).

Every roster page puts `Lock`, while the panel is open, at the panel's
foot: its last child, after both column stacks, so it sits at the bottom
right of the whole card (`.unlock-panel > .roster-card-actions` spans the
grid's columns). One helper so the four pages assert it one way.
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


def assert_lock_at_panel_foot(html: str) -> None:
    """Open, the one `Lock` control is the panel's own child, after both
    columns — not inside either stack."""
    panel, left, right = panel_columns(html)
    assert html.count('id="roster-unlock-btn"') == 1, "two Lock controls"
    assert 'class="roster-card-actions"' not in left + right, (
        "Lock sits inside a column rather than at the panel's foot"
    )
    after_right = panel.index(right) + len(right)
    assert panel.index('class="roster-card-actions"') > after_right, (
        "Lock is not after both columns"
    )
