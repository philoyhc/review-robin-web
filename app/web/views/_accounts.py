"""Sys Admin → Accounts: the Workspace users toolbar
(``guide/admin_pages_refine.md`` Item 1).

The view's state lives in the URL: which category chips are on
(``show``), the Session role (``role``), the search (``q``) and the page
start (``offset``). This module parses it, re-encodes it for the pager
and the action redirects, and shapes the chips. The category rule itself
is SQL, in ``app.services.account_listing``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from urllib.parse import parse_qs, urlencode

from app.services.account_listing import CATEGORIES, SESSION_ROLES

__all__ = [
    "ACCOUNT_CATEGORIES",
    "ACCOUNT_ROLE_OPTIONS",
    "AccountChip",
    "AccountOverviewPill",
    "AccountView",
    "account_refusal_message",
    "account_view_from_query",
    "account_view_query",
    "build_account_chips",
    "build_account_overview_pills",
    "parse_account_view",
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

_DEFAULT_SHOW = tuple(key for key, _, on in ACCOUNT_CATEGORIES if on)
_SEARCH_MAX = 200


@dataclass(frozen=True)
class AccountView:
    """What the table shows. ``show`` keeps toolbar order."""

    show: tuple[str, ...] = _DEFAULT_SHOW
    role: str = "any"
    search: str = ""
    offset: int = 0

    @property
    def is_filtered(self) -> bool:
        """A role or a search narrows the chips' rows; chips alone don't."""
        return self.role != "any" or bool(self.search)

    def with_category(self, key: str) -> AccountView:
        if key in self.show:
            return self
        return replace(
            self, show=tuple(k for k in CATEGORIES if k in self.show or k == key)
        )


def parse_account_view(
    *,
    show: Sequence[str] | None,
    role: str | None,
    search: str | None,
    offset: int | None,
) -> AccountView:
    """The view from query values, tolerantly: unknown chips and roles are
    dropped, the search trimmed and capped, a negative offset zeroed.

    ``show`` absent means the default chips; present but holding only
    blanks means none. The filter form always posts one blank ``show``
    so that turning every chip off survives the round trip.
    """
    if show is None:
        chips = _DEFAULT_SHOW
    else:
        wanted = {value for value in show if value}
        chips = tuple(key for key in CATEGORIES if key in wanted)
    return AccountView(
        show=chips,
        role=role if role in SESSION_ROLES else "any",
        search=(search or "").strip()[:_SEARCH_MAX],
        offset=max(offset or 0, 0),
    )


def account_view_query(view: AccountView, *, offset: bool = True) -> str:
    """The view as a query string, ``show=`` always present so an empty
    chip set stays empty. ``offset=False`` leaves the offset off, for the
    pager to append its own."""
    pairs: list[tuple[str, str]] = [("show", key) for key in view.show] or [
        ("show", "")
    ]
    if view.role != "any":
        pairs.append(("role", view.role))
    if view.search:
        pairs.append(("q", view.search))
    if offset and view.offset:
        pairs.append(("offset", str(view.offset)))
    return urlencode(pairs)


def account_view_from_query(query: str) -> AccountView:
    """Parse ``account_view_query``'s output back, for the actions'
    hidden ``view`` field."""
    values = parse_qs(query, keep_blank_values=True)
    try:
        offset = int((values.get("offset") or ["0"])[0])
    except ValueError:  # "abc", "²" and a 5,000-digit string alike
        offset = 0
    return parse_account_view(
        show=values.get("show"),
        role=(values.get("role") or [None])[0],
        search=(values.get("q") or [None])[0],
        offset=offset,
    )


@dataclass(frozen=True)
class AccountChip:
    key: str
    label: str
    count: int
    selected: bool


def build_account_chips(
    counts: Mapping[str, int], view: AccountView
) -> list[AccountChip]:
    """One chip per category, counted over the whole table."""
    return [
        AccountChip(
            key=key, label=label, count=counts.get(key, 0), selected=key in view.show
        )
        for key, label, _ in ACCOUNT_CATEGORIES
    ]


@dataclass(frozen=True)
class AccountOverviewPill:
    """One count on the Overview card, its label inside the pill."""

    key: str
    count: int
    label: str


#: Singular labels for a count of one (author, 2026-10-14); a key missing
#: here reads the same either way ("1 No role", "1 Unused").
_OVERVIEW_SINGULAR: dict[str, str] = {
    "operators": "Operator",
    "admins": "Admin",
    "super_admins": "super-admin",
}


#: The Overview card's pills, in order, on one line (author,
#: 2026-10-14): the kinds with a role and the super-admins among them,
#: then the kinds without.
_OVERVIEW_ORDER: tuple[str, ...] = (
    "operators", "admins", "super_admins", "no_role", "unused",
)


def build_account_overview_pills(
    counts: Mapping[str, int], *, super_admins: int
) -> list[AccountOverviewPill]:
    """The chips' own counts by kind, plus the super-admins, each label
    singular for a count of one."""
    plurals = {key: (counts.get(key, 0), label) for key, label, _ in ACCOUNT_CATEGORIES}
    plurals["super_admins"] = (super_admins, "super-admins")

    def pill(key: str) -> AccountOverviewPill:
        count, label = plurals[key]
        if count == 1:
            label = _OVERVIEW_SINGULAR.get(key, label)
        return AccountOverviewPill(key=key, count=count, label=label)

    return [pill(key) for key in _OVERVIEW_ORDER]


#: Why a batch was refused, by ``UserOperationError.code``: the reason
#: the page names beside the row (admin_pages_refine Item 2). Written
#: here rather than carried in the URL, and an unknown code gets a fixed
#: sentence rather than its own text, so a link can't put other words on
#: the page.
_REFUSAL_REASONS: dict[str, str] = {
    "still_owner": "{email} still owns sessions; remove them from all sessions first",
    "not_operator": "{email} has no role; admit them before promoting",
    "protected_super_admin": "{email} is a protected super-admin, set only in config",
    "owns_sessions": "{email} owns sessions",
    "has_history": (
        "{email} has created a session or acted in the audit log; only "
        "accounts with no activity can be deleted"
    ),
    "last_admin": "that would leave the workspace with no sys-admin",
    "sole_owner": "a session {email} owns would be left with no owner",
}


def account_refusal_message(code: str, email: str | None) -> str:
    """The banner for a refused action: nothing changed, and why, naming
    the row when there is one. Never the code itself, which came from the
    URL."""
    reason = _REFUSAL_REASONS.get(code)
    if reason is None or ("{email}" in reason and not email):
        return "Couldn't apply that change."
    return f"Nothing changed: {reason.format(email=email)}."
