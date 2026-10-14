"""The Overview card's rows hold every account category once, plus the
super-admins (guide/archive/admin_pages_refine.md Item 3): a category
added to the toolbar can't silently fall off the card."""

from __future__ import annotations

from app.web.views import _accounts


def test_the_rows_cover_every_category_once() -> None:
    keys = [key for row in _accounts._OVERVIEW_ROWS for key in row]
    categories = [key for key, _, _ in _accounts.ACCOUNT_CATEGORIES]
    assert sorted(keys) == sorted([*categories, "super_admins"])
    assert len(keys) == len(set(keys))


def test_a_pill_counts_as_its_chip_does() -> None:
    counts = {"operators": 3, "admins": 1, "no_role": 2, "unused": 4}
    rows = _accounts.build_account_overview_rows(counts, super_admins=1)
    assert [[(p.count, p.label) for p in row] for row in rows] == [
        [(3, "Operators"), (1, "Admins"), (1, "super-admin")],
        [(2, "No role"), (4, "Unused")],
    ]
