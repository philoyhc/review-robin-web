from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionFieldLabel,
    User,
)
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
from app.services import directory_accounts, roster_bulk, unit_of_work
from app.services import invitations as invitations_service
from app.services import session_lifecycle as lifecycle
from app.services.email_identity import EMAIL_RE, normalize_email, normalize_object_id

log = get_logger(__name__)

MAX_BYTES = 1 * 1024 * 1024
MAX_ROWS = 5000
#: Why a roster file holding a NUL character is refused (findings S7). The
#: Settings import refuses such a row with its own row-level wording
#: (``session_config_io.split_rows``).
NUL_MESSAGE = "File contains a NUL character, which cannot be stored"

#: The columns each roster CSV reads (``spec/csv_contracts.md`` §1),
#: keyed by the ``source`` its parser passes. A header naming one of them
#: twice refuses the file, since ``DictReader`` would keep one copy and
#: drop the other (findings S9); any other column, another file's
#: included, is ignored, so two of it lose nothing.
_ROSTER_COLUMNS: dict[str, frozenset[str]] = {
    "reviewers": frozenset(
        {"ReviewerName", "ReviewerEmail", "ReviewerTag1", "ReviewerTag2",
         "ReviewerTag3", "ProfileLink", "PhotoLink", "Status"}
    ),
    "reviewees": frozenset(
        {"RevieweeName", "RevieweeEmail", "RevieweeTag1", "RevieweeTag2",
         "RevieweeTag3", "ProfileLink", "PhotoLink", "Status"}
    ),
    "observers": frozenset(
        {"ObserverName", "ObserverEmail", "ObserverTag1", "Status", "CohortRule"}
    ),
    "relationships": frozenset(
        {"ReviewerEmail", "RevieweeEmail", "PairContextTag1", "PairContextTag2",
         "PairContextTag3", "Status"}
    ),
}


@dataclass(frozen=True)
class DirectoryCheck:
    """An import's directory check (segment 21F): the accounts its
    addresses resolved to, keyed by lookup key, and the counts its audit
    event records."""

    accounts: dict[str, directory_accounts.Account]
    counts: dict[str, int]



def directory_check(directory: Any, addresses: list[str | None]) -> DirectoryCheck:
    """Resolve an import's addresses through ``directory`` (``None``:
    nothing checked) for `_save` to store and count (segment 21F)."""
    return directory_checks(directory, [addresses])[0]


def directory_checks(
    directory: Any, rosters: list[list[str | None]]
) -> list[DirectoryCheck]:
    """`directory_check` for several rosters saved by one request (Quick
    Setup, rehydrate): one lookup under one budget, so the request stays
    inside the front end's limit however many rosters it carries (Codex,
    #3430). Each roster is counted over its own addresses."""
    outcomes = directory_accounts.resolve(
        directory, [address for addresses in rosters for address in addresses]
    )
    found = directory_accounts.accounts(outcomes)
    return [
        DirectoryCheck(
            accounts=found,
            counts=directory_accounts.counts(
                outcomes, addresses, checked=directory is not None
            ),
        )
        for addresses in rosters
    ]

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
    # Segment 19Z: the header's canonical columns, so a merge can tell an
    # absent Status column (keep each row's status) from one the parser
    # defaulted to ``active``.
    columns: frozenset[str] = frozenset()

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
    if "\x00" in text:
        # Valid UTF-8 and stored by SQLite, but Postgres refuses a NUL in
        # a text column at flush: a 500, not a report (findings S7).
        log.warning(
            "csv import rejected",
            extra={"source": source, "reason": "nul_character"},
        )
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message=NUL_MESSAGE,
        )
    return text, None


def csv_error_message(exc: csv.Error) -> str:
    """The operator-facing text for a file the ``csv`` module refuses.

    Chiefly a cell over the parser's 131,072-character field limit,
    which a file under ``MAX_BYTES`` can still carry; every upload path
    that reads a CSV reports it with this rather than answering 500
    (findings D11, Dc8).
    """
    if "field larger than field limit" in str(exc):
        return f"A cell is longer than {csv.field_size_limit():,} characters"
    return f"CSV could not be read: {exc}"


def _unreadable_issue(source: str, exc: csv.Error) -> ValidationIssue:
    """A blocking issue for a file the ``csv`` module refuses to parse."""
    return ValidationIssue(
        severity=Severity.error,
        source=source,
        message=csv_error_message(exc),
    )


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
    try:
        raw_fieldnames = reader.fieldnames
    except csv.Error as exc:
        return None, [], {}, _unreadable_issue(source, exc)
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
    # Two headers naming one column (`ReviewerTag1` and
    # `ReviewerTag1.Tutor`, or one name twice) would leave `DictReader`
    # keeping the last and dropping the other silently (findings S9). Only
    # a column this file reads counts; any other is ignored.
    read = _ROSTER_COLUMNS[source]
    seen: set[str] = set()
    for column in canonical:
        if column in read and column in seen:
            return (
                None,
                canonical,
                captured,
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    field=column,
                    message=f"The {column} column appears more than once",
                ),
            )
        seen.add(column)
    label_limit = SessionFieldLabel.__table__.columns["label"].type.length
    for slot, label in captured.items():
        if len(label) > label_limit:
            column = field_label_csv.column_for_slot(slot)
            # The friendly label rides into `session_field_labels.label`;
            # refused here, not as a Postgres 500 (findings D11).
            return (
                None,
                canonical,
                captured,
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    field=column,
                    message=(
                        f"The label on the {column} header is "
                        f"{len(label)} characters; at most {label_limit} fit"
                    ),
                ),
            )
    reader.fieldnames = canonical
    try:
        rows = list(reader)
    except csv.Error as exc:
        return None, canonical, captured, _unreadable_issue(source, exc)
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


def cell_length_issues(
    row: object,
    model: type,
    headers: dict[str, str],
    *,
    source: str,
    row_number: int,
) -> list[ValidationIssue]:
    """One blocking issue per cell longer than the column it lands in.

    ``headers`` maps each row attribute to the CSV column it came from.
    The limit is read from ``model``'s declared ``String(n)``, so it
    cannot drift from the schema. SQLite stores an over-long value and
    Postgres refuses it at flush, a 500 rather than a report (findings
    D11); the Settings import already checks the same way."""
    issues: list[ValidationIssue] = []
    for attr, header in headers.items():
        value = getattr(row, attr)
        column = model.__table__.columns.get(attr)
        limit = getattr(column.type, "length", None) if column is not None else None
        if isinstance(value, str) and limit is not None and len(value) > limit:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=row_number,
                    field=header,
                    message=(
                        f"{header} is {len(value)} characters; "
                        f"at most {limit} fit"
                    ),
                    problem=f"{header} is longer than {limit} characters",
                )
            )
    return issues


def over_long_field_message(
    model: type, values: dict[str, object], labels: dict[str, str]
) -> str | None:
    """The first value longer than its ``model`` column, as an
    operator-facing sentence, or ``None``.

    The single-row editors' counterpart of :func:`cell_length_issues`:
    the Add / Edit forms write the same columns the CSVs do, and
    Postgres refuses an over-long value at flush (findings Cc3).
    ``labels`` names each attribute as the form does; an attribute it
    omits is named as itself."""
    for attr, value in values.items():
        column = model.__table__.columns.get(attr)
        limit = getattr(column.type, "length", None) if column is not None else None
        if isinstance(value, str) and limit is not None and len(value) > limit:
            return (
                f"{labels.get(attr, attr)} is {len(value)} characters; "
                f"at most {limit} fit."
            )
    return None


def tag_comma_issues(
    row: object,
    headers: dict[str, str],
    *,
    source: str,
    row_number: int,
) -> list[ValidationIssue]:
    """One blocking issue per tag cell holding a comma (findings Gc1,
    ruled 2026-10-07). A group instrument names a group by its tag
    values joined with ", ", so a comma inside one would let two groups
    render the same name. ``headers`` maps each tag attribute to its CSV
    column."""
    return [
        ValidationIssue(
            severity=Severity.error,
            source=source,
            row_number=row_number,
            field=header,
            message=f"{header} may not contain a comma",
            problem=f"{header} contains a comma",
        )
        for attr, header in headers.items()
        if "," in (getattr(row, attr) or "")
    ]


def comma_tag_message(
    values: dict[str, object], labels: dict[str, str]
) -> str | None:
    """The first tag value holding a comma, as an operator-facing
    sentence, or ``None``: the single-row editors' counterpart of
    :func:`tag_comma_issues`. Only ``tag_*`` attributes are checked."""
    for attr, value in values.items():
        if attr.startswith("tag_") and isinstance(value, str) and "," in value:
            return f"{labels.get(attr, attr)} may not contain a comma."
    return None


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    return value.strip() if value else ""


def _none_if_blank(row: dict[str, str], key: str) -> str | None:
    value = _cell(row, key)
    return value or None


def _profile_link_header(row: dict[str, str]) -> str:
    """The column ``_profile_link`` read: ``ProfileLink``, or the legacy
    ``PhotoLink`` a file without one still carries, so an issue names a
    column the operator's file has."""
    return "ProfileLink" if _none_if_blank(row, "ProfileLink") else (
        "PhotoLink" if _none_if_blank(row, "PhotoLink") else "ProfileLink"
    )


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
            problem="Status is not active or inactive",
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
            problem=f"{field} is not a valid email address",
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
                    problem="ReviewerName is blank",
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
                    problem="ReviewerEmail is blank",
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
                problem = "ReviewerEmail appears on more than one row"
            else:
                problem = "ReviewerEmail is used with different names"
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
                    problem=problem,
                )
            )
            continue
        status = _parse_status(raw, source=source, row_number=index)
        if isinstance(status, ValidationIssue):
            issues.append(status)
            continue
        row = ReviewerImportRow(
            name=name,
            email=email,
            profile_link=_profile_link(raw),
            tag_1=_none_if_blank(raw, "ReviewerTag1"),
            tag_2=_none_if_blank(raw, "ReviewerTag2"),
            tag_3=_none_if_blank(raw, "ReviewerTag3"),
            status=status,
        )
        length_issues = cell_length_issues(
            row,
            Reviewer,
            {
                "name": "ReviewerName",
                "email": "ReviewerEmail",
                "profile_link": _profile_link_header(raw),
                "tag_1": "ReviewerTag1",
                "tag_2": "ReviewerTag2",
                "tag_3": "ReviewerTag3",
            },
            source=source,
            row_number=index,
        )
        length_issues += tag_comma_issues(
            row,
            {"tag_1": "ReviewerTag1", "tag_2": "ReviewerTag2", "tag_3": "ReviewerTag3"},
            source=source,
            row_number=index,
        )
        if length_issues:
            issues.extend(length_issues)
            continue
        # Reserved only on a row that parsed, so a later row is never
        # told it duplicates one the caller cannot see (as
        # `parse_relationship_csv` does).
        seen_emails[normalize_email(email)] = (index, name)
        parsed.append(row)

    return ParseResult(
        rows=parsed, issues=issues, field_labels=captured_labels, columns=frozenset(fieldnames)
    )


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
                    problem="RevieweeName is blank",
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
                    problem="RevieweeEmail is blank",
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
                problem = "RevieweeEmail appears on more than one row"
            else:
                problem = "RevieweeEmail is used with different names"
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
                    problem=problem,
                )
            )
            continue
        status = _parse_status(raw, source=source, row_number=index)
        if isinstance(status, ValidationIssue):
            issues.append(status)
            continue
        row = RevieweeImportRow(
            name=name,
            email_or_identifier=identifier,
            profile_link=_profile_link(raw),
            tag_1=_none_if_blank(raw, "RevieweeTag1"),
            tag_2=_none_if_blank(raw, "RevieweeTag2"),
            tag_3=_none_if_blank(raw, "RevieweeTag3"),
            status=status,
        )
        length_issues = cell_length_issues(
            row,
            Reviewee,
            {
                "name": "RevieweeName",
                "email_or_identifier": "RevieweeEmail",
                "profile_link": _profile_link_header(raw),
                "tag_1": "RevieweeTag1",
                "tag_2": "RevieweeTag2",
                "tag_3": "RevieweeTag3",
            },
            source=source,
            row_number=index,
        )
        length_issues += tag_comma_issues(
            row,
            {"tag_1": "RevieweeTag1", "tag_2": "RevieweeTag2", "tag_3": "RevieweeTag3"},
            source=source,
            row_number=index,
        )
        if length_issues:
            issues.extend(length_issues)
            continue
        seen_identifiers[normalize_email(identifier)] = (index, name)
        parsed.append(row)

    return ParseResult(
        rows=parsed, issues=issues, field_labels=captured_labels, columns=frozenset(fieldnames)
    )


def parse_observer_csv(content: bytes) -> ParseResult:
    """Parse an Observers CSV upload. Required column:
    ``ObserverEmail``. Optional columns: ``ObserverName``,
    ``ObserverTag1``, ``Status``, ``CohortRule``. Other columns are
    ignored. ``Status`` follows the roster rule in ``_parse_status``:
    blank is ``active``, ``active`` / ``inactive`` in any case are
    accepted, anything else is a blocking error.

    Observers carry a single ``tag_1`` (not three) per the model
    note in ``app/db/models/observer.py``. Email is the auth-
    bearing identity and is required + strict-shape-validated;
    duplicate emails within the same CSV are blocking errors.

    A ``CohortRule`` cell (compact JSON) round-trips the
    per-observer cohort match rule. It's re-validated
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
                    problem="ObserverEmail is blank",
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
                    problem="ObserverEmail appears on more than one row",
                )
            )
            continue

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
                        problem="CohortRule is not valid JSON",
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
                        problem="CohortRule is not a valid cohort rule",
                    )
                )
                continue
            cohort_rule = ruleset.model_dump(mode="json")

        row = ObserverImportRow(
            email=email,
            display_name=_none_if_blank(raw, "ObserverName"),
            tag_1=_none_if_blank(raw, "ObserverTag1"),
            status=status,
            cohort_rule=cohort_rule,
        )
        length_issues = cell_length_issues(
            row,
            Observer,
            {
                "email": "ObserverEmail",
                "display_name": "ObserverName",
                "tag_1": "ObserverTag1",
            },
            source=source,
            row_number=index,
        )
        length_issues += tag_comma_issues(
            row,
            {"tag_1": "ObserverTag1"},
            source=source,
            row_number=index,
        )
        if length_issues:
            issues.extend(length_issues)
            continue
        seen_emails[normalize_email(email)] = index
        parsed.append(row)

    return ParseResult(rows=parsed, issues=issues, columns=frozenset(fieldnames))


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
    held = list(
        db.execute(select(model).where(model.session_id == session_id)).scalars()
    )
    addresses = {
        normalize_email(getattr(row, spec["model_attr"])) for row in held
    } - {""}
    accounts = {
        normalize_object_id(row.directory_object_id)
        for row in held
        if row.directory_object_id
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
                        f"{spec['field']} '{address}' is the same directory "
                        f"account as row {held}."
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
    status_given: bool,
    correlation_id: str,
) -> tuple[int, int, int, set[str]]:
    """Merge ``rows`` into ``existing`` (segment 19Z, upsert amendment).
    Returns ``(added, updated, unchanged, changed_fields)``.

    A row matches an existing one by its folded address, or by the
    directory account its address resolved to; the lowest id answers a
    roster already holding two. A matched row takes every non-blank
    cell, Status only when the file has the column, and keeps its
    address; an unbound row whose own address resolved is bound. Each
    updated row writes its ``*.updated`` event. Any other row is added."""
    spec = _IDENTITY_ROSTERS[kind]
    by_address: dict[str, Any] = {}
    by_account: dict[str, Any] = {}
    for held in sorted(existing, key=lambda r: r.id):
        by_address.setdefault(normalize_email(getattr(held, spec["model_attr"])), held)
        if held.directory_object_id:
            by_account.setdefault(normalize_object_id(held.directory_object_id), held)
    added = updated = unchanged = 0
    changed_fields: set[str] = set()
    for row in rows:
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
            if name == "status" and not status_given:
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
        changed_fields.update(changes)
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
    return added, updated, unchanged, changed_fields


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
        db, session_id=session_id, exclude=frozenset({kind})
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
        db, session_id=session_id, exclude=frozenset(incoming)
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
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    # One commit for the roster and its labels, so the lock taken by
    # the gate holds to the end and a refusal can't follow a committed
    # replace (findings Bc4).
    with unit_of_work.atomic(db):
        lifecycle.require_editable(db, session)
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
            directory=directory,
            append=append,
            merge=merge,
            columns=columns,
        )
        # Segment 19C Item 1 — reconcile reviewer friendly labels from
        # the roster header (upsert present, clear absent). ``None`` = a
        # caller that isn't an import; skip untouched.
        if field_labels_captured is not None:
            field_labels.apply_import(
                db,
                session,
                source_type="reviewer",
                captured=field_labels_captured,
                user=user,
                correlation_id=correlation_id,
                clear_absent=not (append or merge),
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
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
    acknowledged_loss: int | None = None,
) -> tuple[int, int]:
    from app.services import responses as responses_service
    from app.services.instruments import seed_display_fields_from_reviewees

    # One commit for the roster, its display fields and its labels, as
    # in ``save_reviewers`` (findings Bc4).
    with unit_of_work.atomic(db):
        lifecycle.require_editable(db, session)
        # A merge can move a reviewee between groups by a tag change
        # (segment 19Z): snapshot the partitions, and after the save ask
        # before clearing any group that gained a member, as the
        # reviewee row editor does.
        groups_before = (
            responses_service.snapshot_group_partitions(
                db,
                session_id=session.id,
                instrument_ids=responses_service.session_group_instrument_ids(
                    db, session_id=session.id, source_type="reviewee"
                ),
            )
            if merge
            else {}
        )
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
            directory=directory,
            append=append,
            merge=merge,
            columns=columns,
        )
        if merge:
            from app.services.assignments import recompute_self_review_classification

            responses_service.clear_changed_groups(
                db,
                session_id=session.id,
                before=groups_before,
                acknowledged_loss=acknowledged_loss,
            )
            recompute_self_review_classification(db, session_id=session.id)
        # Lazy-seed display fields for any populated reviewee slots
        # (profile_link / tag_1..3) — see guide/unfinished_business item #14.
        seed_display_fields_from_reviewees(db, session)
        # Segment 19C Item 1 — reconcile reviewee friendly labels from
        # the roster header (upsert present, clear absent).
        if field_labels_captured is not None:
            field_labels.apply_import(
                db,
                session,
                source_type="reviewee",
                captured=field_labels_captured,
                user=user,
                correlation_id=correlation_id,
                clear_absent=not (append or merge),
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
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    lifecycle.require_not_archived(db, session)
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
        directory=directory,
        append=append,
        merge=merge,
        columns=columns,
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
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    """Replace ``model``'s roster with ``rows``, or with ``append`` add
    them and keep every row, assignment and response already there
    (segment 19Z). Returns ``(replaced, new)``; an append replaces 0.

    With ``merge`` (the upsert amendment) a row already on the roster
    is updated and any other added (`_merge_rows`); ``new`` counts the
    rows added. Two file rows on one directory account refuse it
    (`merge_conflicts`), before anything is written.

    An append is refused, before anything is written, by any row
    `append_conflicts` names (`AppendConflict`). It runs here, under
    the session lock the caller holds, so a row added since the
    caller's own check is caught too."""
    if append:
        conflicts = append_conflicts(
            db, session_id=session.id, kind=source_label, rows=rows, directory=directory
        )
        if conflicts:
            raise AppendConflict(conflicts)
    if merge:
        conflicts = merge_conflicts(kind=source_label, rows=rows, directory=directory)
        if conflicts:
            raise AppendConflict(conflicts)
    keeps = append or merge
    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason=f"{source_label}_imported",
        correlation_id=correlation_id,
    )
    # Nothing in `assignments` references an observer, so their events
    # omit the key rather than count rows they never delete (findings
    # S10). The same omitted-not-zero rule as `cascaded_relationships`.
    # An append deletes nothing, so it cascades nothing: the counts are
    # omitted, not zeroed.
    cascaded_assignment_count = (
        _count_assignments(db, session.id)
        if _reaches_assignments(model) and not keeps
        else None
    )
    # Before the delete below: the FK cascade is the database's, so
    # counting afterwards reads 0. Same mechanism as `_delete_all`.
    cascaded_relationship_count = (
        _count_relationships(db, session.id)
        if roster_bulk.reaches_relationships(model) and not keeps
        else None
    )

    existing_rows = list(
        db.execute(select(model).where(model.session_id == session.id)).scalars()
    )
    if keeps:
        replaced, kept = 0, len(existing_rows)
    else:
        replaced, kept = len(existing_rows), 0
        _detach_outbox_if_reviewers(db, model=model, session_id=session.id, rows=existing_rows)
        for row in existing_rows:
            db.delete(row)
        db.flush()

    merged = (
        _merge_rows(
            db,
            session=session,
            user=user,
            model=model,
            kind=source_label,
            existing=existing_rows,
            rows=rows,
            to_kwargs=to_kwargs,
            directory=directory,
            status_given="Status" in columns,
            correlation_id=correlation_id,
        )
        if merge
        else None
    )
    for row in rows if merged is None else []:
        kwargs = to_kwargs(row, session.id)
        if directory is not None:
            # Segment 21F: the account the row's address resolved to, or
            # none (unresolved, not checked, or not an address).
            address = kwargs.get("email") or kwargs.get("email_or_identifier")
            kwargs.update(
                directory_accounts.columns(
                    directory.accounts.get(directory_accounts.key(address) or "")
                )
            )
        db.add(model(**kwargs))
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Merged {source_label}: {merged[0]} added, {merged[1]} updated"
            if merged is not None
            else f"Appended {len(rows)} {source_label} (kept {kept})"
            if append
            else f"Imported {len(rows)} {source_label} (replaced {replaced})"
        ),
        actor_user_id=user.id,
        session=session,
        payload=audit.counts(
            **(
                {"new": merged[0], "updated": merged[1], "unchanged": merged[2]}
                if merged is not None
                else {"new": len(rows), "kept": kept}
                if append
                else {"new": len(rows), "replaced": replaced}
            ),
            **(
                {"cascaded_assignments": cascaded_assignment_count}
                if cascaded_assignment_count is not None
                else {}
            ),
            # 19O.5 — a replace deletes every existing row and re-adds,
            # so it takes the relationships with it exactly as
            # `delete-all` does. Counted before `_replace_rows` runs.
            **(
                {"cascaded_relationships": cascaded_relationship_count}
                if cascaded_relationship_count is not None
                else {}
            ),
            # Segment 21F: what the directory check came to, over the
            # file's distinct addresses. Omitted when the caller ran none.
            **(directory.counts if directory is not None else {}),
        ),
        context=(
            {
                **({"filename": filename} if filename else {}),
                **({"mode": "append"} if append else {}),
                **({"mode": "upsert"} if merge else {}),
            }
            or None
        ),
        correlation_id=correlation_id,
    )

    unit_of_work.commit(db)
    unit_of_work.after_commit(
        db,
        lambda: log.info(
            "roster imported",
            extra={
                "session_id": session.id,
                "source": source_label,
                "new": len(rows),
                "replaced": replaced,
                **({"mode": "append", "kept": kept} if append else {}),
                **({"mode": "upsert"} if merge else {}),
                **(
                    {"cascaded_assignments": cascaded_assignment_count}
                    if cascaded_assignment_count is not None
                    else {}
                ),
                **(
                    {"cascaded_relationships": cascaded_relationship_count}
                    if cascaded_relationship_count is not None
                    else {}
                ),
                "correlation_id": correlation_id,
            },
        ),
    )
    return replaced, (merged[0] if merged is not None else len(rows))


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


def _reaches_assignments(model: type) -> bool:
    """Whether deleting a ``model`` row deletes assignments: a reviewer
    or reviewee row does, through the foreign-key cascade; an observer
    row does not."""
    return model is Reviewer or model is Reviewee


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
    lifecycle.require_editable(db, review_session)
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
    lifecycle.require_editable(db, review_session)
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
    lifecycle.require_not_archived(db, review_session)
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
    # Omitted for observers, as in `_save` (findings S10).
    cascaded_assignments = (
        _count_assignments(db, review_session.id)
        if _reaches_assignments(model)
        else None
    )
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
            **(
                {"cascaded_assignments": cascaded_assignments}
                if cascaded_assignments is not None
                else {}
            ),
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
            **(
                {"cascaded_assignments": cascaded_assignments}
                if cascaded_assignments is not None
                else {}
            ),
            **(
                {"cascaded_relationships": cascaded_relationships}
                if cascaded_relationships is not None
                else {}
            ),
            "correlation_id": correlation_id,
        },
    )
    return deleted, cascaded_assignments or 0
