"""The Overview card's two rows of counts by kind cover every category
once (guide/admin_pages_refine.md Item 3 rung 2a): a category added to
the toolbar can't silently fall off the card."""

from __future__ import annotations

from app.web.views import _accounts


def test_the_rows_cover_every_category_once() -> None:
    keys = [key for _, row in _accounts._OVERVIEW_ROWS for key in row]
    assert sorted(keys) == sorted(key for key, _, _ in _accounts.ACCOUNT_CATEGORIES)
    assert len(keys) == len(set(keys))
