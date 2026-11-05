"""Append and merge (segment 19Z): what each refuses and how a merge
matches and updates rows. Segment 20E rung 2, moved unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ReviewSession,
    User,
)
from app.schemas.imports import (
    ObserverImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit, directory_accounts
from app.services.csv_imports._identity import (
    _IDENTITY_MODELS,
    _IDENTITY_ROSTERS,
    DirectoryCheck,
    cross_table_identity_conflict,
)
from app.services.email_identity import normalize_email, normalize_object_id

# What the package's other modules import from this one; the leading
# underscore marks a name private to the package, not to the module.
__all__ = [
    "AppendConflict",
    "_MERGE_KEEPS",
    "_merge_rows",
    "append_conflicts",
    "merge_conflicts",
]


class AppendConflict(Exception):
    """An append refused at its save, under the session lock (segment
    19Z): a file row already on the roster, or on a directory account
    already there. ``issues`` name the rows, as `append_conflicts`
    reports them, so a caller renders them as the file's problems."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__(f"{len(issues)} row(s) already on the roster")
        self.issues = issues


def append_conflicts(
    db: Session,
    *,
    session_id: int,
    kind: str,
    rows: Sequence[ReviewerImportRow | RevieweeImportRow | ObserverImportRow],
    directory: DirectoryCheck | None = None,
) -> list[ValidationIssue]:
    """The rows an append to ``kind``'s roster refuses (segment 19Z;
    author, 2026-10-31): a row whose folded address is already on the
    roster, and a row whose address resolved, in ``directory``, to an
    account a row on the roster is bound to. The within-file duplicate
    rule, extended to the rows already saved. Rows are numbered as the
    parser numbers them, from 1."""
    spec = _IDENTITY_ROSTERS[kind]
    model = _IDENTITY_MODELS[kind]
    held = list(db.execute(select(model).where(model.session_id == session_id)).scalars())
    addresses = {normalize_email(getattr(row, spec["model_attr"])) for row in held} - {""}
    accounts = {
        normalize_object_id(row.directory_object_id) for row in held if row.directory_object_id
    }
    issues: list[ValidationIssue] = []
    for index, row in enumerate(rows, start=1):
        address = getattr(row, spec["row_attr"]) or ""
        if normalize_email(address) in addresses:
            problem = f"{spec['field']} is already on the roster"
            message = f"{spec['field']} '{address}' is already on the roster."
        else:
            account = (
                directory.accounts.get(directory_accounts.key(address) or "")
                if directory is not None
                else None
            )
            if account is None or normalize_object_id(account.object_id) not in accounts:
                continue
            problem = f"{spec['field']} is a directory account already on the roster"
            message = (
                f"{spec['field']} '{address}' is the same directory account "
                f"as a {spec['label']} already on the roster."
            )
        issues.append(
            ValidationIssue(
                severity=Severity.error,
                source=kind,
                row_number=index,
                field=spec["field"],
                message=message,
                problem=problem,
            )
        )
    return issues


def merge_conflicts(
    *,
    kind: str,
    rows: Sequence[ReviewerImportRow | RevieweeImportRow | ObserverImportRow],
    directory: DirectoryCheck | None = None,
) -> list[ValidationIssue]:
    """The rows a merge into ``kind``'s roster refuses (segment 19Z,
    upsert amendment): two file rows whose addresses resolved to one
    directory account, so one person twice. Two rows at one address are
    already the parser's within-file duplicate."""
    spec = _IDENTITY_ROSTERS[kind]
    first: dict[str, int] = {}
    issues: list[ValidationIssue] = []
    for index, row in enumerate(rows, start=1):
        address = getattr(row, spec["row_attr"]) or ""
        account = (
            directory.accounts.get(directory_accounts.key(address) or "")
            if directory is not None
            else None
        )
        if account is None:
            continue
        held = first.setdefault(normalize_object_id(account.object_id), index)
        if held != index:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=kind,
                    row_number=index,
                    field=spec["field"],
                    message=(
                        f"{spec['field']} '{address}' is the same directory account as row {held}."
                    ),
                    problem=f"{spec['field']} is a directory account named twice in the file",
                )
            )
    return issues


#: What a merge never writes from a file: the row's session and address.
_MERGE_KEEPS = frozenset({"session_id", "email", "email_or_identifier"})


def _merge_rows(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    model: Any,
    kind: str,
    existing: list[Any],
    rows: list[Any],
    to_kwargs: Any,
    directory: DirectoryCheck | None,
    correlation_id: str,
) -> tuple[int, int, int]:
    """Merge ``rows`` into ``existing`` (segment 19Z, upsert amendment).
    Returns ``(added, updated, unchanged)``.

    A row matches an existing one by its folded address, or by the
    directory account its address resolved to; the lowest id answers a
    roster already holding two. A matched row takes every non-blank
    cell, Status only where its cell was filled in (``status_given``),
    and keeps its address; an unbound row whose own address resolved is bound,
    unless another row already holds that account, which refuses the merge
    as an append is refused (`AppendConflict`). Each updated row writes its
    ``*.updated`` event. Any other row is added.

    A name change on a row matched by account is checked against the
    other rosters at the row's **kept** address, which the route's check
    over the file's addresses cannot see; a conflict refuses the merge
    (`AppendConflict`) before any row is touched (Codex, #3440)."""
    # Local: observers imports this module.
    from app.services.observers import same_cohort_rule

    spec = _IDENTITY_ROSTERS[kind]
    by_address: dict[str, Any] = {}
    by_account: dict[str, Any] = {}
    for held in sorted(existing, key=lambda r: r.id):
        by_address.setdefault(normalize_email(getattr(held, spec["model_attr"])), held)
        if held.directory_object_id:
            by_account.setdefault(normalize_object_id(held.directory_object_id), held)
    added = updated = unchanged = 0
    planned: list[tuple[Any, Any, dict[str, Any], Any]] = []
    issues: list[ValidationIssue] = []
    # Two file rows landing on one existing row (one by address, one by
    # account) are one person twice: refused, not applied in turn.
    claimed: dict[int, int] = {}
    for index, row in enumerate(rows, start=1):
        kwargs = to_kwargs(row, session.id)
        address = kwargs.get(spec["model_attr"])
        account = (
            directory.accounts.get(directory_accounts.key(address) or "")
            if directory is not None
            else None
        )
        held = by_address.get(normalize_email(address))
        if held is None and account is not None:
            held = by_account.get(normalize_object_id(account.object_id))
            new_name = kwargs.get(spec["name_attr"])
            if held is not None and new_name is not None:
                kept = getattr(held, spec["model_attr"])
                conflict = cross_table_identity_conflict(
                    db, session_id=session.id, kind=kind, identifier=kept, name=new_name
                )
                if conflict is not None:
                    holder_label, holder_name = conflict
                    issues.append(
                        ValidationIssue(
                            severity=Severity.error,
                            source=kind,
                            row_number=index,
                            field=spec["field"],
                            message=(
                                f"{spec['field']} '{address}' is {kept}, used by "
                                f"{holder_label} '{holder_name}' in this session; "
                                "names must match."
                            ),
                            problem=(
                                f"{spec['field']} is used under a different name in another roster"
                            ),
                        )
                    )
        if held is not None:
            first = claimed.setdefault(held.id, index)
            if first != index:
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source=kind,
                        row_number=index,
                        field=spec["field"],
                        message=(
                            f"{spec['field']} '{address}' is the same {spec['label']} "
                            f"as row {first}."
                        ),
                        problem=f"{spec['field']} names a {spec['label']} another row also names",
                    )
                )
        if held is not None and account is not None and not held.directory_object_id:
            other = by_account.get(normalize_object_id(account.object_id))
            if other is not None and other.id != held.id:
                # Binding this row would put a second row on an account
                # the roster already holds: one person twice, which an
                # append refuses too (assessment 2026-11-02, M2).
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source=kind,
                        row_number=index,
                        field=spec["field"],
                        message=(
                            f"{spec['field']} '{address}' is the same directory "
                            f"account as {spec['label']} "
                            f"'{getattr(other, spec['model_attr'])}' already on the roster."
                        ),
                        problem=f"{spec['field']} is a directory account already on the roster",
                    )
                )
        planned.append((held, row, kwargs, account))
    if issues:
        raise AppendConflict(issues)
    for held, row, kwargs, account in planned:
        if held is None:
            if directory is not None:
                kwargs.update(directory_accounts.columns(account))
            db.add(model(**kwargs))
            added += 1
            continue
        changes: dict[str, list[object]] = {}
        for name, value in kwargs.items():
            if name in _MERGE_KEEPS or value is None:
                continue
            if name == "status" and not getattr(row, "status_given", False):
                continue
            if name == "cohort_rule" and same_cohort_rule(held.cohort_rule, value):
                continue
            if getattr(held, name) != value:
                changes[name] = [getattr(held, name), value]
        if account is not None and not held.directory_object_id:
            for name, value in directory_accounts.columns(account).items():
                if getattr(held, name) != value:
                    changes[name] = [getattr(held, name), value]
        if not changes:
            unchanged += 1
            continue
        for name, (_, value) in changes.items():
            setattr(held, name, value)
        audit.write_event(
            db,
            event_type=f"{spec['label']}.updated",
            summary=f"Updated {spec['label']} {getattr(held, spec['model_attr'])} (merge)",
            actor_user_id=user.id,
            session=session,
            payload=audit.changes(changes),
            refs={f"{spec['label']}_id": held.id},
            correlation_id=correlation_id,
        )
        updated += 1
    db.flush()
    return added, updated, unchanged
