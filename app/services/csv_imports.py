from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.schemas.imports import (
    ObserverImportRow,
    RelationshipImportRow,
    ReviewerImportRow,
    RevieweeImportRow,
)
from app.logging_config import get_logger
from app.schemas.observer_cohort_rule import CohortRuleSet
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit, field_labels, field_label_csv
from app.services import roster_bulk
from app.services import invitations as invitations_service
from app.services import session_lifecycle as lifecycle
from app.services.email_identity import EMAIL_RE, normalize_email

log = get_logger(__name__)

MAX_BYTES = 1 * 1024 * 1024
MAX_ROWS = 5000


@dataclass
class ParseResult:
    rows: (
        list[ReviewerImportRow]
        | list[RevieweeImportRow]
        | list[ObserverImportRow]
        | list[RelationshipImportRow]
    )
    issues: list[ValidationIssue]
    # Segment 19C Item 1 — friendly-label overrides captured from the
    # roster header's ``<Column>.<label>`` suffixes, keyed by
    # ``(source_type, source_field)``. Empty for a header with no
    # suffixes; the save step reconciles (upsert present, clear absent).
    field_labels: dict[tuple[str, str], str] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return any(issue.is_blocking for issue in self.issues)


def decode_csv(
    content: bytes, source: str, *, max_bytes: int = MAX_BYTES
) -> tuple[str | None, ValidationIssue | None]:
    """Decode a CSV upload body to text, returning a structured
    ``ValidationIssue`` instead of raising on the two operator-facing
    failure modes (file too large / not valid UTF-8).

    ``max_bytes`` defaults to the reviewer / reviewee import ceiling
    (``MAX_BYTES``) and is overridable so a caller with a different
    ceiling need not fork the helper. **No production caller overrides it
    today** — only ``test_logging_observability.py``, exercising the
    too-large path.
    The one that did was the manual-assignments importer, retired with
    the CSV-upload path in 16A PR 5 along with its ``MANUAL_CSV_MAX_BYTES``
    constant — this docstring went on naming both for four months.
    """
    if len(content) > max_bytes:
        log.warning(
            "csv import rejected",
            extra={"source": source, "reason": "too_large", "bytes": len(content)},
        )
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message=f"File too large (max {max_bytes // 1024} KiB)",
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        log.warning(
            "csv import rejected",
            extra={"source": source, "reason": "not_utf8"},
        )
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message="File is not valid UTF-8",
        )
    return text, None


def _read_dict_rows(
    text: str,
    source: str,
) -> tuple[
    list[dict[str, str]] | None,
    list[str],
    dict[tuple[str, str], str],
    ValidationIssue | None,
]:
    """Read the CSV into row dicts keyed by **canonical** column names.

    Returns ``(rows, canonical_fieldnames, field_labels, issue)``. The
    header row is normalised (Segment 19C Item 1): any labelable tag
    column's ``.label`` suffix is stripped to the bare canonical name —
    so row access and the missing-column checks are unchanged — and the
    captured ``(source_type, source_field) -> label`` overrides are
    returned alongside. ``DictReader.fieldnames`` is reassigned to the
    canonical names *after* the header row is consumed, so every data
    row maps by the bare column name.
    """
    reader = csv.DictReader(io.StringIO(text))
    raw_fieldnames = reader.fieldnames
    if raw_fieldnames is None:
        return (
            None,
            [],
            {},
            ValidationIssue(
                severity=Severity.error,
                source=source,
                message="CSV has no header row",
            ),
        )
    canonical, captured = field_label_csv.normalize_headers(list(raw_fieldnames))
    reader.fieldnames = canonical
    rows = list(reader)
    if len(rows) > MAX_ROWS:
        return (
            None,
            canonical,
            captured,
            ValidationIssue(
                severity=Severity.error,
                source=source,
                message=f"Too many rows (max {MAX_ROWS})",
            ),
        )
    return rows, canonical, captured, None


def _missing_columns_issues(
    fieldnames: list[str],
    required: list[str],
    source: str,
) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            severity=Severity.error,
            source=source,
            message=f"Missing required column: {col}",
            field=col,
        )
        for col in required
        if col not in fieldnames
    ]


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    return value.strip() if value else ""


def _none_if_blank(row: dict[str, str], key: str) -> str | None:
    value = _cell(row, key)
    return value or None


def _profile_link(row: dict[str, str]) -> str | None:
    """The roster's profile link, from ``ProfileLink`` or, failing that,
    the legacy ``PhotoLink`` header (19T Item 5 renamed the column; files
    and exported bundles written before it still import). A non-blank
    ``ProfileLink`` wins when a file carries both."""
    return _none_if_blank(row, "ProfileLink") or _none_if_blank(row, "PhotoLink")


# Segment 18P PR C — the roster soft-delete states, shared by the
# reviewer / reviewee / observer parsers. Mirrors
# ``reviewers._VALID_STATUSES``.
_VALID_ROSTER_STATUSES: frozenset[str] = frozenset({"active", "inactive"})


def _parse_status(
    row: dict[str, str], *, source: str, row_number: int
) -> str | ValidationIssue:
    """Parse an optional ``Status`` cell → ``active`` / ``inactive``.

    Blank or absent → ``"active"`` (back-compat: a pre-18P-C roster
    CSV carries no ``Status`` column and should re-import everyone
    active). A present, non-empty value outside the allowed set is a
    blocking per-row error.
    """
    # not-identity: a roster Status enum from a CSV cell, not an email.
    value = _cell(row, "Status").lower()
    if not value:
        return "active"
    if value not in _VALID_ROSTER_STATUSES:
        return ValidationIssue(
            severity=Severity.error,
            source=source,
            row_number=row_number,
            field="Status",
            message=(
                f"Status must be one of {sorted(_VALID_ROSTER_STATUSES)}; "
                f"got {value!r}"
            ),
        )
    return value


def _parse_email(
    value: str,
    *,
    strict: bool,
    source: str,
    row_number: int,
    field: str,
) -> str | ValidationIssue:
    """Validate ``value`` as an email address.

    With ``strict=True`` the value must match ``EMAIL_RE`` — the
    reviewer path, where every reviewer needs an institutional email
    for auth.

    With ``strict=False`` non-email identifiers are accepted (no
    ``@``); but if an ``@`` is present the value must still match
    ``EMAIL_RE`` so typos like ``foo@`` or ``@bar`` are caught
    rather than imported and dying later on send. This is the
    reviewee path today, where reviewees aren't expected to use the
    app.

    The ``strict`` flag is the seam for the future symmetric mode
    where reviewees use the app and require institutional email; at
    that point the reviewee call site flips ``strict=True`` (or
    threads it from a per-session toggle).
    """
    if not strict and "@" not in value:
        return value
    if not EMAIL_RE.fullmatch(value):
        return ValidationIssue(
            severity=Severity.error,
            source=source,
            row_number=row_number,
            field=field,
            message=f"{field} '{value}' is not a valid email address",
        )
    return value


def parse_reviewer_csv(content: bytes) -> ParseResult:
    source = "reviewers"
    issues: list[ValidationIssue] = []

    text, decode_issue = decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    raw_rows, fieldnames, captured_labels, count_issue = _read_dict_rows(
        text, source
    )
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    issues.extend(
        _missing_columns_issues(fieldnames, ["ReviewerName", "ReviewerEmail"], source)
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    parsed: list[ReviewerImportRow] = []
    seen_emails: dict[str, tuple[int, str]] = {}

    for index, raw in enumerate(raw_rows, start=1):
        name = _cell(raw, "ReviewerName")
        email = _cell(raw, "ReviewerEmail")
        if not name:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerName",
                    message="ReviewerName is required",
                )
            )
            continue
        if not email:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message="ReviewerEmail is required",
                )
            )
            continue
        email_check = _parse_email(
            email,
            strict=True,
            source=source,
            row_number=index,
            field="ReviewerEmail",
        )
        if isinstance(email_check, ValidationIssue):
            issues.append(email_check)
            continue
        prior = seen_emails.get(normalize_email(email))
        if prior is not None:
            prior_index, prior_name = prior
            if prior_name == name:
                message = (
                    f"Duplicate ReviewerEmail '{email}' "
                    f"(also on row {prior_index})"
                )
            else:
                message = (
                    f"ReviewerEmail '{email}' was used for '{prior_name}' "
                    f"on row {prior_index} — names must match."
                )
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message=message,
                )
            )
            continue
        seen_emails[normalize_email(email)] = (index, name)
        status = _parse_status(raw, source=source, row_number=index)
        if isinstance(status, ValidationIssue):
            issues.append(status)
            continue
        parsed.append(
            ReviewerImportRow(
                name=name,
                email=email,
                profile_link=_profile_link(raw),
                tag_1=_none_if_blank(raw, "ReviewerTag1"),
                tag_2=_none_if_blank(raw, "ReviewerTag2"),
                tag_3=_none_if_blank(raw, "ReviewerTag3"),
                status=status,
            )
        )

    return ParseResult(rows=parsed, issues=issues, field_labels=captured_labels)


def parse_reviewee_csv(content: bytes) -> ParseResult:
    source = "reviewees"
    issues: list[ValidationIssue] = []

    text, decode_issue = decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    raw_rows, fieldnames, captured_labels, count_issue = _read_dict_rows(
        text, source
    )
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    issues.extend(
        _missing_columns_issues(fieldnames, ["RevieweeName", "RevieweeEmail"], source)
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    parsed: list[RevieweeImportRow] = []
    seen_identifiers: dict[str, tuple[int, str]] = {}

    for index, raw in enumerate(raw_rows, start=1):
        name = _cell(raw, "RevieweeName")
        identifier = _cell(raw, "RevieweeEmail")
        if not name:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeName",
                    message="RevieweeName is required",
                )
            )
            continue
        if not identifier:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message="RevieweeEmail is required",
                )
            )
            continue
        identifier_check = _parse_email(
            identifier,
            strict=False,
            source=source,
            row_number=index,
            field="RevieweeEmail",
        )
        if isinstance(identifier_check, ValidationIssue):
            issues.append(identifier_check)
            continue
        prior = seen_identifiers.get(normalize_email(identifier))
        if prior is not None:
            prior_index, prior_name = prior
            if prior_name == name:
                message = (
                    f"Duplicate RevieweeEmail '{identifier}' "
                    f"(also on row {prior_index})"
                )
            else:
                message = (
                    f"RevieweeEmail '{identifier}' was used for '{prior_name}' "
                    f"on row {prior_index} — names must match."
                )
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message=message,
                )
            )
            continue
        seen_identifiers[normalize_email(identifier)] = (index, name)
        status = _parse_status(raw, source=source, row_number=index)
        if isinstance(status, ValidationIssue):
            issues.append(status)
            continue
        parsed.append(
            RevieweeImportRow(
                name=name,
                email_or_identifier=identifier,
                profile_link=_profile_link(raw),
                tag_1=_none_if_blank(raw, "RevieweeTag1"),
                tag_2=_none_if_blank(raw, "RevieweeTag2"),
                tag_3=_none_if_blank(raw, "RevieweeTag3"),
                status=status,
            )
        )

    return ParseResult(rows=parsed, issues=issues, field_labels=captured_labels)


def parse_observer_csv(content: bytes) -> ParseResult:
    """Parse an Observers CSV upload. Required column:
    ``ObserverEmail``. Optional columns: ``ObserverName``,
    ``ObserverTag1``, ``CohortRule``. Other columns are ignored.

    Observers carry a single ``tag_1`` (not three) per the model
    note in ``app/db/models/observer.py``. Email is the auth-
    bearing identity and is required + strict-shape-validated;
    duplicate emails within the same CSV are blocking errors.

    Segment 18P PR B — a ``CohortRule`` cell (compact JSON) round-
    trips the per-observer cohort match rule. It's re-validated
    through ``CohortRuleSet`` here (bad JSON / bad shape is a
    blocking error), so an imported rule is as trustworthy as one
    saved through the editor.
    """
    source = "observers"
    issues: list[ValidationIssue] = []

    text, decode_issue = decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    # Observers carry no renamable friendly-label slots, so the
    # captured-label map is always empty here (Segment 19C Item 1).
    raw_rows, fieldnames, _captured_labels, count_issue = _read_dict_rows(
        text, source
    )
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    issues.extend(
        _missing_columns_issues(fieldnames, ["ObserverEmail"], source)
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    parsed: list[ObserverImportRow] = []
    seen_emails: dict[str, int] = {}

    for index, raw in enumerate(raw_rows, start=1):
        email = _cell(raw, "ObserverEmail")
        if not email:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ObserverEmail",
                    message="ObserverEmail is required",
                )
            )
            continue
        email_check = _parse_email(
            email,
            strict=True,
            source=source,
            row_number=index,
            field="ObserverEmail",
        )
        if isinstance(email_check, ValidationIssue):
            issues.append(email_check)
            continue
        prior = seen_emails.get(normalize_email(email))
        if prior is not None:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ObserverEmail",
                    message=(
                        f"Duplicate ObserverEmail '{email}' "
                        f"(also on row {prior})"
                    ),
                )
            )
            continue
        seen_emails[normalize_email(email)] = index

        status = _parse_status(raw, source=source, row_number=index)
        if isinstance(status, ValidationIssue):
            issues.append(status)
            continue

        cohort_raw = _none_if_blank(raw, "CohortRule")
        cohort_rule: dict[str, Any] | None = None
        if cohort_raw is not None:
            try:
                loaded = json.loads(cohort_raw)
            except json.JSONDecodeError:
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source=source,
                        row_number=index,
                        field="CohortRule",
                        message="CohortRule is not valid JSON",
                    )
                )
                continue
            try:
                ruleset = CohortRuleSet.model_validate(loaded)
            except ValidationError:
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source=source,
                        row_number=index,
                        field="CohortRule",
                        message=(
                            "CohortRule failed cohort-rule schema "
                            "validation"
                        ),
                    )
                )
                continue
            cohort_rule = ruleset.model_dump(mode="json")

        parsed.append(
            ObserverImportRow(
                email=email,
                display_name=_none_if_blank(raw, "ObserverName"),
                tag_1=_none_if_blank(raw, "ObserverTag1"),
                status=status,
                cohort_rule=cohort_rule,
            )
        )

    return ParseResult(rows=parsed, issues=issues)


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
    },
    "reviewees": {
        "model_attr": "email_or_identifier",
        "row_attr": "email_or_identifier",
        "name_attr": "name",
        "row_name_attr": "name",
        "label": "reviewee",
        "field": "RevieweeEmail",
    },
    "observers": {
        "model_attr": "email",
        "row_attr": "email",
        "name_attr": "display_name",
        "row_name_attr": "display_name",
        "label": "observer",
        "field": "ObserverEmail",
    },
}

_IDENTITY_MODELS = {
    "reviewers": Reviewer,
    "reviewees": Reviewee,
    "observers": Observer,
}


def _identity_holders(
    db: Session, *, session_id: int, exclude: str
) -> dict[str, list[tuple[str, str]]]:
    """``{normalized email: [(roster label, name), ...]}`` for every
    roster but ``exclude``, within one session.

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
        if roster == exclude:
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
        db, session_id=session_id, exclude=kind
    ).get(normalize_email(identifier), [])
    return _first_disagreeing_holder(holders, name)


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
    spec = _IDENTITY_ROSTERS.get(kind)
    if spec is None:
        raise ValueError(
            f"check_cross_table_identity: unknown kind {kind!r}; "
            f"expected one of {sorted(_IDENTITY_ROSTERS)}"
        )

    holders = _identity_holders(db, session_id=session_id, exclude=kind)
    issues: list[ValidationIssue] = []
    for index, row in enumerate(rows, start=1):
        identifier = getattr(row, spec["row_attr"]) or ""
        name = getattr(row, spec["row_name_attr"])
        if not is_comparable_identity(identifier, name):
            continue
        held = _first_disagreeing_holder(
            holders.get(normalize_email(identifier), []), name
        )
        if held is None:
            continue
        holder_label, holder_name = held
        issues.append(
            ValidationIssue(
                severity=Severity.error,
                source=kind,
                row_number=index,
                field=spec["field"],
                message=(
                    f"{spec['field']} '{identifier}' is already used by "
                    f"{holder_label} '{holder_name}' in this session — "
                    f"names must match (got '{name}')."
                ),
            )
        )
    return issues


def existing_reviewer_count(db: Session, session_id: int) -> int:
    return _count(db, Reviewer, session_id)


def existing_reviewee_count(db: Session, session_id: int) -> int:
    return _count(db, Reviewee, session_id)


def existing_observer_count(db: Session, session_id: int) -> int:
    return _count(db, Observer, session_id)


def _count(
    db: Session,
    model: type[Reviewer] | type[Reviewee] | type[Observer],
    session_id: int,
) -> int:
    stmt = select(func.count(model.id)).where(model.session_id == session_id)
    return int(db.execute(stmt).scalar_one())


def save_reviewers(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[ReviewerImportRow],
    filename: str,
    correlation_id: str,
    field_labels_captured: dict[tuple[str, str], str] | None = None,
) -> tuple[int, int]:
    result = _save(
        db,
        session=session,
        user=user,
        model=Reviewer,
        rows=rows,
        event_type="reviewers.imported",
        source_label="reviewers",
        filename=filename,
        correlation_id=correlation_id,
        to_kwargs=_reviewer_to_kwargs,
    )
    # Segment 19C Item 1 — reconcile reviewer friendly labels from the
    # roster header (upsert present, clear absent). ``None`` = a caller
    # that isn't an import; skip untouched.
    if field_labels_captured is not None:
        field_labels.apply_import(
            db,
            session,
            source_type="reviewer",
            captured=field_labels_captured,
            user=user,
            correlation_id=correlation_id,
        )
    return result


def save_reviewees(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[RevieweeImportRow],
    filename: str,
    correlation_id: str,
    field_labels_captured: dict[tuple[str, str], str] | None = None,
) -> tuple[int, int]:
    result = _save(
        db,
        session=session,
        user=user,
        model=Reviewee,
        rows=rows,
        event_type="reviewees.imported",
        source_label="reviewees",
        filename=filename,
        correlation_id=correlation_id,
        to_kwargs=_reviewee_to_kwargs,
    )
    # Lazy-seed display fields for any populated reviewee slots
    # (profile_link / tag_1..3) — see guide/unfinished_business item #14.
    from app.services.instruments import seed_display_fields_from_reviewees

    if seed_display_fields_from_reviewees(db, session):
        db.commit()
    # Segment 19C Item 1 — reconcile reviewee friendly labels from the
    # roster header (upsert present, clear absent).
    if field_labels_captured is not None:
        field_labels.apply_import(
            db,
            session,
            source_type="reviewee",
            captured=field_labels_captured,
            user=user,
            correlation_id=correlation_id,
        )
    return result


def save_observers(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[ObserverImportRow],
    filename: str,
    correlation_id: str,
) -> tuple[int, int]:
    return _save(
        db,
        session=session,
        user=user,
        model=Observer,
        rows=rows,
        event_type="observers.imported",
        source_label="observers",
        filename=filename,
        correlation_id=correlation_id,
        to_kwargs=_observer_to_kwargs,
    )


def _observer_to_kwargs(row: ObserverImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "email": row.email,
        "display_name": row.display_name,
        "tag_1": row.tag_1,
        "status": row.status,
        "cohort_rule": row.cohort_rule,
    }


def _reviewer_to_kwargs(row: ReviewerImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "name": row.name,
        "email": row.email,
        "profile_link": row.profile_link,
        "tag_1": row.tag_1,
        "tag_2": row.tag_2,
        "tag_3": row.tag_3,
        "status": row.status,
    }


def _reviewee_to_kwargs(row: RevieweeImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "name": row.name,
        "email_or_identifier": row.email_or_identifier,
        "profile_link": row.profile_link,
        "tag_1": row.tag_1,
        "tag_2": row.tag_2,
        "tag_3": row.tag_3,
        "status": row.status,
    }


def _save(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    model: Any,
    rows: list[Any],
    event_type: str,
    source_label: str,
    filename: str,
    correlation_id: str,
    to_kwargs: Any,
) -> tuple[int, int]:
    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason=f"{source_label}_imported",
        correlation_id=correlation_id,
    )
    cascaded_assignment_count = _count_assignments(db, session.id)
    # Before the delete below: the FK cascade is the database's, so
    # counting afterwards reads 0. Same mechanism as `_delete_all`.
    cascaded_relationship_count = (
        _count_relationships(db, session.id)
        if roster_bulk.reaches_relationships(model)
        else None
    )

    existing_rows = list(
        db.execute(select(model).where(model.session_id == session.id)).scalars()
    )
    replaced = len(existing_rows)
    _detach_outbox_if_reviewers(db, model=model, session_id=session.id, rows=existing_rows)
    for row in existing_rows:
        db.delete(row)
    db.flush()

    for row in rows:
        db.add(model(**to_kwargs(row, session.id)))
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=f"Imported {len(rows)} {source_label} (replaced {replaced})",
        actor_user_id=user.id,
        session=session,
        payload=audit.counts(
            new=len(rows),
            replaced=replaced,
            cascaded_assignments=cascaded_assignment_count,
            # 19O.5 — a replace deletes every existing row and re-adds,
            # so it takes the relationships with it exactly as
            # `delete-all` does. Counted before `_replace_rows` runs.
            **(
                {"cascaded_relationships": cascaded_relationship_count}
                if cascaded_relationship_count is not None
                else {}
            ),
        ),
        context={"filename": filename} if filename else None,
        correlation_id=correlation_id,
    )

    db.commit()
    log.info(
        "roster imported",
        extra={
            "session_id": session.id,
            "source": source_label,
            "new": len(rows),
            "replaced": replaced,
            "cascaded_assignments": cascaded_assignment_count,
            **(
                {"cascaded_relationships": cascaded_relationship_count}
                if cascaded_relationship_count is not None
                else {}
            ),
            "correlation_id": correlation_id,
        },
    )
    return replaced, len(rows)


def _detach_outbox_if_reviewers(
    db: Session, *, model: Any, session_id: int, rows: list[Any]
) -> None:
    """Clear the outbox FKs before a reviewer delete (19O.3).

    ``_save`` and ``_delete_all`` are generic over ``Reviewer`` /
    ``Reviewee`` / ``Observer``; only reviewers are referenced by
    ``email_outbox``, so only they need the unlink. Gated on the model
    rather than on the ids, because reviewer and reviewee ids overlap
    and an unguarded id list would unlink another table's rows.
    """
    if model is not Reviewer or not rows:
        return
    invitations_service.detach_outbox(
        db,
        session_id=session_id,
        reviewer_ids=[row.id for row in rows],
        reviewers_deleted=True,
    )


def _count_assignments(db: Session, session_id: int) -> int:
    from app.db.models import Assignment

    stmt = select(func.count(Assignment.id)).where(
        Assignment.session_id == session_id
    )
    return int(db.execute(stmt).scalar_one())


def _count_relationships(db: Session, session_id: int) -> int:
    # The service's own counter, not a third copy of the query. Imported
    # inside the function because `relationships` imports this module at
    # its top level — a module-level import here would cycle.
    from app.services import relationships as relationships_service

    return relationships_service.existing_count(db, session_id)


def existing_assignment_count(db: Session, session_id: int) -> int:
    """Used by routes to surface the cascade warning before import."""
    return _count_assignments(db, session_id)


def delete_all_reviewers(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Reviewer,
        event_type="reviewers.deleted_all",
        source_label="reviewers",
        correlation_id=correlation_id,
    )


def delete_all_reviewees(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Reviewee,
        event_type="reviewees.deleted_all",
        source_label="reviewees",
        correlation_id=correlation_id,
    )


def delete_all_observers(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Observer,
        event_type="observers.deleted_all",
        source_label="observers",
        correlation_id=correlation_id,
    )


def _delete_all(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    model: Any,
    event_type: str,
    source_label: str,
    correlation_id: str,
) -> tuple[int, int]:
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason=f"{source_label}_deleted_all",
        correlation_id=correlation_id,
    )
    cascaded = _count_assignments(db, review_session.id)
    # 19O.5 — the whole session's relationships, because emptying either
    # roster empties them all. Taken before the delete: the cascade is
    # `ondelete="CASCADE"` on the FK with no ORM collection on either
    # parent, so a count afterwards always reads 0.
    cascaded_relationships = (
        _count_relationships(db, review_session.id)
        if roster_bulk.reaches_relationships(model)
        else None
    )
    rows = list(
        db.execute(
            select(model).where(model.session_id == review_session.id)
        ).scalars()
    )
    deleted = len(rows)
    _detach_outbox_if_reviewers(
        db, model=model, session_id=review_session.id, rows=rows
    )
    for row in rows:
        db.delete(row)
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=f"Deleted all {deleted} {source_label}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            deleted=deleted,
            cascaded_assignments=cascaded,
            # Omitted, not zero, for observers: nothing references them,
            # so their event keeps the payload it had.
            **(
                {"cascaded_relationships": cascaded_relationships}
                if cascaded_relationships is not None
                else {}
            ),
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    log.info(
        "roster deleted",
        extra={
            "session_id": review_session.id,
            "source": source_label,
            "deleted": deleted,
            "cascaded_assignments": cascaded,
            **(
                {"cascaded_relationships": cascaded_relationships}
                if cascaded_relationships is not None
                else {}
            ),
            "correlation_id": correlation_id,
        },
    )
    return deleted, cascaded
