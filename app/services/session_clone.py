"""Session cloning — deep-copy a session's configuration graph into a
fresh ``draft`` session (Segment 18A Part 1).

Two modes:

- ``"all"`` — copies the full setup, including the reviewer /
  reviewee / relationship roster.
- ``"config"`` — copies the configuration shell only (instruments,
  response type definitions, rule sets, field-label overrides,
  settings, tags) but not the roster.

Never copied either way: responses, assignments, invitations, audit
history, email-outbox rows — a clone always starts as a clean draft.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Relationship,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionFieldLabel,
    SessionOperator,
    SessionRuleSet,
    SessionTag,
    User,
)
from app.services import audit

CLONE_MODES: tuple[str, ...] = ("all", "config")

# ``id`` plus the ``TimestampMixin`` columns are never carried over —
# a cloned row is new, so it gets a fresh PK and fresh timestamps.
_SKIP_BASE: frozenset[str] = frozenset({"id", "created_at", "updated_at"})

_CODE_MAX_LENGTH = 64


def _column_values(obj: object, *, skip: set[str]) -> dict[str, Any]:
    """Every mapped column value of ``obj`` except the keys in ``skip``."""
    mapper = sa_inspect(obj).mapper
    return {
        attr.key: getattr(obj, attr.key)
        for attr in mapper.column_attrs
        if attr.key not in skip
    }


def _unique_code(db: Session, base: str) -> str:
    """A ``sessions.code`` not yet taken — ``{base}-copy``, then
    ``{base}-copy-2`` … (codes are unique). Truncated to the column
    width."""
    candidate = f"{base}-copy"[:_CODE_MAX_LENGTH]
    n = 2
    while (
        db.execute(
            select(ReviewSession.id).where(ReviewSession.code == candidate)
        ).first()
        is not None
    ):
        candidate = f"{base}-copy-{n}"[:_CODE_MAX_LENGTH]
        n += 1
    return candidate


def clone_session(
    db: Session,
    *,
    source: ReviewSession,
    user: User,
    mode: str,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Clone ``source`` into a fresh ``draft`` session owned by ``user``.

    The clone is named ``"Copy of {name}"`` with a derived unique code;
    the operator renames it afterwards. The deadline resets (a clone is
    a new cycle); tags are copied in both modes.
    """
    if mode not in CLONE_MODES:
        raise ValueError(f"Unknown clone mode {mode!r}")

    clone = ReviewSession(
        name=f"Copy of {source.name}",
        code=_unique_code(db, source.code),
        description=source.description,
        status="draft",
        deadline=None,
        assignment_mode=source.assignment_mode,
        self_reviews_active=source.self_reviews_active,
        help_contact=source.help_contact,
        email_template_overrides=(
            dict(source.email_template_overrides)
            if source.email_template_overrides
            else None
        ),
        display_timezone=source.display_timezone,
        created_by_user_id=user.id,
    )
    db.add(clone)
    db.flush()

    db.add(
        SessionOperator(session_id=clone.id, user_id=user.id, role="owner")
    )

    # Response type definitions — copied first so instruments' response
    # fields can re-point at the clones.
    rtd_map: dict[int, int] = {}
    for rtd in source.response_type_definitions:
        new_rtd = ResponseTypeDefinition(
            session_id=clone.id,
            **_column_values(rtd, skip={"id", "session_id"}),
        )
        db.add(new_rtd)
        db.flush()
        rtd_map[rtd.id] = new_rtd.id

    # Session rule sets — copied before instruments (rule_set_id).
    rule_set_map: dict[int, int] = {}
    for rule_set in db.execute(
        select(SessionRuleSet).where(SessionRuleSet.session_id == source.id)
    ).scalars():
        new_rule_set = SessionRuleSet(
            session_id=clone.id,
            **_column_values(
                rule_set, skip=set(_SKIP_BASE) | {"session_id"}
            ),
        )
        db.add(new_rule_set)
        db.flush()
        rule_set_map[rule_set.id] = new_rule_set.id

    # Instruments + their display / response fields.
    instrument_count = 0
    for instrument in source.instruments:
        new_instrument = Instrument(
            session_id=clone.id,
            rule_set_id=rule_set_map.get(instrument.rule_set_id),
            **_column_values(
                instrument,
                skip=set(_SKIP_BASE)
                | {
                    "session_id",
                    "rule_set_id",
                    # Runtime state — a draft clone's instruments
                    # start closed.
                    "accepting_responses",
                    "deadline_closed_at",
                },
            ),
        )
        db.add(new_instrument)
        db.flush()
        instrument_count += 1
        for field in instrument.display_fields:
            db.add(
                InstrumentDisplayField(
                    instrument_id=new_instrument.id,
                    **_column_values(field, skip={"id", "instrument_id"}),
                )
            )
        for field in instrument.response_fields:
            # iii-b4: response_type_id FK dropped; just clone every
            # mapped column (including the inline bounds).
            db.add(
                InstrumentResponseField(
                    instrument_id=new_instrument.id,
                    **_column_values(
                        field,
                        skip={"id", "instrument_id"},
                    ),
                )
            )

    # Field-label overrides + tags.
    for label in source.field_labels:
        db.add(
            SessionFieldLabel(
                session_id=clone.id,
                **_column_values(label, skip={"id", "session_id"}),
            )
        )
    for tag in db.execute(
        select(SessionTag).where(SessionTag.session_id == source.id)
    ).scalars():
        db.add(
            SessionTag(
                session_id=clone.id,
                **_column_values(
                    tag, skip={"id", "session_id", "created_at"}
                ),
            )
        )

    # Roster — copied in ``"all"`` mode only.
    reviewer_count = reviewee_count = relationship_count = 0
    if mode == "all":
        reviewer_map: dict[int, int] = {}
        for reviewer in source.reviewers:
            new_reviewer = Reviewer(
                session_id=clone.id,
                **_column_values(
                    reviewer, skip=set(_SKIP_BASE) | {"session_id"}
                ),
            )
            db.add(new_reviewer)
            db.flush()
            reviewer_map[reviewer.id] = new_reviewer.id
            reviewer_count += 1

        reviewee_map: dict[int, int] = {}
        for reviewee in source.reviewees:
            new_reviewee = Reviewee(
                session_id=clone.id,
                **_column_values(
                    reviewee, skip=set(_SKIP_BASE) | {"session_id"}
                ),
            )
            db.add(new_reviewee)
            db.flush()
            reviewee_map[reviewee.id] = new_reviewee.id
            reviewee_count += 1

        for rel in db.execute(
            select(Relationship).where(Relationship.session_id == source.id)
        ).scalars():
            db.add(
                Relationship(
                    session_id=clone.id,
                    reviewer_id=reviewer_map[rel.reviewer_id],
                    reviewee_id=reviewee_map[rel.reviewee_id],
                    **_column_values(
                        rel,
                        skip=set(_SKIP_BASE)
                        | {"session_id", "reviewer_id", "reviewee_id"},
                    ),
                )
            )
            relationship_count += 1

    db.flush()
    audit.write_event(
        db,
        event_type="session.cloned",
        summary=(
            f"Session {clone.code} cloned from {source.code} "
            f"({'full' if mode == 'all' else 'config-only'})"
        ),
        actor_user_id=user.id,
        session=clone,
        payload=audit.counts(
            reviewers=reviewer_count,
            reviewees=reviewee_count,
            relationships=relationship_count,
            instruments=instrument_count,
        ),
        refs={"source_session_id": source.id},
        context={"mode": mode},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(clone)
    return clone
