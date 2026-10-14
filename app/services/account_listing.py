"""Sys Admin → Accounts: one page of the Workspace users table, filtered
in SQL (``guide/admin_pages_refine.md`` Item 1).

Every sign-in creates a ``users`` row, so the table must hold a review's
worth of participants (1,000 and up). It replaced
``users.list_workspace_users``, which read every row into Python: this
module filters, counts and pages in the database, and computes the
per-row session counts for the page only.

**The category rule** partitions the table, so every row is under
exactly one chip:

- ``admins``: ``is_sys_admin``, or a super-admin email. Admins win: an
  admin has operator access whatever its Operator flag says.
- ``operators``: ``is_operator`` and not an admin.
- ``no_role``: neither, with history: created a session, owns one, or
  acted in the audit log. Each refuses Delete (``spec/permissions.md``
  §4.1), owning as ``owns_sessions`` and the other two as
  ``has_history``.
- ``unused``: neither, no history.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.auth.roles import effective_super_admin_emails, is_super_admin
from app.db.models import (
    AuditEvent,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.services.email_identity import normalize_email
from app.services.users import WorkspaceUserRow

__all__ = [
    "CATEGORIES",
    "SESSION_ROLES",
    "AccountsPage",
    "category_of",
    "list_accounts_page",
    "search_options",
]


#: Category keys, in toolbar order.
CATEGORIES: tuple[str, ...] = ("operators", "admins", "no_role", "unused")

#: Session role keys the dropdown filters by; ``any`` is no filter.
SESSION_ROLES: tuple[str, ...] = ("reviewer", "reviewee", "observer", "owner")


@dataclass(frozen=True)
class AccountsPage:
    """One page of the table and what the toolbar needs around it.

    ``total`` counts every row the filters match, across all pages.
    ``counts`` is per category over the whole table, ignoring the role
    and the search, so a chip says what turning it on would add.
    ``offset`` is the clamped start of this page.
    """

    rows: list[WorkspaceUserRow]
    total: int
    counts: dict[str, int]
    offset: int


def _is_admin() -> ColumnElement[bool]:
    supers = [normalize_email(email) for email in effective_super_admin_emails()]
    return or_(User.is_sys_admin.is_(True), func.lower(User.email).in_(supers))


def _has_history() -> ColumnElement[bool]:
    # Owning a session counts, as the author ruled (Item 1): a co-owner
    # who never acted is not unused, and Delete refuses them anyway.
    return or_(
        exists().where(ReviewSession.created_by_user_id == User.id),
        exists().where(SessionOperator.user_id == User.id),
        exists().where(AuditEvent.actor_user_id == User.id),
    )


def _category() -> ColumnElement[str]:
    return case(
        (_is_admin(), "admins"),
        (User.is_operator.is_(True), "operators"),
        (_has_history(), "no_role"),
        else_="unused",
    )


def _role_filter(role: str) -> ColumnElement[bool]:
    """Accounts whose email appears in that role in any session, live or
    archived, case-insensitively; ``owner`` is a ``session_operators``
    row."""
    # not-identity: a display filter on Accounts that gates nothing,
    # comparing two stored columns with the same SQL ``lower`` on both
    # sides; no Python value is folded, so ``normalize_email`` has no
    # side to stand on.
    email = func.lower(User.email)
    if role == "reviewer":
        return exists().where(func.lower(Reviewer.email) == email)
    if role == "reviewee":
        return exists().where(func.lower(Reviewee.email_or_identifier) == email)
    if role == "observer":
        return exists().where(func.lower(Observer.email) == email)
    if role == "owner":
        return exists().where(SessionOperator.user_id == User.id)
    raise ValueError(f"unknown session role {role!r}")


def _search_filter(search: str) -> ColumnElement[bool]:
    needle = search.lower()
    return or_(
        func.lower(User.email).contains(needle, autoescape=True),
        func.lower(func.coalesce(User.display_name, "")).contains(
            needle, autoescape=True
        ),
    )


def _filters(
    categories: Collection[str], role: str | None, search: str
) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = [_category().in_(list(categories))]
    if role:
        clauses.append(_role_filter(role))
    if search:
        clauses.append(_search_filter(search))
    return clauses


def category_of(db: Session, user_id: int) -> str | None:
    """The chip one account sits under, or ``None`` if it doesn't exist."""
    return db.execute(
        select(_category()).where(User.id == user_id)
    ).scalar_one_or_none()


def _offset_of(
    db: Session, user_id: int, clauses: list[ColumnElement[bool]], page_size: int
) -> int | None:
    """The page start that holds ``user_id`` under these filters, or
    ``None`` when the filters hide it. Rows run newest first."""
    if db.execute(
        select(User.id).where(User.id == user_id, *clauses)
    ).first() is None:
        return None
    ahead = db.execute(
        select(func.count(User.id)).where(User.id > user_id, *clauses)
    ).scalar_one()
    return (ahead // page_size) * page_size


def list_accounts_page(
    db: Session,
    *,
    categories: Collection[str],
    role: str | None = None,
    search: str = "",
    offset: int = 0,
    page_size: int = 200,
    selected_user_id: int | None = None,
) -> AccountsPage:
    """The rows under ``categories`` matching ``role`` and ``search``,
    newest first, one page from ``offset``.

    ``offset`` is clamped onto a page boundary, never rejected. With
    ``selected_user_id`` on a row the filters match, the page is the one
    holding that row, so an action's redirect lands where the row is.
    """
    clauses = _filters(categories, role, search)
    total = db.execute(
        select(func.count(User.id)).where(*clauses)
    ).scalar_one()

    if selected_user_id is not None:
        found = _offset_of(db, selected_user_id, clauses, page_size)
        if found is not None:
            offset = found
    last_start = ((total - 1) // page_size) * page_size if total else 0
    offset = min(max(offset, 0), last_start)
    offset = (offset // page_size) * page_size

    history = _has_history().label("has_history")
    row_category = _category().label("row_category")
    page = db.execute(
        select(User, history, row_category)
        .where(*clauses)
        .order_by(User.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    category = _category().label("category")
    counts = {key: 0 for key in CATEGORIES}
    for key, count in db.execute(
        select(category, func.count(User.id)).group_by(category)
    ):
        counts[key] = count

    session_total, user_sole = _session_counts(db, [user.id for user, _, _ in page])
    rows = [
        WorkspaceUserRow(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_operator=user.is_operator,
            is_sys_admin=user.is_sys_admin,
            is_super_admin=is_super_admin(user.email),
            created_at=user.created_at,
            session_operator_count=session_total.get(user.id, 0),
            sole_owner_count=user_sole.get(user.id, 0),
            has_history=bool(has_history),
            category=row_category,
        )
        for user, has_history, row_category in page
    ]
    return AccountsPage(rows=rows, total=total, counts=counts, offset=offset)


def _session_counts(
    db: Session, user_ids: list[int]
) -> tuple[dict[int, int], dict[int, int]]:
    """Per user on the page: sessions they own, and how many of those
    they own alone."""
    if not user_ids:
        return {}, {}
    memberships = list(
        db.execute(
            select(SessionOperator.session_id, SessionOperator.user_id).where(
                SessionOperator.user_id.in_(user_ids)
            )
        )
    )
    session_ids = {session_id for session_id, _ in memberships}
    owners_per_session = dict(
        db.execute(
            select(SessionOperator.session_id, func.count(SessionOperator.id))
            .where(SessionOperator.session_id.in_(session_ids))
            .group_by(SessionOperator.session_id)
        ).all()
    ) if session_ids else {}
    total: dict[int, int] = defaultdict(int)
    sole: dict[int, int] = defaultdict(int)
    for session_id, user_id in memberships:
        total[user_id] += 1
        if owners_per_session.get(session_id) == 1:
            sole[user_id] += 1
    return total, sole


def search_options(
    db: Session,
    *,
    categories: Collection[str],
    search: str = "",
    cap: int = 200,
) -> list[str]:
    """The search box's typeahead: emails and names of the accounts
    under ``categories`` that contain ``search``, sorted, the first
    ``cap`` shown. The page asks again as the operator types, so the cap
    limits what one list shows, never which accounts can be suggested:
    typing more narrows the list to the account wanted."""
    clauses = _filters(categories, None, search)
    emails = db.execute(
        select(User.email).where(*clauses).order_by(User.email).limit(cap)
    ).scalars()
    names = db.execute(
        select(User.display_name)
        .where(*clauses, User.display_name.is_not(None), User.display_name != "")
        .distinct()
        .order_by(User.display_name)
        .limit(cap)
    ).scalars()
    return sorted(set(emails) | set(names), key=str.casefold)[:cap]
