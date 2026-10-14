"""The Overview card's line holds every account category once, plus the
super-admins (guide/archive/admin_pages_refine.md Item 3): a category
added to the toolbar can't silently fall off the card."""

from __future__ import annotations

from app.web.views import _accounts


def test_the_line_covers_every_category_once() -> None:
    keys = list(_accounts._OVERVIEW_ORDER)
    categories = [key for key, _, _ in _accounts.ACCOUNT_CATEGORIES]
    assert sorted(keys) == sorted([*categories, "super_admins"])
    assert len(keys) == len(set(keys))


def test_a_pill_counts_as_its_chip_does() -> None:
    counts = {"operators": 3, "admins": 2, "no_role": 5, "unused": 4}
    pills = _accounts.build_account_overview_pills(counts, super_admins=0)
    assert [(p.count, p.label) for p in pills] == [
        (3, "Operators"), (2, "Admins"), (0, "super-admins"),
        (5, "No role"), (4, "Unused"),
    ]


def test_a_count_of_one_reads_singular() -> None:
    counts = {"operators": 1, "admins": 1, "no_role": 1, "unused": 1}
    pills = _accounts.build_account_overview_pills(counts, super_admins=1)
    assert [p.label for p in pills] == [
        "Operator", "Admin", "super-admin", "No role", "Unused",
    ]
