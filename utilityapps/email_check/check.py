"""The check itself: each distinct address looked up once, each row
classified, accounts under more than one address grouped (spec §§5–7;
segment U1, rung 5). The CSV in and out is `csvio`'s; the directory is
the host's (`cordware.graph`).

A lookup that did not finish is `ERROR`, never `NOT_FOUND` (spec §6): the
directory could not be asked, which says nothing about the address.
"""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from cordware.graph import Directory, DirectoryUser, GraphError
from utilityapps.email_check import csvio

STATUSES = ("OK", "USE_PRIMARY", "FOUND_NO_PRIMARY", "NOT_FOUND", "AMBIGUOUS", "INVALID_INPUT", "ERROR")
#: Statuses whose row names one account, so it can join a duplicate group.
RESOLVED = frozenset({"OK", "USE_PRIMARY", "FOUND_NO_PRIMARY"})
#: Alias lookup is not built (spec phase 2), so every run says so.
COVERAGE = "BASIC_ONLY"
#: Lookups in flight at once: conservative, as spec §10 asks.
WORKERS = 4


@dataclass(frozen=True)
class Outcome:
    """What one address came to: a status, how it matched, and the account."""

    status: str
    match_type: str
    user: DirectoryUser | None = None
    note: str = ""
    #: For `ERROR`: the `GraphError` kind, which the log may carry.
    error_kind: str = ""


@dataclass(frozen=True)
class Result:
    csv: str
    counts: dict[str, int]
    groups: int
    rows: int
    lookups: int
    error_kinds: tuple[str, ...]


def classify(key: str, users: list[DirectoryUser]) -> Outcome:
    """One address against what the directory returned for it."""
    distinct = {u.id: u for u in users}
    if not distinct:
        return Outcome("NOT_FOUND", "NONE", note="No user-directory match")
    if len(distinct) > 1:
        return Outcome("AMBIGUOUS", "MULTIPLE", note=f"{len(distinct)} accounts match")
    (user,) = distinct.values()
    mail = (user.mail or "").lower()
    if mail and mail == key:
        return Outcome("OK", "PRIMARY_MAIL", user)
    if user.user_principal_name.lower() == key:
        if mail:
            return Outcome("USE_PRIMARY", "UPN", user)
        return Outcome("FOUND_NO_PRIMARY", "UPN", user, note="The account has no primary email")
    # The directory matched on neither field as this compares them: name
    # no winner rather than guess (spec §5).
    return Outcome("AMBIGUOUS", "MULTIPLE", note="The match is neither the account's mail nor its UPN")


def _look_up(directory: Directory, key: str) -> Outcome:
    try:
        return classify(key, directory.find_users(key))
    except GraphError as exc:
        return Outcome(
            "ERROR", "NONE", note=f"Lookup incomplete ({exc.kind}); try again later", error_kind=exc.kind
        )


def look_up_all(directory: Directory, keys: Iterable[str]) -> dict[str, Outcome]:
    keys = list(dict.fromkeys(keys))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return dict(zip(keys, pool.map(lambda k: _look_up(directory, k), keys), strict=True))


def run(upload: csvio.Upload, column: int, directory: Directory) -> Result:
    keys = [csvio.lookup_key(row[column]) for row in upload.rows]
    outcomes = look_up_all(directory, (k for k in keys if k is not None))

    # Duplicate groups (spec §7): an account reached by two or more distinct
    # addresses, numbered in the order the file first names it.
    keys_by_account: dict[str, list[str]] = {}
    for key in keys:
        outcome = outcomes.get(key) if key is not None else None
        if outcome is not None and outcome.status in RESOLVED and outcome.user is not None:
            seen = keys_by_account.setdefault(outcome.user.id, [])
            if key not in seen:
                seen.append(key)
    group_of = {
        account: str(number)
        for number, account in enumerate(
            (a for a, ks in keys_by_account.items() if len(ks) > 1), start=1
        )
    }

    counts = dict.fromkeys(STATUSES, 0)
    cells = []
    for key in keys:
        outcome = (
            outcomes[key]
            if key is not None
            else Outcome("INVALID_INPUT", "NONE", note="Blank or not an address")
        )
        counts[outcome.status] += 1
        user = outcome.user
        recommended = user.mail if user is not None and outcome.status in {"OK", "USE_PRIMARY"} else None
        cells.append(
            [
                outcome.status,
                outcome.match_type,
                COVERAGE,
                recommended or "",
                user.user_principal_name if user else "",
                user.display_name if user else "",
                user.id if user else "",
                group_of.get(user.id, "") if user else "",
                outcome.note,
            ]
        )
    errors = tuple(sorted({o.error_kind for o in outcomes.values() if o.status == "ERROR"}))
    return Result(
        csv=csvio.write(upload, cells),
        counts=counts,
        groups=len(group_of),
        rows=len(upload.rows),
        lookups=len(outcomes),
        error_kinds=errors,
    )
