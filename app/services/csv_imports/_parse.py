"""Reading a roster CSV (the four roster files' parsers): decoding, row
reading, the cell checks and the three ``parse_*_csv``. Segment 20E rung 2,
moved unchanged from ``csv_imports.py``.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.db.base import Base, column_length
from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    SessionFieldLabel,
)
from app.logging_config import get_logger
from app.schemas.imports import (
    ObserverImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.schemas.observer_cohort_rule import CohortRuleSet
from app.schemas.validation import Severity, ValidationIssue
from app.services import field_label_csv
from app.services.email_identity import EMAIL_RE, normalize_email

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

@dataclass
class ParseResult[R]:
    """A parsed roster or relationships file, generic over its row
    type (``ReviewerImportRow`` and its siblings)."""

    rows: list[R]
    issues: list[ValidationIssue]
    # Segment 19C Item 1 — friendly-label overrides captured from the
    # roster header's ``<Column>.<label>`` suffixes, keyed by
    # ``(source_type, source_field)``. Empty for a header with no
    # suffixes; the save step reconciles (upsert present, clear absent).
    field_labels: dict[tuple[str, str], str] = field(
        default_factory=dict[tuple[str, str], str]
    )
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
    label_limit = column_length(SessionFieldLabel, "label")
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
    model: type[Base],
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
    model: type[Base], values: Mapping[str, object], labels: dict[str, str]
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
    values: Mapping[str, object], labels: dict[str, str]
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


def parse_reviewer_csv(content: bytes) -> ParseResult[ReviewerImportRow]:
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
            status_given=bool(_cell(raw, "Status")),
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


def parse_reviewee_csv(content: bytes) -> ParseResult[RevieweeImportRow]:
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
            status_given=bool(_cell(raw, "Status")),
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


def parse_observer_csv(content: bytes) -> ParseResult[ObserverImportRow]:
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
            status_given=bool(_cell(raw, "Status")),
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
