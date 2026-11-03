"""One person across the rosters: the directory check an import runs
(segment 21F), the same-person test, and the cross-roster and incoming
identity checks. Segment 20E rung 2, moved unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.schemas.imports import (
    ObserverImportRow,
    ReviewerImportRow,
    RevieweeImportRow,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services import directory_accounts
from app.services.email_identity import normalize_email

@dataclass(frozen=True)
class DirectoryCheck:
    """An import's directory check (segment 21F): the accounts its
    addresses resolved to, keyed by lookup key, and the counts its audit
    event records."""

    accounts: dict[str, directory_accounts.Account]
    counts: dict[str, int]
    #: The lookup keys the directory gave no answer for (not checked:
    #: no token, an expired one, a failed or unfinished lookup). A
    #: replace keeps such a row's earlier binding rather than dropping
    #: it (`_save`).
    unchecked: frozenset[str] = frozenset()
    #: ``"unauthorized"`` when Graph refused an expired token, which the
    #: upload routes answer by holding the file and asking to renew
    #: (segment 20G); ``None`` otherwise.
    stopped: str | None = None
    #: Why any address went unchecked (`directory_accounts.NO_TOKEN`, or
    #: Graph's failure kind), or ``None``; the import's audit event
    #: records it so the card's line can name it (segment 20G).
    unchecked_reason: str | None = None



def directory_check(
    directory: Any,
    addresses: list[str | None],
    known: Mapping[str, Any] | None = None,
) -> DirectoryCheck:
    """Resolve an import's addresses through ``directory`` (``None``:
    nothing checked) for `_save` to store and count (segment 21F).
    ``known``: answers the countdown already fetched (segment 20H Item
    6, `directory_lookups.recall`), not asked again."""
    return directory_checks(directory, [addresses], known=known)[0]


def directory_checks(
    directory: Any,
    rosters: list[list[str | None]],
    known: Mapping[str, Any] | None = None,
) -> list[DirectoryCheck]:
    """`directory_check` for several rosters saved by one request (Quick
    Setup, rehydrate): one lookup under one budget, so the request stays
    inside the front end's limit however many rosters it carries (Codex,
    #3430). Each roster is counted over its own addresses."""
    outcomes = directory_accounts.resolve(
        directory, [address for addresses in rosters for address in addresses], known=known
    )
    found = directory_accounts.accounts(outcomes)
    return [
        DirectoryCheck(
            accounts=found,
            counts=directory_accounts.counts(
                outcomes, addresses, checked=directory is not None
            ),
            unchecked=directory_accounts.unchecked(
                outcomes, addresses, checked=directory is not None
            ),
            stopped=directory_accounts.sign_in_stop(
                outcomes, addresses, checked=directory is not None
            ),
            unchecked_reason=directory_accounts.unchecked_reason(
                outcomes, addresses, checked=directory is not None
            ),
        )
        for addresses in rosters
    ]


def is_comparable_identity(identifier: str | None, name: str | None) -> bool:
    """Can this ``(identifier, name)`` pair disagree with another one?

    Two cannot, and both are skipped wherever the cross-roster rule is
    applied:

    * an identifier with no ``@`` — a reviewee's anonymous handle in the
      asymmetric mode, which is not a mailbox and cannot collide with
      one;
    * a row whose name is unset. ``Observer.display_name`` is nullable
      and its CSV column optional, where ``Reviewer.name`` and
      ``Reviewee.name`` are not — so without this an unnamed observer
      would conflict with every reviewer sharing its mailbox (19Q Item
      7, the author's two answers interacting).

    One function rather than the copy per call site the rule grew at
    rung 1: a mutant that removed only the importer's copy survived
    until a test went looking for it, and rung 2's Validate rule would
    have been a third. ``app.services.validation`` imports this for
    exactly that reason — the *membership* rule has one home even where
    the output shapes differ.
    """
    return "@" in (identifier or "") and bool(name)


#: Per roster: the model, its identity attribute, its name attribute,
#: and the label a message uses for it. The import-row classes spell the
#: same two fields differently, so each carries its own pair.
_IDENTITY_ROSTERS: dict[str, dict[str, str]] = {
    "reviewers": {
        "model_attr": "email",
        "row_attr": "email",
        "name_attr": "name",
        "row_name_attr": "name",
        "label": "reviewer",
        "field": "ReviewerEmail",
        "file": "Reviewers",
    },
    "reviewees": {
        "model_attr": "email_or_identifier",
        "row_attr": "email_or_identifier",
        "name_attr": "name",
        "row_name_attr": "name",
        "label": "reviewee",
        "field": "RevieweeEmail",
        "file": "Reviewees",
    },
    "observers": {
        "model_attr": "email",
        "row_attr": "email",
        "name_attr": "display_name",
        "row_name_attr": "display_name",
        "label": "observer",
        "field": "ObserverEmail",
        "file": "Observers",
    },
}

_IDENTITY_MODELS = {
    "reviewers": Reviewer,
    "reviewees": Reviewee,
    "observers": Observer,
}


def _identity_holders(
    db: Session, *, session_id: int, exclude: frozenset[str]
) -> dict[str, list[tuple[str, str]]]:
    """``{normalized email: [(roster label, name), ...]}`` for every
    roster not in ``exclude``, within one session — the rosters an
    upload replaces are left out, since their rows are about to go.

    Two kinds of row are skipped, for the same reason — they cannot
    disagree with a name — see :func:`is_comparable_identity`.

    **Every holder is kept, and none is chosen.** An earlier form of
    this collapsed each mailbox to one holder, which was wrong twice
    over (Codex review on #2485, 19Q Item 7 rung 2):

    * Reviewers and reviewees carry no DB uniqueness on
      ``(session_id, email)`` — that is why
      ``reviewers.duplicate_email`` and ``reviewees.duplicate_id`` exist
      as Validate rules — so one mailbox can already hold two names. A
      new row matching the *chosen* holder was then accepted while the
      other holder still disagreed with it, which is the rule this
      module exists to enforce, failing open.
    * The collapse picked the highest ``id``, and ids are table-local.
      Comparing a ``Reviewer.id`` against an ``Observer.id`` says
      nothing about which row came first, so "the most recently added
      holder" was not what it selected.

    Nothing here now depends on the order rows arrive in. Which holder a
    message cites is decided by :func:`_first_disagreeing_holder`, from
    the values rather than from the query.
    """
    holders: dict[str, list[tuple[str, str]]] = {}
    for roster, spec in _IDENTITY_ROSTERS.items():
        if roster in exclude:
            continue
        model = _IDENTITY_MODELS[roster]
        for row in (
            db.execute(select(model).where(model.session_id == session_id))
            .scalars()
            .all()
        ):
            identifier = getattr(row, spec["model_attr"]) or ""
            name = getattr(row, spec["name_attr"])
            if not is_comparable_identity(identifier, name):
                continue
            holders.setdefault(normalize_email(identifier), []).append(
                (spec["label"], name)
            )
    return holders


#: Roster label -> its position in ``_IDENTITY_ROSTERS``, so a message
#: naming one of several disagreeing holders names the same one every
#: time, on every dialect.
_ROSTER_ORDER = {
    spec["label"]: index
    for index, spec in enumerate(_IDENTITY_ROSTERS.values())
}


def _first_disagreeing_holder(
    holders: list[tuple[str, str]], name: str
) -> tuple[str, str] | None:
    """The holder to cite when one or more disagree with ``name``.

    **Any** disagreement is a conflict — the caller must not be able to
    slip a row past by matching one holder of a mailbox that already
    carries two names. Which one the 400 names is presentation, and is
    picked from the values (roster order, then name) rather than from
    the order the database returned: an assertion on a cited name is
    otherwise a false green, since SQLite hands an unordered ``SELECT``
    back in insertion order and Postgres does not owe it.
    """
    disagreeing = [held for held in holders if held[1] != name]
    if not disagreeing:
        return None
    return min(
        disagreeing, key=lambda held: (_ROSTER_ORDER[held[0]], held[1])
    )


def cross_table_identity_conflict(
    db: Session, *, session_id: int, kind: str, identifier: str, name: str
) -> tuple[str, str] | None:
    """The ``(roster label, name)`` already holding ``identifier`` under
    a *different* name, or ``None``.

    The single-row form of :func:`check_cross_table_identity`, for the
    create / edit services. Both call it, so the rule has one home —
    19Q Item 7 exists because the rule had one home and only the CSV
    path could reach it.

    A row of the same ``kind`` never conflicts: the whole roster is
    excluded, which is also why an edit does not collide with itself.
    Within-roster duplicates are each service's own ``_email_taken`` /
    ``_identifier_taken`` guard.
    """
    if kind not in _IDENTITY_ROSTERS:
        raise ValueError(
            f"cross_table_identity_conflict: unknown kind {kind!r}; "
            f"expected one of {sorted(_IDENTITY_ROSTERS)}"
        )
    if not is_comparable_identity(identifier, name):
        return None
    holders = _identity_holders(
        db, session_id=session_id, exclude=_with_mirrors(db, session_id, {kind})
    ).get(normalize_email(identifier), [])
    return _first_disagreeing_holder(holders, name)


def _with_mirrors(db: Session, session_id: int, kinds: set[str] | frozenset[str]) -> frozenset[str]:
    """``kinds``, plus the Reviewees roster when a Reviewers write is
    checked under symmetric review (segment 20B): every reviewee there
    mirrors a reviewer, so a reviewer's own mirror never conflicts with
    a correction of their name, and the reconcile carries it over."""
    if "reviewers" in kinds and db.execute(
        select(ReviewSession.symmetric_review).where(ReviewSession.id == session_id)
    ).scalar_one_or_none():
        return frozenset(kinds) | {"reviewees"}
    return frozenset(kinds)


def check_cross_table_identity(
    db: Session,
    *,
    session_id: int,
    rows: list[ReviewerImportRow]
    | list[RevieweeImportRow]
    | list[ObserverImportRow],
    kind: str,
) -> list[ValidationIssue]:
    """Block CSV uploads where a row's email is already present in
    *another* roster (within the same session) under a different name.

    Email is the unique person-identifier across the three rosters; name
    is the human-facing label. Same email + same name is allowed — one
    person is commonly both reviewer and reviewee, and may observe too.
    Same email + different name is a blocking error.

    **Names compare exactly** (author's ruling, 2026-09-19), as this
    function has always done; what changed is that the rule is now
    chosen rather than inherited. Exact means **case-sensitive** — and
    not whitespace-sensitive, because every path trims a name long
    before it arrives here (`_cell` on the CSV side, each service's
    `_normalised_name`). A first draft of this docstring claimed a
    trailing space would conflict; the test that went looking for it
    found 303.

    **Three-way since 19Q Item 7** (author, 2026-09-19). It compared
    reviewers against reviewees and back, and observers took part in
    neither direction — nor did the observer CSV import call this at
    all. Each kind now compares against the other two.

    An unrecognised ``kind`` raises. It used to fall through both
    branches and return ``[]``, so an observer CSV routed here would
    have been checked, found nothing, and reported success — a guard
    that passes by not running.
    """
    if kind not in _IDENTITY_ROSTERS:
        raise ValueError(
            f"check_cross_table_identity: unknown kind {kind!r}; "
            f"expected one of {sorted(_IDENTITY_ROSTERS)}"
        )
    return check_incoming_identity(
        db, session_id=session_id, incoming={kind: rows}
    )[kind]


def check_incoming_identity(
    db: Session,
    *,
    session_id: int,
    incoming: Mapping[str, Sequence[Any]],
) -> dict[str, list[ValidationIssue]]:
    """:func:`check_cross_table_identity` for several roster files
    uploaded together, keyed by kind (``guide/quick_setup_update.md``
    Item 1, author's rule of 2026-10-12).

    Each file is checked against the **other uploaded files** and
    against the **existing rosters not being replaced**. A roster whose
    file is attached is about to go, so its rows hold nothing. One file
    is exactly today's rule, which is why
    :func:`check_cross_table_identity` is this function with one kind.

    A row disagreeing with an existing roster is reported as before;
    one that agrees there but disagrees with another uploaded file gets
    its own ``problem``, naming that file. The skips and the exact-name
    comparison are the single-file rule's: :func:`is_comparable_identity`
    and :func:`_first_disagreeing_holder`.

    Only checks — saves nothing — so a caller can check every file
    before it writes any. An unrecognised kind raises.
    """
    unknown = sorted(set(incoming) - set(_IDENTITY_ROSTERS))
    if unknown:
        raise ValueError(
            f"check_incoming_identity: unknown kind(s) {unknown}; "
            f"expected among {sorted(_IDENTITY_ROSTERS)}"
        )

    existing = _identity_holders(
        db, session_id=session_id, exclude=_with_mirrors(db, session_id, set(incoming))
    )
    uploaded = {
        kind: _incoming_holders(kind, rows) for kind, rows in incoming.items()
    }

    issues_by_kind: dict[str, list[ValidationIssue]] = {}
    for kind, rows in incoming.items():
        spec = _IDENTITY_ROSTERS[kind]
        issues: list[ValidationIssue] = []
        for index, row in enumerate(rows, start=1):
            identifier = getattr(row, spec["row_attr"]) or ""
            name = getattr(row, spec["row_name_attr"])
            if not is_comparable_identity(identifier, name):
                continue
            key = normalize_email(identifier)
            held = _first_disagreeing_holder(existing.get(key, []), name)
            if held is not None:
                holder_label, holder_name = held
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source=kind,
                        row_number=index,
                        field=spec["field"],
                        message=(
                            f"{spec['field']} '{identifier}' is already used "
                            f"by {holder_label} '{holder_name}' in this "
                            f"session — names must match (got '{name}')."
                        ),
                        problem=(
                            f"{spec['field']} is already used under a "
                            f"different name in another roster"
                        ),
                    )
                )
                continue
            held = _first_disagreeing_holder(
                [
                    holder
                    for other, holders in uploaded.items()
                    if other != kind
                    for holder in holders.get(key, [])
                ],
                name,
            )
            if held is None:
                continue
            holder_label, holder_name = held
            holder_file = _FILE_BY_LABEL[holder_label]
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=kind,
                    row_number=index,
                    field=spec["field"],
                    message=(
                        f"{spec['field']} '{identifier}' is used by "
                        f"{holder_label} '{holder_name}' in the uploaded "
                        f"{holder_file} file — names must match "
                        f"(got '{name}')."
                    ),
                    problem=(
                        f"{spec['field']} is used under a different name "
                        f"in the uploaded {holder_file} file"
                    ),
                )
            )
        issues_by_kind[kind] = issues
    return issues_by_kind


#: Roster label -> how a message names that roster's uploaded file.
_FILE_BY_LABEL = {
    spec["label"]: spec["file"] for spec in _IDENTITY_ROSTERS.values()
}


def _incoming_holders(
    kind: str, rows: Sequence[Any]
) -> dict[str, list[tuple[str, str]]]:
    """:func:`_identity_holders` for an uploaded file's parsed rows:
    ``{normalized email: [(roster label, name), ...]}``, skipping what
    :func:`is_comparable_identity` skips."""
    spec = _IDENTITY_ROSTERS[kind]
    holders: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        identifier = getattr(row, spec["row_attr"]) or ""
        name = getattr(row, spec["row_name_attr"])
        if not is_comparable_identity(identifier, name):
            continue
        holders.setdefault(normalize_email(identifier), []).append(
            (spec["label"], name)
        )
    return holders
