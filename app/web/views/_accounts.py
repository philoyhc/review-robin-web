"""Sys Admin → Accounts: the Workspace users toolbar
(``guide/admin_pages_refine.md`` Item 1).

Four category chips partition the table, and every row is under
exactly one of them. The partition is a display rule over flags the
service already returns, so it lives here rather than in
``app.services.users``.

Rung 1 is the scaffold: the chips carry real labels and counts but
filter nothing yet.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from app.services.users import WorkspaceUserRow

__all__ = [
    "ACCOUNT_CATEGORIES",
    "ACCOUNT_ROLE_OPTIONS",
    "AccountChip",
    "account_category",
    "build_account_chips",
]


#: ``(key, label, on by default)`` in toolbar order.
ACCOUNT_CATEGORIES: tuple[tuple[str, str, bool], ...] = (
    ("operators", "Operators", True),
    ("admins", "Admins", True),
    ("no_role", "No role", False),
    ("unused", "Unused", False),
)

#: The Session role dropdown: what an account does in sessions, which
#: the chips can't say. ``any`` is the unfiltered default.
ACCOUNT_ROLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("any", "Any"),
    ("reviewer", "Reviewer"),
    ("reviewee", "Reviewee"),
    ("observer", "Observer"),
    ("owner", "Owner"),
)


@dataclass(frozen=True)
class AccountChip:
    key: str
    label: str
    count: int
    selected: bool


def account_category(row: WorkspaceUserRow) -> str:
    """The one chip a row sits under.

    Admins win: an admin has operator access whatever its Operator flag
    says, so it is never also counted as an operator. A row with neither
    flag splits on history, which is what decides whether Delete is
    allowed (``spec/permissions.md`` §4.1).
    """
    if row.is_sys_admin or row.is_super_admin:
        return "admins"
    if row.is_operator:
        return "operators"
    return "no_role" if row.has_history else "unused"


def build_account_chips(rows: Iterable[WorkspaceUserRow]) -> list[AccountChip]:
    """One chip per category, counted over the whole table."""
    counts = Counter(account_category(row) for row in rows)
    return [
        AccountChip(key=key, label=label, count=counts[key], selected=default)
        for key, label, default in ACCOUNT_CATEGORIES
    ]
