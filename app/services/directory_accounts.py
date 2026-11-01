"""Roster addresses resolved through the directory (segment 21F).

An address on a roster row is looked up through the host's Graph helper
(`cordware.graph.look_up_all`, the Email Address Checker's lookup) on the
uploading operator's delegated token. A row whose address resolves to
exactly one account (`OK`, `USE_PRIMARY`, `FOUND_NO_PRIMARY`) stores that
account's object ID, mail and UPN beside the address as written; any other
outcome stores none of them, and the row keeps matching by mail.

Nothing here talks to a request: the routes hand in a `Directory` (or
``None`` when there is none to ask, which checks nothing).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from cordware.graph import RESOLVED, Directory, GraphError, Outcome, look_up_all

from app.services.email_identity import looks_like_email, normalize_email

#: The import's time budget, in seconds: under App Service's front-end
#: limit, as the checker's plain post is. A lookup unfinished by then is
#: *not checked*, and its row keeps matching by mail.
BUDGET = 120.0


@dataclass(frozen=True)
class Account:
    """The directory account an address resolved to."""

    object_id: str
    mail: str | None
    upn: str
    #: The directory's display name; an invite stores it (19Z). Roster
    #: rows do not.
    name: str = ""


#: The columns a roster row stores, empty when its address did not bind.
UNBOUND = {"directory_object_id": None, "directory_mail": None, "directory_upn": None}


def key(address: str | None) -> str | None:
    """The lookup key for an address, or ``None`` for a blank or for a
    value that is not an address (an anonymous reviewee identifier)."""
    if not looks_like_email(address):
        return None
    return normalize_email(address)


def account_of(outcome: Outcome | None) -> Account | None:
    """The account an outcome binds to: one account, or none."""
    if outcome is None or outcome.status not in RESOLVED or outcome.user is None:
        return None
    user = outcome.user
    return Account(
        object_id=user.id, mail=user.mail, upn=user.user_principal_name,
        name=user.display_name,
    )


def columns(account: Account | None) -> dict[str, str | None]:
    """A row's directory columns for ``account``."""
    if account is None:
        return dict(UNBOUND)
    return {
        "directory_object_id": account.object_id,
        "directory_mail": account.mail,
        "directory_upn": account.upn,
    }


def resolve(
    directory: Directory | None, addresses: Iterable[str | None], *, budget: float = BUDGET
) -> dict[str, Outcome]:
    """Each distinct address looked up once. With no directory, nothing
    is checked and the answer is empty."""
    if directory is None:
        return {}
    keys = [k for k in (key(a) for a in addresses) if k is not None]
    return look_up_all(directory, keys, budget=budget)


def accounts(outcomes: Mapping[str, Outcome]) -> dict[str, Account]:
    """The keys that bound, with their accounts."""
    found = {k: account_of(o) for k, o in outcomes.items()}
    return {k: a for k, a in found.items() if a is not None}


def look_up_one(directory: Directory | None, address: str) -> Outcome | None:
    """One address's directory outcome, or ``None`` when nothing was
    asked: no directory, or a value that is not an address."""
    k = key(address)
    if k is None or directory is None:
        return None
    return look_up_all(directory, [k], budget=BUDGET).get(k)


#: The fewest characters a picker's search asks the directory with (19Z,
#: invite from the directory): fewer would match half the institution.
SEARCH_MIN = 3


@dataclass(frozen=True)
class Person:
    """One directory match as a picker offers it."""

    name: str
    mail: str | None
    upn: str

    @property
    def address(self) -> str:
        """What a pick fills an address box with: the mail, else the
        sign-in name (an account with no mail)."""
        return self.mail or self.upn


@dataclass(frozen=True)
class Search:
    """A picker's answer: the matches, or ``None`` with why not."""

    people: list[Person] | None
    reason: str | None = None


def search(directory: Directory | None, text: str) -> Search:
    """The directory's matches for what a picker's box holds; ``people``
    is ``None`` when the directory cannot be asked, and ``reason`` says
    why (`GraphError.reason`; ``no_token`` with no directory). Text
    shorter than `SEARCH_MIN` asks nothing and matches no one."""
    prefix = text.strip()
    if directory is None:
        return Search(None, "no_token")
    if len(prefix) < SEARCH_MIN:
        return Search([])
    try:
        users = directory.search_users(prefix)
    except GraphError as exc:
        return Search(None, exc.reason)
    return Search([Person(name=u.display_name, mail=u.mail, upn=u.user_principal_name) for u in users])


def resolver(directory: Directory | None) -> Callable[[str], Account | None]:
    """One address resolved on demand, for the single-row add and edit."""

    def resolve_one(address: str) -> Account | None:
        k = key(address)
        if k is None or directory is None:
            return None
        return account_of(look_up_all(directory, [k], budget=BUDGET).get(k))

    return resolve_one


def counts(
    outcomes: Mapping[str, Outcome], addresses: Iterable[str | None], *, checked: bool
) -> dict[str, int]:
    """What an import's directory check came to, over its distinct
    addresses (identifiers that are not addresses are left out). With
    ``checked`` false, every address is *not checked*."""
    keys = list(dict.fromkeys(k for k in (key(a) for a in addresses) if k is not None))
    tally = {
        "directory_by_mail": 0,
        "directory_by_upn": 0,
        "directory_not_found": 0,
        "directory_ambiguous": 0,
        "directory_not_checked": 0,
    }
    for k in keys:
        outcome = outcomes.get(k) if checked else None
        status = outcome.status if outcome is not None else "ERROR"
        if status == "OK":
            tally["directory_by_mail"] += 1
        elif status in ("USE_PRIMARY", "FOUND_NO_PRIMARY"):
            tally["directory_by_upn"] += 1
        elif status == "NOT_FOUND":
            tally["directory_not_found"] += 1
        elif status == "AMBIGUOUS":
            tally["directory_ambiguous"] += 1
        else:
            tally["directory_not_checked"] += 1
    return tally


def recipient(row: object) -> str:
    """Where a roster row's mail goes: the directory's mail for a row
    bound to an account with one (a row given by UPN, whose UPN may take
    no mail), else the address as written (author's ruling, 2026-10-31)."""
    mail = getattr(row, "directory_mail", None)
    if getattr(row, "directory_object_id", None) and mail:
        return mail
    return getattr(row, "email", None) or getattr(row, "email_or_identifier", "")


def rebind(
    row: object,
    *,
    old: str | None,
    new: str | None,
    resolve: Callable[[str], Account | None] | None,
) -> list[str | None] | None:
    """A roster row's address edited from ``old`` to ``new``: the same
    address (folded) keeps its binding; another resolves afresh, and
    without a lookup, or not found, the binding is cleared, never kept
    (segment 21F; Codex, #3424). Returns ``[old, new]`` object IDs for
    the audit's ``changes`` when the account the row admits moved."""
    if key(old) == key(new):
        return None
    before = getattr(row, "directory_object_id", None)
    account = resolve(new) if (resolve is not None and new) else None
    for name, value in columns(account).items():
        setattr(row, name, value)
    after = getattr(row, "directory_object_id", None)
    return None if before == after else [before, after]
