"""Roster addresses resolved through the directory (segment 21F).

An address on a roster row is looked up through the host's Graph helper
(`cordware.graph.look_up_all`, the Email Address Checker's lookup) on the
uploading operator's delegated token. A row whose address resolves to
exactly one account (`OK`, `USE_PRIMARY`, `FOUND_NO_PRIMARY`) stores that
account's object ID, mail and UPN beside the address as written; any other
outcome stores none of them, and the row keeps matching by mail. One
exception: on a replace, an address the directory gave no answer for (no
token, an expired one, a failed or unfinished lookup) keeps the account
the replaced row had (`unchecked`; `app.services.csv_imports._save`, in `_saving.py`).

Nothing here talks to a request: the routes hand in a `Directory` (or
``None`` when there is none to ask, which checks nothing).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from cordware.graph import RESOLVED, Directory, GraphError, Outcome, look_up_all

from app.services.email_identity import looks_like_email, normalize_email, normalize_object_id

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
    """The account an outcome binds to: one account, or none. Its object
    id is stored normalized (segment 20G), so matching compares plainly;
    an answer with no id binds nothing."""
    if outcome is None or outcome.status not in RESOLVED or outcome.user is None:
        return None
    user = outcome.user
    object_id = normalize_object_id(user.id)
    if not object_id:
        return None
    return Account(
        object_id=object_id, mail=user.mail, upn=user.user_principal_name,
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


#: The outcomes that are the directory's answer about an address: bound,
#: or found to be nobody or several. Anything else is *not checked*.
ANSWERED = RESOLVED | {"NOT_FOUND", "AMBIGUOUS"}


def unchecked(
    outcomes: Mapping[str, Outcome], addresses: Iterable[str | None], *, checked: bool
) -> frozenset[str]:
    """The lookup keys among ``addresses`` the directory gave no answer
    for: every one with ``checked`` false, else those whose outcome is
    missing or not in `ANSWERED` (an expired token, a failed or
    unfinished lookup). The keys `counts` tallies as *not checked*."""
    keys = {k for k in (key(a) for a in addresses) if k is not None}
    if not checked:
        return frozenset(keys)
    return frozenset(
        k for k in keys if (o := outcomes.get(k)) is None or o.status not in ANSWERED
    )


#: Why an address went unchecked when there was no delegated token to
#: ask with (`unchecked_reason`); the other reasons are Graph's own
#: failure kinds (`cordware.graph.GraphError.kind`).
NO_TOKEN = "no_token"

#: The one stop renewing the sign-in cures (segment 20G, author
#: 2026-11-03): Graph refusing an expired token. No token at all (the
#: token store off, or a sign-in that did not ask for Graph) and
#: ``forbidden`` (consent or scope) are not cured by renewing, so those
#: save as any other failure does, and the import says why.
RENEWABLE_KIND = "unauthorized"


def sign_in_stop(
    outcomes: Mapping[str, Outcome], addresses: Iterable[str | None], *, checked: bool
) -> str | None:
    """`RENEWABLE_KIND` when Graph refused the token for any of
    ``addresses`` (an expired token: `look_up_all` ends every lookup not
    yet started with it), else ``None`` (segment 20G). Only this stop
    holds an upload and asks to renew."""
    if not checked:
        return None
    keys = [k for k in (key(a) for a in addresses) if k is not None]
    for k in keys:
        outcome = outcomes.get(k)
        if outcome is not None and outcome.error_kind == RENEWABLE_KIND:
            return RENEWABLE_KIND
    return None


def unchecked_reason(
    outcomes: Mapping[str, Outcome], addresses: Iterable[str | None], *, checked: bool
) -> str | None:
    """Why any of ``addresses`` went unchecked, or ``None`` when every one
    was answered (segment 20G): `NO_TOKEN` when nothing could be asked,
    else the first unanswered outcome's failure kind (``forbidden``,
    ``throttled``, ``server``, ``timeout`` …), ``"timeout"`` for a lookup
    with no outcome. The import records it, and the card's line names it."""
    keys = [k for k in (key(a) for a in addresses) if k is not None]
    if not keys:
        return None
    if not checked:
        return NO_TOKEN
    for k in keys:
        outcome = outcomes.get(k)
        if outcome is None:
            return "timeout"
        if outcome.status not in ANSWERED:
            return outcome.error_kind or "timeout"
    return None


def binding(row: object) -> dict[str, str | None] | None:
    """A saved row's directory columns, or ``None`` when it is unbound."""
    if not getattr(row, "directory_object_id", None):
        return None
    return {name: getattr(row, name, None) for name in UNBOUND}


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
