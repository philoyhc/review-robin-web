"""What a refused reviewer Save / Submit / Clear shows (participant
audit P3, author's ruling 2026-10-15): the sentence naming why, and the
answers the POST carried, as text to copy. The gate that decides the
cause is ``_write_refusal`` in ``routes_reviewer/_surface/_context.py``.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Reviewer,
    ReviewSession,
)
from app.services import date_formatting
from app.services import instruments as instruments_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service

# Each cause has its own sentence: a reviewer with nothing assigned was
# never "no longer" accepted, and a session reverted to draft is not
# "closed".
REFUSED_NOT_OPEN = "not_open"
REFUSED_CLOSED = "closed"
REFUSED_NO_ASSIGNMENTS = "no_assignments"


def write_refused_notice(
    review_session: ReviewSession, cause: str, *, action: str
) -> str:
    """The sentence a refused write shows. ``action`` is ``"save"``,
    ``"submit"`` or ``"clear"``."""
    outcome = {
        "save": "your last changes weren't saved",
        "submit": "your answers weren't submitted",
        "clear": "your answers weren't cleared",
    }[action]
    if cause == REFUSED_NO_ASSIGNMENTS:
        return f"You have nothing to review in this session right now, so {outcome}."
    if cause == REFUSED_NOT_OPEN:
        return f"This review is not currently open, so {outcome}."
    if lifecycle.is_ready(review_session) and lifecycle.deadline_has_passed(
        review_session
    ):
        zone = sessions_service.resolve_session_timezone(review_session)
        when = date_formatting.format_datetime(review_session.deadline, zone)
        label = date_formatting.gmt_offset_zone_label(
            zone, at=review_session.deadline
        )
        return f"This review closed at its deadline, {when} ({label}), so {outcome}."
    return f"This review has closed, so {outcome}."


def unsaved_answers(
    db: Session,
    review_session: ReviewSession,
    reviewer: Reviewer,
    form: Mapping[str, str],
) -> list[dict[str, str]]:
    """What a refused Save or Submit carried, as plain text the reviewer
    can copy. Read from the raw form, not the parsed upserts, whose
    values are stripped: an answer keeps its leading and trailing
    whitespace, such as a first line's indentation.

    Every typed value that isn't blank comes back, changed or not,
    whatever row it was posted against: echoing only some would make
    the card an oracle, for stored answers the visibility setting hides
    and for which assignment ids are the reviewer's. An entry is labeled
    ``{instrument}: {reviewee} — {field}`` only when a GET would show
    that row now, i.e. an included assignment of this reviewer on a
    visible field in a ``ready`` or ``expired`` session; any other value
    is listed bare, so an excluded row, a session that never opened and
    a hand-made id all name nobody."""
    typed = [
        u
        for u in responses_service.parse_form_payload(form, strip=False)
        if u.value.strip()
    ]
    if not typed:
        return []
    shown: dict[int, Assignment] = {}
    fields: dict[tuple[int, str], InstrumentResponseField] = {}
    if lifecycle.is_ready(review_session) or lifecycle.is_expired(review_session):
        # The rows a GET shows: the same filter as the surface's own
        # loader, ``_load_assignments_with_relations`` in
        # ``routes_reviewer/_surface/_context.py``. Keep them in step.
        shown = {
            a.id: a
            for a in db.execute(
                select(Assignment)
                .options(
                    joinedload(Assignment.reviewee),
                    joinedload(Assignment.instrument),
                )
                .where(
                    Assignment.session_id == review_session.id,
                    Assignment.reviewer_id == reviewer.id,
                    Assignment.include.is_(True),
                )
            ).scalars()
        }
        if shown:
            fields = {
                (f.instrument_id, f.field_key): f
                for f in db.execute(
                    select(InstrumentResponseField)
                    .where(
                        InstrumentResponseField.instrument_id.in_(
                            {a.instrument_id for a in shown.values()}
                        )
                    )
                    .where(InstrumentResponseField.visible.is_(True))
                ).scalars()
            }
    out: list[dict[str, str]] = []
    for upsert in typed:
        assignment = shown.get(upsert.assignment_id)
        field = (
            fields.get((assignment.instrument_id, upsert.field_key))
            if assignment is not None
            else None
        )
        if assignment is None or field is None:
            out.append({"value": upsert.value})
            continue
        out.append(
            {
                "instrument_label": instruments_service._instrument_label(
                    assignment.instrument
                ),
                "reviewee_name": assignment.reviewee.name,
                "field_label": field.label,
                "value": upsert.value,
            }
        )
    return out
