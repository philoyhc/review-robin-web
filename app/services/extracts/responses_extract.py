"""Responses extract — the analysis-facing per-session CSV.

Streams the session's reviewer responses as a CSV designed for
**downstream analysis** (Excel pivots, pandas groupby, BI tools)
by an external analyst — *not* the app itself. The file has two
parts:

1. A **preamble** — one block per instrument: a row carrying the
   instrument's positional name (``instrument_1``, ``instrument_2``,
   …), then one ``FieldKey, HelpText`` row per response field. The
   preamble doubles as a field dictionary, keeping the per-field
   help text out of the (denormalised) data table where it would
   repeat on every row. A blank row separates it from the table.
2. The **data table** — :data:`HEADER` then one row per
   ``Response``: denormalised reviewer / reviewee identity + tags,
   instrument + field context, and the response-type name, so the
   table is readable without joining against the other extracts.

The instrument name — in both the preamble and the table's
``InstrumentName`` column — is the positional id ``instrument_{n}``
(by instrument order); the operator's typed name is intentionally
not exported (not analysis-relevant). An analyst joins a help text
to its data column via the shared ``FieldKey``.

No import counterpart. Operators don't upload responses; only
reviewers create them via the response surface.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service
from app.services.assignments import is_self_review
from app.services.date_formatting import iso_in_zone
from app.services.sessions import resolve_session_timezone

__all__ = ["HEADER", "serialize_responses"]


# 21-column header. Pinned in unit tests so a rename here fails
# loud and forces analysts of the file to update their pipelines
# deliberately.
HEADER: tuple[str, ...] = (
    # Reviewer identity + tags (5 cols).
    "ReviewerName",
    "ReviewerEmail",
    "ReviewerTag1",
    "ReviewerTag2",
    "ReviewerTag3",
    # Reviewee identity + tags (5 cols). Note ``RevieweeEmail``
    # mirrors the rosters CSV header even though the underlying
    # column is ``Reviewee.email_or_identifier``. For a collapsed
    # group-scoped row these carry the composed group identity in
    # ``RevieweeName`` with the other four left empty.
    "RevieweeName",
    "RevieweeEmail",
    "RevieweeTag1",
    "RevieweeTag2",
    "RevieweeTag3",
    # Instrument context (2 cols). ``InstrumentName`` is the
    # positional id ``instrument_{n}``; it maps to the matching
    # preamble block.
    "InstrumentName",
    "InstrumentShortLabel",
    # Field context (3 cols).
    "FieldKey",
    "FieldLabel",
    "ResponseType",
    # Value (1 col). Empty cell ⇒ reviewer cleared the field.
    "Value",
    # Self-review flag (1 col, PR 4a). Computed from
    # ``is_self_review(reviewer, reviewee)`` — case-insensitive
    # match of ``reviewer.email`` against
    # ``reviewee.email_or_identifier`` when the latter is an
    # email; ``FALSE`` for non-email reviewee identifiers, and
    # ``FALSE`` on a collapsed group-scoped row (a group response
    # is not a per-person self-review). Uppercase ``TRUE`` /
    # ``FALSE`` for analyst-tool friendliness (Excel idiom).
    "SelfReview",
    # Lifecycle (3 cols). ``SubmittedAt`` empty ⇒
    # saved-but-not-submitted draft.
    "SavedAt",
    "SubmittedAt",
    "Version",
    # Instrument flavour (1 col, Segment 13C / 18D Part 3). Derived
    # ``per-reviewee`` / ``group-scoped``. Appended (not grouped
    # with the other instrument columns) so the column indices of
    # the original 20-column file stay stable for existing analyst
    # pipelines.
    "InstrumentFlavour",
)


def _name_included_instruments(
    db: Session, instrument_ids: set[int]
) -> set[int]:
    """Group-scoped instruments whose RevieweeName Display Field is
    Included — their export identity carries the member-name list."""
    if not instrument_ids:
        return set()
    rows = db.execute(
        select(InstrumentDisplayField.instrument_id).where(
            InstrumentDisplayField.instrument_id.in_(instrument_ids),
            InstrumentDisplayField.source_type == "reviewee",
            InstrumentDisplayField.source_field == "name",
            InstrumentDisplayField.visible.is_(True),
        )
    ).scalars()
    return set(rows)


def _compose_group_identity(
    group_key: tuple[str, ...],
    member_names: list[str],
    *,
    with_names: bool,
) -> str:
    """The single-cell ``RevieweeName`` value for a collapsed group
    row: the boundary tag values, plus the full member-name list
    when the RevieweeName Display Field is Included."""
    tag_part = ", ".join(v for v in group_key if v)
    if with_names and member_names:
        members = ", ".join(member_names)
        return f"{tag_part} ({members})" if tag_part else members
    return tag_part or "(group)"


def _group_export_index(
    db: Session, review_session: ReviewSession
) -> tuple[
    dict[int, tuple[str, ...]],
    dict[tuple[int, tuple[str, ...]], str],
]:
    """Precompute, for the session's group-scoped instruments:

    - ``key_by_assignment`` — group key (the tuple of boundary tag
      values) per assignment; assignments on per-reviewee
      instruments are absent.
    - ``identity`` — the composed group-identity string per
      ``(instrument_id, group_key)``, used as the collapsed row's
      ``RevieweeName``.
    """
    assignments = list(
        db.execute(
            select(Assignment)
            .options(joinedload(Assignment.reviewee))
            .where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    key_by_assignment = responses_service.group_keys(
        db, assignments=assignments, session_id=review_session.id
    )
    if not key_by_assignment:
        return {}, {}
    with_names = _name_included_instruments(
        db,
        {a.instrument_id for a in assignments if a.id in key_by_assignment},
    )
    members: dict[tuple[int, tuple[str, ...]], set[str]] = {}
    for assignment in assignments:
        group_key = key_by_assignment.get(assignment.id)
        if group_key is None:
            continue
        members.setdefault(
            (assignment.instrument_id, group_key), set()
        ).add(assignment.reviewee.name)
    identity = {
        (instrument_id, group_key): _compose_group_identity(
            group_key,
            sorted(names),
            with_names=instrument_id in with_names,
        )
        for (instrument_id, group_key), names in members.items()
    }
    return key_by_assignment, identity


def serialize_responses(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s responses.

    Yields, in order: the per-instrument preamble blocks (an
    ``(instrument_{n},)`` row followed by one
    ``(field_key, help_text)`` row per response field); a blank
    row; :data:`HEADER`; then the data rows. The data query
    streams through a ``yield_per`` cursor so memory stays flat on
    sessions with hundreds of thousands of rows.

    A per-reviewee instrument emits one row per ``Response``. A
    **group-scoped instrument** (``Instrument.group_kind`` set)
    emits one row per group: the reviewer's answer is fanned out
    across the group's member assignments at save time, so those
    duplicate ``Response`` rows collapse to a single row carrying
    the composed group identity in ``RevieweeName`` (the other
    reviewee columns empty) and ``InstrumentFlavour=group-scoped``.

    A session with no instruments emits just :data:`HEADER` (no
    preamble, no gap). Per the "Empty / missing values" rule, a
    ``Response`` row with ``value IS NULL`` (reviewer cleared the
    field) emits an empty ``Value`` cell — the row is still emitted
    because the reviewer interacted with the field. A field with no
    ``Response`` row at all emits no data row.
    """

    # Timestamps render in the session's resolved zone (18B) — ISO
    # 8601 carrying that zone's offset, so the cell is precise and
    # round-trip-safe while still naming the session zone.
    session_zone = resolve_session_timezone(review_session)

    # Preamble — per-instrument field dictionary. Instruments are
    # named positionally by their sorted order; the operator's
    # typed name is not exported.
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    instrument_label: dict[int, str] = {}
    for n, instrument in enumerate(instruments, start=1):
        label = f"instrument_{n}"
        instrument_label[instrument.id] = label
        yield (label,)
        fields = sorted(
            instrument.response_fields, key=lambda f: (f.order, f.id)
        )
        for field in fields:
            yield (field.field_key, field.help_text or "")
    if instruments:
        # Blank-row gap between the preamble and the data table.
        yield ()

    yield HEADER

    # Group-scoped instruments collapse the fan-out's per-member
    # duplicate Response rows to one row per group; the index work
    # is skipped entirely when the session has none.
    if any(i.group_kind is not None for i in instruments):
        group_key_by_assignment, group_identity = _group_export_index(
            db, review_session
        )
    else:
        group_key_by_assignment, group_identity = {}, {}
    seen_group_cells: set[tuple[int, int, tuple[str, ...], int]] = set()

    stmt = (
        select(
            Response,
            Reviewer,
            Reviewee,
            Instrument,
            InstrumentResponseField,
            ResponseTypeDefinition,
        )
        .join(Assignment, Response.assignment_id == Assignment.id)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .join(Instrument, Assignment.instrument_id == Instrument.id)
        .join(
            InstrumentResponseField,
            Response.response_field_id == InstrumentResponseField.id,
        )
        .join(
            ResponseTypeDefinition,
            InstrumentResponseField.response_type_id
            == ResponseTypeDefinition.id,
        )
        .where(Assignment.session_id == review_session.id)
        .order_by(
            Reviewer.email,
            Reviewee.email_or_identifier,
            Instrument.order,
            Instrument.id,
            InstrumentResponseField.order,
            InstrumentResponseField.id,
        )
        .execution_options(yield_per=1000)
    )

    for response, reviewer, reviewee, instrument, field, rtd in db.execute(
        stmt
    ):
        group_key = group_key_by_assignment.get(response.assignment_id)
        if group_key is not None:
            # Group-scoped — collapse the fanned-out member
            # duplicates to one row per (reviewer, instrument,
            # group, field).
            cell = (reviewer.id, instrument.id, group_key, field.id)
            if cell in seen_group_cells:
                continue
            seen_group_cells.add(cell)
            reviewee_name = group_identity.get(
                (instrument.id, group_key), "(group)"
            )
            reviewee_email = ""
            reviewee_tags = ("", "", "")
            self_review = "FALSE"
            flavour = "group-scoped"
        else:
            reviewee_name = reviewee.name
            reviewee_email = reviewee.email_or_identifier
            reviewee_tags = (
                reviewee.tag_1 or "",
                reviewee.tag_2 or "",
                reviewee.tag_3 or "",
            )
            self_review = (
                "TRUE" if is_self_review(reviewer, reviewee) else "FALSE"
            )
            flavour = "per-reviewee"
        yield (
            reviewer.name,
            reviewer.email,
            reviewer.tag_1 or "",
            reviewer.tag_2 or "",
            reviewer.tag_3 or "",
            reviewee_name,
            reviewee_email,
            reviewee_tags[0],
            reviewee_tags[1],
            reviewee_tags[2],
            instrument_label.get(instrument.id, ""),
            instrument.short_label or "",
            field.field_key,
            field.label,
            rtd.response_type,
            response.value if response.value is not None else "",
            self_review,
            iso_in_zone(response.saved_at, session_zone),
            iso_in_zone(response.submitted_at, session_zone),
            str(response.version),
            flavour,
        )
