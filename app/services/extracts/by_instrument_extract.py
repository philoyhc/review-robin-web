"""By-instrument wide-format extract — one CSV per instrument.

Backs the Extract data tab's **By instrument** lens (per
``guide/extract_data.md``). Each CSV is a single rubric's
worth of responses, shaped wide for cross-reviewer comparison:

- A **meta header block** (key / value rows) carrying the
  instrument identity, per-response-field type + constraint
  metadata, the assignment count, and the pool / unit-of-review
  / self-review configuration.
- A blank row.
- A **wide data table** with one row per (reviewer × reviewee)
  assignment, columns = identity + tags + one column per
  response field's ``label`` + ``SelfReview`` + ``SavedAt`` +
  ``SubmittedAt``.

Group-scoped instruments collapse the same way the unified
Responses CSV does — one data row per ``(reviewer × group)``
with the composed group identity in ``RevieweeName``.

Distinct from ``serialize_responses_for_instrument`` (long
format, 21 columns × responses) — different lens, different
analyst use case.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
)
from app.services import field_labels
from app.services import responses as responses_service
from app.services.date_formatting import iso_in_zone
from app.services.instruments import decode_band1_state, decode_group_kind
from app.services.instruments._instrument_crud import GROUP_KIND_SENTINEL
from app.services.observer_cohort import CohortIds
from app.services.participant_tokens import ParticipantTokenizer
from app.services.sessions import resolve_session_timezone

__all__ = [
    "by_instrument_filename_slug",
    "fallback_instrument_label",
    "serialize_by_instrument",
]


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #


def fallback_instrument_label(instrument: Instrument, position: int) -> str:
    """The human-facing instrument label for the meta header.

    Uses ``Instrument.short_label`` when set; falls back to the
    ugly positional ``Instrument_{N}`` so the meta row is never
    blank."""
    if instrument.short_label and instrument.short_label.strip():
        return instrument.short_label.strip()
    return f"Instrument_{position}"


def by_instrument_filename_slug(
    instrument: Instrument, position: int, *, used: set[str]
) -> str:
    """A filesystem-safe slug for the per-instrument CSV name.

    Built from the short label (or the ``Instrument_{N}``
    fallback) — keeps alphanumerics + ``-`` + ``_``, collapses
    runs of other characters into a single ``_``. Empty slug
    after sanitisation falls through to ``Instrument_{N}``.
    Collisions resolve by appending ``_{position}`` and mutating
    ``used`` in place so the caller's loop stays one-pass.
    """
    base = fallback_instrument_label(instrument, position)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_")
    if not slug:
        slug = f"Instrument_{position}"
    candidate = slug
    if candidate in used:
        candidate = f"{slug}_{position}"
    used.add(candidate)
    return candidate


# --------------------------------------------------------------------------- #
# Serializer
# --------------------------------------------------------------------------- #


def serialize_by_instrument(
    db: Session,
    review_session: ReviewSession,
    instrument: Instrument,
    *,
    position: int,
    include_metadata: bool = True,
    include_empty_assignments: bool = True,
    cohort_filter: CohortIds | None = None,
    identification: str = "raw",
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for one instrument's wide-format extract.

    Row order:

    1. Meta header (key / value rows) — instrument identity, per
       response-field metadata, assignment count, pool /
       unit-of-review / self-review config. **Skipped entirely
       when ``include_metadata`` is False, along with the
       blank separator row.**
    2. One blank row (skipped with the meta block).
    3. Data table header.
    4. Data rows, one per (reviewer, reviewee_or_group) pair.
       Assignments with no responses are skipped when
       ``include_empty_assignments`` is False.

    Observer-collation parameters (default to operator-side
    behaviour — full identification, no cohort filtering):

    - ``cohort_filter`` — when given, a row is included only
      when **both** ends qualify: reviewer ∈
      ``cohort_filter.reviewer_ids`` AND reviewee ∈
      ``cohort_filter.reviewee_ids``. Single-side rules (e.g.
      ``reviewer.tag1 = math``) still work because the
      materialiser fills the unconstrained side with the
      full roster, so AND collapses to the constrained side
      alone. ``None`` → no cohort filtering.
    - ``identification`` — ``"raw"`` (default; identified
      names + emails + tags) or ``"anonymized"`` (per-row
      reviewer / reviewee names replaced by per-session
      opaque tokens via ``ParticipantTokenizer``; emails and
      tag columns blanked so the only identifier is the
      token). ``"summarized"`` is a no-op at the row level —
      callers handle the no-download path before calling.
    """

    session_zone = resolve_session_timezone(review_session)
    fields = sorted(
        instrument.response_fields, key=lambda f: (f.order, f.id)
    )

    tokenizer = (
        ParticipantTokenizer(review_session)
        if identification == "anonymized"
        else None
    )

    if include_metadata:
        yield from _meta_block(
            db, review_session, instrument, fields, position
        )
        yield ()
    yield from _data_block(
        db,
        review_session,
        instrument,
        fields,
        session_zone,
        include_empty_assignments=include_empty_assignments,
        cohort_filter=cohort_filter,
        tokenizer=tokenizer,
    )


# --------------------------------------------------------------------------- #
# Meta block
# --------------------------------------------------------------------------- #


def _meta_block(
    db: Session,
    review_session: ReviewSession,
    instrument: Instrument,
    fields: list[InstrumentResponseField],
    position: int,
) -> Iterable[tuple[str, ...]]:
    yield ("Instrument", fallback_instrument_label(instrument, position))
    yield ("Description", instrument.description or "")
    for field in fields:
        yield ("Response field", field.label or "")
        yield ("Data Type", _data_type_label(field._inline_data_type))
        yield (
            "Min, Max, Step, List",
            _numeric_cell(field._inline_min),
            _numeric_cell(field._inline_max),
            _numeric_cell(field._inline_step),
            field._inline_list_csv or "",
        )
        yield ("Helptext", field.help_text or "")
    yield ("Number of assignments", str(_count_assignments(db, instrument)))
    pools = _decode_pools(db, instrument, review_session)
    yield ("Pool of reviewers", pools["reviewers"])
    yield ("Pool of reviewees", pools["reviewees"])
    yield ("Unit of review", _unit_of_review_label(instrument, review_session))
    yield ("Self-review excluded", _self_review_excluded_label(db, instrument))


def _data_type_label(value: str | None) -> str:
    return (value or "").strip()


def _numeric_cell(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _count_assignments(db: Session, instrument: Instrument) -> int:
    rows = db.execute(
        select(Assignment.id).where(
            Assignment.instrument_id == instrument.id,
            Assignment.include.is_(True),
        )
    ).all()
    return len(rows)


# --------------------------------------------------------------------------- #
# Pool / unit-of-review / self-review rendering
# --------------------------------------------------------------------------- #


def _decode_pools(
    db: Session, instrument: Instrument, review_session: ReviewSession
) -> dict[str, str]:
    state = decode_band1_state(instrument, db)
    return {
        "reviewers": _render_pool(state["link1"], review_session),
        "reviewees": _render_pool(state["link2"], review_session),
    }


def _render_pool(link_state: dict[str, Any], session: ReviewSession) -> str:
    mode = link_state.get("mode") or "all"
    if mode == "all":
        return "ALL OF"
    rules = link_state.get("rules") or []
    if not rules:
        return "ALL OF"
    combinator = link_state.get("combinator") or "AND"
    parts = [_render_rule(rule, session) for rule in rules]
    return f"{combinator}({', '.join(parts)})"


def _render_rule(rule: dict[str, str], session: ReviewSession) -> str:
    field = rule.get("field") or ""
    op = rule.get("op") or "IS"
    operand_value = rule.get("operand_value") or ""
    operand_tag = rule.get("operand_tag") or ""
    field_label = _prefixed_field_label(field, session)
    if operand_tag:
        operand_label = _prefixed_field_label(operand_tag, session)
        return f"{field_label} {op} {operand_label}"
    return f"{field_label} {op} '{operand_value}'"


def _prefixed_field_label(field_path: str, session: ReviewSession) -> str:
    """``<source_type>.<friendly label>`` rendering for the Pool
    rule rows — preserves the prefix so the row reads
    ``reviewer.Position`` not the ambiguous bare ``Position``."""
    if "." not in field_path:
        return field_path
    source_type, _, _ = field_path.partition(".")
    return f"{source_type}.{_field_friendly_label(field_path, session)}"


def _field_friendly_label(field_path: str, session: ReviewSession) -> str:
    """Resolve ``reviewer.tag_1`` etc. to its friendly label via
    the per-session field-label resolver. Falls back to the raw
    field path when the slot isn't in scope.

    Band 1 rules persist the source-field as ``tag1`` /
    ``tag2`` / ``tag3`` (no underscore — see
    ``_band1.py``'s rule shape docstring) while the field-label
    resolver keys on ``tag_1`` / ``tag_2`` / ``tag_3``. Normalise
    the no-underscore form on lookup so both spellings resolve."""
    if "." not in field_path:
        return field_path
    source_type, _, source_field = field_path.partition(".")
    lookup_field = source_field
    if (
        len(lookup_field) == 4
        and lookup_field.startswith("tag")
        and lookup_field[3].isdigit()
    ):
        lookup_field = f"tag_{lookup_field[3]}"
    try:
        return field_labels.resolve(session, source_type, lookup_field)
    except field_labels.FieldLabelSourceError:
        return source_field


def _unit_of_review_label(
    instrument: Instrument, session: ReviewSession
) -> str:
    if instrument.group_kind is None:
        return "Individual"
    pairs = decode_group_kind(instrument.group_kind)
    if not pairs or instrument.group_kind == GROUP_KIND_SENTINEL:
        return "Group"
    labels = [
        _field_friendly_label(f"{source}.{slot}", session)
        for source, slot in pairs
    ]
    if len(labels) == 1:
        return f"Group by {labels[0]}"
    return f"Group by AND({', '.join(labels)})"


def _self_review_excluded_label(db: Session, instrument: Instrument) -> str:
    if instrument.rule_set_id is None:
        return "No"
    rule_set = db.get(SessionRuleSet, instrument.rule_set_id)
    if rule_set is None:
        return "No"
    return "Yes" if rule_set.exclude_self_reviews else "No"


# --------------------------------------------------------------------------- #
# Data block
# --------------------------------------------------------------------------- #


def _data_block(
    db: Session,
    review_session: ReviewSession,
    instrument: Instrument,
    fields: list[InstrumentResponseField],
    session_zone: object,
    *,
    include_empty_assignments: bool,
    cohort_filter: CohortIds | None = None,
    tokenizer: ParticipantTokenizer | None = None,
) -> Iterable[tuple[str, ...]]:
    yield _header_row(review_session, fields)
    yield from _data_rows(
        db,
        review_session,
        instrument,
        fields,
        session_zone,
        include_empty_assignments=include_empty_assignments,
        cohort_filter=cohort_filter,
        tokenizer=tokenizer,
    )


def _header_row(
    review_session: ReviewSession,
    fields: list[InstrumentResponseField],
) -> tuple[str, ...]:
    rt = _field_friendly_label
    cols: list[str] = [
        "ReviewerName",
        "ReviewerEmail",
        rt("reviewer.tag_1", review_session),
        rt("reviewer.tag_2", review_session),
        rt("reviewer.tag_3", review_session),
        "RevieweeName",
        "RevieweeEmail",
        rt("reviewee.tag_1", review_session),
        rt("reviewee.tag_2", review_session),
        rt("reviewee.tag_3", review_session),
    ]
    cols.extend(field.label or field.field_key for field in fields)
    cols.extend(("SelfReview", "SavedAt", "SubmittedAt"))
    return tuple(cols)


def _data_rows(
    db: Session,
    review_session: ReviewSession,
    instrument: Instrument,
    fields: list[InstrumentResponseField],
    session_zone: object,
    *,
    include_empty_assignments: bool,
    cohort_filter: CohortIds | None = None,
    tokenizer: ParticipantTokenizer | None = None,
) -> Iterable[tuple[str, ...]]:
    assignments = list(
        db.execute(
            select(Assignment)
            .options(
                joinedload(Assignment.reviewer),
                joinedload(Assignment.reviewee),
            )
            .where(
                Assignment.instrument_id == instrument.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    if not assignments:
        return

    if cohort_filter is not None:
        # Row in scope only when BOTH ends conform to the cohort.
        # Single-side rules (e.g. ``reviewer.tag1 = math``) still
        # work: the materialiser fills the unconstrained side
        # with the full roster, so the AND filter collapses to
        # the constrained side alone. Multi-side rules require
        # both ends to match — which is the right reading of
        # "these are the rows the cohort qualifies for".
        # OR was the previous default and let every row through
        # whenever a rule only constrained one side (since the
        # unconstrained side fell back to ALL ids).
        reviewer_ids = cohort_filter.reviewer_ids
        reviewee_ids = cohort_filter.reviewee_ids
        assignments = [
            a
            for a in assignments
            if a.reviewer_id in reviewer_ids
            and a.reviewee_id in reviewee_ids
        ]
        if not assignments:
            return

    group_key_by_assignment, group_identity = _group_index(
        db, review_session, instrument, assignments
    )

    responses_by_assignment = _responses_by_assignment(
        db, instrument, [a.id for a in assignments]
    )

    field_ids = [f.id for f in fields]
    rows: list[tuple[tuple[str, str], tuple[str, ...]]] = []
    seen_group_rows: set[tuple[int, tuple[str, ...]]] = set()
    for assignment in assignments:
        assignment_responses = responses_by_assignment.get(
            assignment.id, {}
        )
        if not include_empty_assignments and not assignment_responses:
            continue
        group_key = group_key_by_assignment.get(assignment.id)
        if group_key is not None:
            dedupe = (assignment.reviewer_id, group_key)
            if dedupe in seen_group_rows:
                continue
            seen_group_rows.add(dedupe)
        row = _assignment_row(
            assignment=assignment,
            instrument=instrument,
            field_ids=field_ids,
            responses=assignment_responses,
            group_key=group_key,
            group_identity=group_identity,
            session_zone=session_zone,
            tokenizer=tokenizer,
        )
        sort_key = (row[5], row[0])  # composed reviewee name, then reviewer
        rows.append((sort_key, row))

    rows.sort(key=lambda pair: pair[0])
    for _, row in rows:
        yield row


def _assignment_row(
    *,
    assignment: Assignment,
    instrument: Instrument,
    field_ids: list[int],
    responses: dict[int, Response],
    group_key: tuple[str, ...] | None,
    group_identity: dict[tuple[int, tuple[str, ...]], str],
    session_zone: object,
    tokenizer: ParticipantTokenizer | None = None,
) -> tuple[str, ...]:
    reviewer: Reviewer = assignment.reviewer
    reviewee: Reviewee = assignment.reviewee

    # Identification block: ``tokenizer`` only set for Anonymized
    # observer downloads. Names ride through as opaque per-session
    # tokens; emails + tag columns blank so the only identifier is
    # the token. Operator extracts (``tokenizer is None``) carry
    # the raw fields.
    if tokenizer is not None:
        reviewer_name = tokenizer.token("reviewer", reviewer.id)
        reviewer_email = ""
        reviewer_tags = ("", "", "")
    else:
        reviewer_name = reviewer.name
        reviewer_email = reviewer.email
        reviewer_tags = (
            reviewer.tag_1 or "",
            reviewer.tag_2 or "",
            reviewer.tag_3 or "",
        )

    if group_key is not None:
        # Grouped row: the "reviewee" is a group. Blank the
        # group label under Anonymized so the operator-set
        # tag value (e.g. ``"Tutorial-A"``) doesn't leak.
        reviewee_name = (
            ""
            if tokenizer is not None
            else group_identity.get(
                (instrument.id, group_key), "(group)"
            )
        )
        reviewee_email = ""
        reviewee_tags = ("", "", "")
    elif tokenizer is not None:
        reviewee_name = tokenizer.token("reviewee", reviewee.id)
        reviewee_email = ""
        reviewee_tags = ("", "", "")
    else:
        reviewee_name = reviewee.name
        reviewee_email = reviewee.email_or_identifier
        reviewee_tags = (
            reviewee.tag_1 or "",
            reviewee.tag_2 or "",
            reviewee.tag_3 or "",
        )
    # Read the canonical column. Pre-consolidation this branch
    # hardcoded ``FALSE`` for group-scoped rows, silently
    # mislabelling every self-review group. The whole-group rule
    # baked into ``Assignment.is_self_review`` (PR 1/2 of
    # ``guide/self_review_consolidate.md``) is the source of truth
    # for every flavour.
    self_review = "TRUE" if assignment.is_self_review else "FALSE"

    values: list[str] = []
    saved_at = None
    submitted_at = None
    for field_id in field_ids:
        response = responses.get(field_id)
        if response is None:
            values.append("")
            continue
        values.append(response.value if response.value is not None else "")
        if saved_at is None or response.saved_at > saved_at:
            saved_at = response.saved_at
        if response.submitted_at is not None and (
            submitted_at is None or response.submitted_at > submitted_at
        ):
            submitted_at = response.submitted_at

    return (
        reviewer_name,
        reviewer_email,
        reviewer_tags[0],
        reviewer_tags[1],
        reviewer_tags[2],
        reviewee_name,
        reviewee_email,
        reviewee_tags[0],
        reviewee_tags[1],
        reviewee_tags[2],
        *values,
        self_review,
        iso_in_zone(saved_at, session_zone) if saved_at else "",
        iso_in_zone(submitted_at, session_zone) if submitted_at else "",
    )


def _responses_by_assignment(
    db: Session,
    instrument: Instrument,
    assignment_ids: list[int],
) -> dict[int, dict[int, Response]]:
    """For each assignment, the latest ``Response`` row per
    response-field. Same field can have multiple ``Response``
    rows when the reviewer re-saved — pick the highest version."""
    if not assignment_ids:
        return {}
    rows = list(
        db.execute(
            select(Response)
            .join(
                InstrumentResponseField,
                Response.response_field_id == InstrumentResponseField.id,
            )
            .where(
                Response.assignment_id.in_(assignment_ids),
                InstrumentResponseField.instrument_id == instrument.id,
            )
        ).scalars()
    )
    by_assignment: dict[int, dict[int, Response]] = {}
    for response in rows:
        slot = by_assignment.setdefault(response.assignment_id, {})
        existing = slot.get(response.response_field_id)
        if existing is None or response.version > existing.version:
            slot[response.response_field_id] = response
    return by_assignment


def _group_index(
    db: Session,
    review_session: ReviewSession,
    instrument: Instrument,
    assignments: list[Assignment],
) -> tuple[
    dict[int, tuple[str, ...]],
    dict[tuple[int, tuple[str, ...]], str],
]:
    if instrument.group_kind is None:
        return {}, {}
    key_by_assignment = responses_service.group_keys(
        db, assignments=assignments, session_id=review_session.id
    )
    if not key_by_assignment:
        return {}, {}
    members: dict[tuple[int, tuple[str, ...]], set[str]] = {}
    for assignment in assignments:
        group_key = key_by_assignment.get(assignment.id)
        if group_key is None:
            continue
        members.setdefault(
            (instrument.id, group_key), set()
        ).add(assignment.reviewee.name)
    identity = {
        (instr_id, group_key): _compose_group_identity(group_key, names)
        for (instr_id, group_key), names in members.items()
    }
    return key_by_assignment, identity


def _compose_group_identity(
    group_key: tuple[str, ...], member_names: set[str]
) -> str:
    """Single-cell group identity for the wide row. Mirrors the
    unified Responses CSV's group rendering shape (no member-name
    expansion — this lens is per-instrument, not the unified
    cross-instrument view)."""
    tag_part = ", ".join(v for v in group_key if v)
    return tag_part or "(group)"
