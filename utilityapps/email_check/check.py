"""The check itself: each distinct address looked up once, each row
classified, accounts under more than one address grouped (spec §§5–7;
segment U1, rung 5). The CSV in and out is `csvio`'s; the directory is
the host's (`cordware.graph`).

A lookup that did not finish is `ERROR`, never `NOT_FOUND` (spec §6): the
directory could not be asked, which says nothing about the address.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cordware import graph
from cordware.graph import (  # noqa: F401  (re-exported: the checker's vocabulary)
    RESOLVED,
    SIGN_IN_KINDS,
    Directory,
    DirectoryUser,
    GraphError,
    Outcome,
    classify,
)
from cordware.graph import error_outcome as _error
from utilityapps.email_check import csvio

STATUSES = ("OK", "USE_PRIMARY", "FOUND_NO_PRIMARY", "NOT_FOUND", "AMBIGUOUS", "INVALID_INPUT", "ERROR")
# `RESOLVED` (a row naming one account, so it can join a duplicate group),
# `SIGN_IN_KINDS`, `Outcome` and `classify` are `cordware.graph`'s, shared
# with RRW's roster upload from segment 21F.
#: Alias lookup is not built (spec phase 2), so every run says so.
COVERAGE = "BASIC_ONLY"
#: Lookups in flight at once: conservative, as spec §10 asks.
WORKERS = 4
#: The whole check's time budget, in seconds. A lookup not finished by
#: then is `ERROR` (`timeout`) and the rest still download (spec §§4, 10):
#: under App Service's front-end limit of about 230 s, so throttling
#: cannot lose the whole export (diff-reviewer, `#3411`).
BUDGET = 120.0
#: The page's batches (segment U2): at most this many keys per lookup
#: request, each request under its own budget.
BATCH_MAX = 25
BATCH_BUDGET = 60.0
#: What the outcomes a page carries back may hold (segment U2).
MATCH_TYPES = frozenset({"PRIMARY_MAIL", "UPN", "NONE", "MULTIPLE"})
#: An `ERROR`'s kinds: the directory's, the budget's, and a page that
#: stopped before every key was sent (segment U2). The log carries these
#: and nothing else.
ERROR_KINDS = frozenset({*GraphError.KINDS, "timeout", "incomplete"})
_FIELD_MAX = 512


@dataclass(frozen=True)
class Result:
    csv: str
    counts: dict[str, int]
    groups: int
    rows: int
    lookups: int
    error_kinds: tuple[str, ...]


def look_up_all(
    directory: Directory, keys: Iterable[str], *, budget: float = BUDGET
) -> dict[str, Outcome]:
    """`cordware.graph.look_up_all` at the checker's own pace (`WORKERS`)."""
    return graph.look_up_all(directory, keys, budget=budget, workers=WORKERS)


def outcome_json(outcome: Outcome) -> dict:
    """One outcome as the lookup endpoint returns it and the page carries
    it back to `/check` (segment U2)."""
    user = outcome.user
    return {
        "status": outcome.status,
        "match_type": outcome.match_type,
        "note": outcome.note,
        "error_kind": outcome.error_kind,
        "user": None
        if user is None
        else {
            "id": user.id,
            "display_name": user.display_name,
            "mail": user.mail,
            "user_principal_name": user.user_principal_name,
        },
    }


class OutcomesRejected(ValueError):
    """Carried outcomes that don't fit the file or the shape `outcome_json` writes."""


def _text(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or len(value) > _FIELD_MAX:
        raise OutcomesRejected("a field is not a short string")
    return value


def outcomes_from_json(data: object, keys: Iterable[str]) -> dict[str, Outcome]:
    """Carried outcomes, checked against the file's keys. The shape is
    checked, not the truth: they come from the super-admin's own page and
    go only into the super-admin's own download (segment U2)."""
    if not isinstance(data, dict):
        raise OutcomesRejected("the outcomes are not an object")
    allowed = set(keys)
    outcomes: dict[str, Outcome] = {}
    for key, raw in data.items():
        if key not in allowed:
            raise OutcomesRejected("an outcome names an address the file does not have")
        if not isinstance(raw, dict):
            raise OutcomesRejected("an outcome is not an object")
        status = raw.get("status")
        match_type = raw.get("match_type")
        if status not in STATUSES or status == "INVALID_INPUT" or match_type not in MATCH_TYPES:
            raise OutcomesRejected("an outcome has an unknown status or match type")
        user_raw = raw.get("user")
        user = None
        if user_raw is not None:
            if not isinstance(user_raw, dict):
                raise OutcomesRejected("an outcome's account is not an object")
            user = DirectoryUser(
                _text(user_raw.get("id")),
                _text(user_raw.get("display_name")),
                _text(user_raw.get("mail"), optional=True),
                _text(user_raw.get("user_principal_name")),
            )
        if (status in RESOLVED) != (user is not None):
            raise OutcomesRejected("an outcome's account does not fit its status")
        error_kind = _text(raw.get("error_kind", ""))
        if (status == "ERROR") != (error_kind in ERROR_KINDS):
            raise OutcomesRejected("an outcome's error kind does not fit its status")
        outcomes[key] = Outcome(status, match_type, user, _text(raw.get("note", "")), error_kind)
    return outcomes


def run(
    upload: csvio.Upload,
    column: int,
    directory: Directory | None,
    *,
    carried: dict[str, Outcome] | None = None,
    stopped: str = "",
) -> Result:
    """Check the file: look every key up, or, with ``carried``, take the
    outcomes the page's batches collected (segment U2). A key they lack is
    `ERROR`: ``stopped``'s kind when a refused sign-in stopped the batches,
    else `incomplete`."""
    keys = [csvio.lookup_key(row[column]) for row in upload.rows]
    if carried is None:
        assert directory is not None
        outcomes = look_up_all(directory, (k for k in keys if k is not None))
    else:
        missing = _error(stopped if stopped in SIGN_IN_KINDS else "incomplete")
        outcomes = {k: carried.get(k, missing) for k in keys if k is not None}

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
