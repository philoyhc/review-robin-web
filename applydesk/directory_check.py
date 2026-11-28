"""Addresses Apply Desk takes in, looked up in the directory (segment AD2Y).

An upload (Create dossiers', Invitees', Panels') hands its addresses here.
Each distinct address is looked up once through the host's Graph helper
(`cordware.graph.look_up_all`, as Review Robin's rosters are). One that
resolves to exactly one account (`OK`, `USE_PRIMARY`, `FOUND_NO_PRIMARY`)
binds that account's person (`people.from_directory`). Any other answer
leaves the address to the caller, which keeps it pending: not found is
kept and counted, never refused (author, 2026-11-28).

`look_up` asks and counts; it touches no database, so a caller can refuse
before writing anything (an expired sign-in, `stop`). `bind` then stores
what was found, in the caller's transaction. Nothing here talks to a
request: the route hands in the request's directory, or None when there is
none to ask, which checks nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from applydesk import people
from applydesk.models import Person
from cordware.graph import RESOLVED, Finder, Outcome, look_up_all

#: The lookup's time budget, in seconds, as Review Robin's upload has: a
#: lookup unfinished by then is *not checked*, and *Recheck* asks again.
BUDGET = 120.0

#: The outcomes that are the directory's answer about an address: bound,
#: or found to be nobody or several. Anything else is *not checked*.
ANSWERED = RESOLVED | {"NOT_FOUND", "AMBIGUOUS"}

#: Why nothing was checked when there was no directory to ask.
NO_TOKEN = "no_token"

#: The one failure that holds an upload (Review Robin's segment 20G): Graph
#: refusing an expired sign-in, which signing in again cures. No token,
#: ``forbidden`` and the rest save, counted as not checked.
RENEWABLE_KIND = "unauthorized"


@dataclass(frozen=True)
class Counts:
    """What a lookup came to, over its distinct addresses."""

    by_mail: int = 0
    by_upn: int = 0
    not_found: int = 0
    ambiguous: int = 0
    not_checked: int = 0

    @property
    def found(self) -> int:
        return self.by_mail + self.by_upn

    def as_dict(self) -> dict[str, int]:
        """The counts as an audit envelope or a reply names them."""
        return {
            "directory_by_mail": self.by_mail,
            "directory_by_upn": self.by_upn,
            "directory_not_found": self.not_found,
            "directory_ambiguous": self.ambiguous,
            "directory_not_checked": self.not_checked,
        }


@dataclass(frozen=True)
class Lookup:
    """Each distinct address's outcome, by its match key, and the tally."""

    outcomes: Mapping[str, Outcome] = field(default_factory=dict[str, Outcome])
    counts: Counts = Counts()
    #: Why any address went unchecked (`NO_TOKEN`, or Graph's failure
    #: kind), "" when every one was answered.
    unchecked_reason: str = ""

    @property
    def stop(self) -> bool:
        """Whether Graph refused the sign-in as expired: the caller saves
        nothing and asks the operator to sign in again."""
        return any(o.error_kind == RENEWABLE_KIND for o in self.outcomes.values())

    def resolved(self, address: str) -> Outcome | None:
        """The outcome that binds ``address``, or None."""
        key = people.email_key(address)
        found = self.outcomes.get(key) if key else None
        if found is None or found.status not in RESOLVED or found.user is None:
            return None
        return found


def _keys(addresses: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(k for k in (people.email_key(a) for a in addresses) if k))


def _tally(keys: list[str], outcomes: Mapping[str, Outcome]) -> tuple[Counts, str]:
    tally = dict.fromkeys(("by_mail", "by_upn", "not_found", "ambiguous", "not_checked"), 0)
    reason = ""
    for key in keys:
        outcome = outcomes.get(key)
        status = outcome.status if outcome is not None else "ERROR"
        if status == "OK":
            tally["by_mail"] += 1
        elif status in ("USE_PRIMARY", "FOUND_NO_PRIMARY"):
            tally["by_upn"] += 1
        elif status == "NOT_FOUND":
            tally["not_found"] += 1
        elif status == "AMBIGUOUS":
            tally["ambiguous"] += 1
        else:
            tally["not_checked"] += 1
            reason = reason or (outcome.error_kind if outcome else "") or "timeout"
    return Counts(**tally), reason


def look_up(
    directory: Finder | None, addresses: Iterable[str], *, budget: float = BUDGET
) -> Lookup:
    """Each distinct address looked up once, folded by `people.email_key`.
    With no directory nothing is asked, and every address is not checked
    (`NO_TOKEN`)."""
    keys = _keys(addresses)
    if not keys:
        return Lookup()
    if directory is None:
        return Lookup({}, Counts(not_checked=len(keys)), NO_TOKEN)
    outcomes = look_up_all(directory, keys, budget=budget)
    counts, reason = _tally(keys, outcomes)
    return Lookup(outcomes, counts, reason)


def bind(
    session: Session, lookup: Lookup, tenant_id: str, actor: Person | None
) -> dict[str, Person]:
    """Each address the directory resolved, bound to its account's person
    (`people.from_directory`: a bound row reused, a pending one with the
    address bound in place, else a new bound person), by its match key.
    The tenant is the uploader's own, as the search's add takes it. With
    no tenant nothing binds. Flushes."""
    if not tenant_id:
        return {}
    bound: dict[str, Person] = {}
    for key, outcome in lookup.outcomes.items():
        if outcome.status in RESOLVED and outcome.user is not None:
            bound[key] = people.from_directory(session, outcome.user, tenant_id, actor)
    return bound
