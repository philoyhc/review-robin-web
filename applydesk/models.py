"""Apply Desk's tables (segment AD2A): people, exercises, who operates
them, and the audit trail; an exercise's settings and tags (AD2B); its
timeline, gates, outcomes and Candidates (AD2C); its panels and roster
(AD2E); its form's cards (AD2D); its email ticks and templates (AD2L).
The rest of an exercise still comes from `applydesk/sample_data.py` until
the series' later segments (`applydesk/guide/ad2_series.md`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from applydesk.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Person(Base):
    """Someone Apply Desk knows (ruling 73), bound by tenant and object ID
    once known; until then *pending*, found by `email_key` (the casefolded
    email) and bound at first sign-in. Email, UPN and name are snapshots.
    The operator allowlist is on the row (ruling 75): `may_operate`, set by
    the platform super-admin."""

    __tablename__ = "person"
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_id", name="uq_person_tenant_object"),
        # One pending person per address (Codex on #4110); bound people may
        # share an address, theirs being a snapshot only.
        Index(
            "uq_person_pending_email",
            "email_key",
            unique=True,
            sqlite_where=text("object_id IS NULL"),
            postgresql_where=text("object_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320))
    email_key: Mapped[str | None] = mapped_column(String(320), index=True)
    upn: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(255))
    # The casefolded name the people searches match (segment AD2E, AD-127):
    # SQLite's `lower()` is ASCII-only, so "émile" missed "Émile" there.
    # Kept in step with `display_name` by `_name_key` below. Three times the
    # name's width: casefolding lengthens some letters ("ß" is "ss"), at
    # most to three (Codex on #4169).
    display_name_key: Mapped[str | None] = mapped_column(String(765), index=True)
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When they first signed in (segment AD2W): a directory pick is bound
    # without signing in, so `bound_at` is not it.
    first_signed_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    may_operate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    admitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_person_admitted_by")
    )
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # An Admin (segment AD2M): reaches the Admin pages and keeps the
    # operator list; made and unmade by the super-admin. An Admin is always
    # on the operator list too (Promote puts them there; Revoke refuses one).
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    @validates("display_name")
    def _name_key(self, _key: str, value: str | None) -> str | None:
        self.display_name_key = value.casefold() if value else None
        return value

    @property
    def bound(self) -> bool:
        """Whether the person is tied to an account (tenant and object ID)."""
        return self.object_id is not None

    @property
    def label(self) -> str:
        """How pages name the person: their name, else their address."""
        return self.display_name or self.email or "Unknown person"


class Exercise(Base):
    """An exercise: its public ID (AD-53: unique per table) and its own
    settings (segment AD2B). `revision` 0 means no settings are recorded
    yet (a row AD2A made); the pages then keep the sample's. NULL is unset,
    never the text "Not set" (AD-60); a NULL help contact or timezone takes
    the operator settings' default (AD-54). Nothing is hard-deleted
    (ruling 74): `archived_at` and `deleted_at`."""

    __tablename__ = "exercise"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_exercise_public_id"),
        # One live exercise per code, ignoring case; archiving or deleting
        # frees it (segment AD2B).
        Index(
            "uq_exercise_live_code",
            "code_key",
            unique=True,
            sqlite_where=text(
                "code_key IS NOT NULL AND archived_at IS NULL AND deleted_at IS NULL"
            ),
            postgresql_where=text(
                "code_key IS NOT NULL AND archived_at IS NULL AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    name: Mapped[str | None] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(40))
    code_key: Mapped[str | None] = mapped_column(String(40))  # the code, casefolded
    description: Mapped[str | None] = mapped_column(Text)
    eligibility: Mapped[str | None] = mapped_column(String(16))  # "open", "invitation"
    blind: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    help_contact: Mapped[str | None] = mapped_column(String(320))
    timezone: Mapped[str | None] = mapped_column(String(64))
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_exercise_created_by")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Process's own revision (segment AD2C): 0 until its timeline is first
    # saved, the pages keeping the sample's; a Details save leaves it be.
    process_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Panels' own revision (segment AD2E): 0 until its panels are first
    # saved, the pages keeping the sample's.
    panels_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # The form's heading and its own revision (segment AD2D): 0 until Form
    # is first saved, the pages keeping the sample's form.
    form_title: Mapped[str | None] = mapped_column(String(200))
    form_description: Mapped[str | None] = mapped_column(Text)
    form_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Whether Process has recorded its email ticks (segment AD2L): until
    # then a sample keeps its own.
    sends_saved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class ExerciseTag(Base):
    """One tag on an exercise (segment AD2B): kept in the case first typed,
    unique per exercise ignoring case."""

    __tablename__ = "exercise_tag"
    __table_args__ = (UniqueConstraint("exercise_id", "label_key", name="uq_exercise_tag_label"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercise.id", name="fk_exercise_tag_exercise"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    label_key: Mapped[str] = mapped_column(String(40), nullable=False)


class ExerciseOperator(Base):
    """A person's grant on an exercise (ruling 73): one row per pair, its
    Owners marked. Removal sets `removed_at`; re-adding clears it. An
    exercise has one or more Owners (segment AD2M: an Admin or the
    super-admin adopting one becomes an Owner beside the others); every
    change to them runs under the exercise's row lock
    (`applydesk/operators.py`), which replaced the one-Owner index."""

    __tablename__ = "exercise_operator"
    __table_args__ = (
        UniqueConstraint("exercise_id", "person_id", name="uq_exercise_operator_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercise.id", name="fk_exercise_operator_exercise"), nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", name="fk_exercise_operator_person"), nullable=False
    )
    is_owner: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    added_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_exercise_operator_added_by")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _exercise_fk(table: str) -> Mapped[int]:
    return mapped_column(
        ForeignKey("exercise.id", name=f"fk_{table}_exercise"), nullable=False, index=True
    )


class Stage(Base):
    """A stage of an exercise's timeline (segment AD2C, rulings 15 and
    35): its place, name and dates (NULL unset), its status, whether
    applicants see it, and, on the stage holding the form, the form's own
    window and state, the one source of either (AD-36, AD-59). ``key`` is
    stable across saves (``s<n>``). Retired, never deleted (ruling 74)."""

    __tablename__ = "stage"
    __table_args__ = (UniqueConstraint("exercise_id", "key", name="uq_stage_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("stage")
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    holds_form: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Ruling 77: the exercise's one Candidates item sits on a stage.
    holds_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    form_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    form_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "draft", "open" or "closed" on the stage holding the form (ruling 24).
    form_state: Mapped[str | None] = mapped_column(String(8))
    form_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    form_closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Gate(Base):
    """A gate (rulings 21, 27, 28): its ``key`` unique per exercise and never
    reused, its handle in URLs and file names (ruling 37, AD-48); its
    number is computed for display. ``rule`` is validated JSON whose
    references are keys (AD-62)."""

    __tablename__ = "gate"
    __table_args__ = (UniqueConstraint("exercise_id", "key", name="uq_gate_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("gate")
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stage.id", name="fk_gate_stage"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    via: Mapped[str] = mapped_column(String(16), nullable=False, default="RRW")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="automatic")
    total_min: Mapped[int | None] = mapped_column(Integer)
    total_max: Mapped[int | None] = mapped_column(Integer)
    review_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rule: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GateField(Base):
    """A response field evaluators answer (ruling 28), by a stable key
    Review Robin reports under (AD-51)."""

    __tablename__ = "gate_field"
    __table_args__ = (UniqueConstraint("gate_id", "key", name="uq_gate_field_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gate_id: Mapped[int] = mapped_column(
        ForeignKey("gate.id", name="fk_gate_field_gate"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="integer")
    min: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    max: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    step: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    options: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # A bounded Integer or Decimal answered as Review Robin's scale (segment
    # AD2S): ``type`` stays the number type, as Review Robin's does, and the
    # labels read ``start|middle|end``, "" for none.
    scale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scale_labels: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    help: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GateResult(Base):
    """One of a gate's results (ruling 21): position 1 is the headline; the
    field it collates by FK, never a copy of it (AD-51)."""

    __tablename__ = "gate_result"
    __table_args__ = (UniqueConstraint("gate_id", "key", name="uq_gate_result_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gate_id: Mapped[int] = mapped_column(
        ForeignKey("gate.id", name="fk_gate_result_gate"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    field_id: Mapped[int | None] = mapped_column(
        ForeignKey("gate_field.id", name="fk_gate_result_field")
    )
    derive: Mapped[str] = mapped_column(String(16), nullable=False, default="mean")
    value: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    at_least: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ignore_zero: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GateSource(Base):
    """One of a gate's ranked evaluator sources (ruling 27): ``ref`` a panel
    key or a Form question until AD2E and AD2D store those. Rewritten
    with its gate on each save."""

    __tablename__ = "gate_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gate_id: Mapped[int] = mapped_column(
        ForeignKey("gate.id", name="fk_gate_source_gate"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    all_members: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Outcome(Base):
    """An outcome (rulings 13, 14, 38): its key unique per exercise and never
    reused, its due time, its rule; *Decided* is derived, never stored."""

    __tablename__ = "outcome"
    __table_args__ = (UniqueConstraint("exercise_id", "key", name="uq_outcome_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("outcome")
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stage.id", name="fk_outcome_stage"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rule: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutcomeValue(Base):
    """A value an outcome decides (AD-57): rules name it by key, kept
    while its label stands or is renamed on Process (the page carries each
    value's key, `process_store`); ``advances`` says whether it takes the
    application on."""

    __tablename__ = "outcome_value"
    __table_args__ = (UniqueConstraint("outcome_id", "key", name="uq_outcome_value_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outcome_id: Mapped[int] = mapped_column(
        ForeignKey("outcome.id", name="fk_outcome_value_outcome"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    advances: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutcomeWeight(Base):
    """A gate result's weight in an outcome's combined result: the gate by
    FK, the result by its key on it ("" reads its first, ruling 21).
    Rewritten with its outcome on each save."""

    __tablename__ = "outcome_weight"
    __table_args__ = (
        UniqueConstraint("outcome_id", "gate_id", "result_key", name="uq_outcome_weight_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outcome_id: Mapped[int] = mapped_column(
        ForeignKey("outcome.id", name="fk_outcome_weight_outcome"), nullable=False, index=True
    )
    gate_id: Mapped[int] = mapped_column(
        ForeignKey("gate.id", name="fk_outcome_weight_gate"), nullable=False
    )
    result_key: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    weight: Mapped[float] = mapped_column(Float, nullable=False)


class OutcomeRelease(Base):
    """An outcome released to one audience (``applicants`` or ``reviewers``),
    by whom and when (ruling 38): written only by a release (AD2F's
    *Release*). Whom it opens to, and what, is ruling 79's views (AD2V)."""

    __tablename__ = "outcome_release"
    __table_args__ = (UniqueConstraint("outcome_id", "audience", name="uq_outcome_release_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outcome_id: Mapped[int] = mapped_column(
        ForeignKey("outcome.id", name="fk_outcome_release_outcome"), nullable=False, index=True
    )
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_outcome_release_by")
    )


class Candidate(Base):
    """Someone on an exercise's Candidates list (ruling 77): added by hand,
    through the people search or a CSV, once per exercise; removing them
    sets ``removed_at``, adding them again clears it."""

    __tablename__ = "candidate"
    __table_args__ = (UniqueConstraint("exercise_id", "person_id", name="uq_candidate_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("candidate")
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", name="fk_candidate_person"), nullable=False
    )
    via: Mapped[str] = mapped_column(String(8), nullable=False)  # "search" or "csv"
    added_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_candidate_added_by")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Application(Base):
    """One application to an exercise (segment AD2J; AD-38): its applicant a
    person (ruling 73), its name as they gave it, and its state, `draft`,
    `submitted` or `withdrawn`, with the time of each move. A withdrawn
    application keeps its `submitted_at`. ``form_revision`` is the
    exercise's when it was submitted. Rows are in the order applications
    came in (``id``); nothing is deleted (ruling 74)."""

    __tablename__ = "application"
    __table_args__ = (UniqueConstraint("public_id", name="uq_application_public_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), nullable=False)
    exercise_id: Mapped[int] = _exercise_fk("application")
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", name="fk_application_person"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(10), nullable=False)  # draft, submitted, withdrawn
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdraw_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    form_revision: Mapped[int | None] = mapped_column(Integer)


class Panel(Base):
    """A named roster an exercise keeps (segment AD2E; rulings 4, 19, 39):
    keyed per exercise (``panel-<n>``, minted by the server, never reused),
    named uniquely among its live panels; retiring sets ``retired_at``
    (ruling 74)."""

    __tablename__ = "panel"
    __table_args__ = (
        UniqueConstraint("exercise_id", "key", name="uq_panel_key"),
        Index(
            "uq_panel_live_name",
            "exercise_id",
            "name_key",
            unique=True,
            sqlite_where=text("retired_at IS NULL"),
            postgresql_where=text("retired_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("panel")
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_key: Mapped[str] = mapped_column(String(240), nullable=False)  # casefolded: 3 x 80
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RosterEntry(Base):
    """Someone on an exercise's Panels table (ruling 20), on a panel or on
    none: the name as typed and the note, one per person (AD-50). Removing
    them sets ``retired_at``; adding them again clears it."""

    __tablename__ = "roster_entry"
    __table_args__ = (UniqueConstraint("exercise_id", "person_id", name="uq_roster_entry_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("roster_entry")
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", name="fk_roster_entry_person"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PanelMember(Base):
    """A roster entry on a panel; unticking sets ``retired_at``, ticking
    again clears it."""

    __tablename__ = "panel_member"
    __table_args__ = (UniqueConstraint("panel_id", "roster_entry_id", name="uq_panel_member_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    panel_id: Mapped[int] = mapped_column(
        ForeignKey("panel.id", name="fk_panel_member_panel"), nullable=False, index=True
    )
    roster_entry_id: Mapped[int] = mapped_column(
        ForeignKey("roster_entry.id", name="fk_panel_member_entry"), nullable=False, index=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FormCard(Base):
    """One card of an exercise's form (segment AD2D; AD-45): a field, a
    section or a page break, in the form's order. ``key`` is stable across
    saves and renames (``q<n>``, minted by the server, never reused), so a
    rule names a question by it. The text widths are Form's own checks;
    ``pool`` is ``institution`` or a panel's key. Removing a card sets
    ``retired_at`` (ruling 74)."""

    __tablename__ = "form_card"
    __table_args__ = (UniqueConstraint("exercise_id", "key", name="uq_form_card_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("form_card")
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # field, section, pagebreak
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="string")
    label: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    help: Mapped[str] = mapped_column(Text, nullable=False, default="")
    min: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    max: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    step: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    options: Mapped[str] = mapped_column(Text, nullable=False, default="")
    exclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ratio_w: Mapped[str] = mapped_column(String(6), nullable=False, default="4")
    ratio_h: Mapped[str] = mapped_column(String(6), nullable=False, default="5")
    pool: Mapped[str] = mapped_column(String(80), nullable=False, default="institution")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailSend(Base):
    """One email Process ticks (segment AD2L; rulings 16, 65): ``item`` is
    ``receipt``, ``reminder`` or an outcome's key, ``audience``
    ``Applicants`` or ``Evaluators``. Recorded with Process's save; an
    unticked one is retired (ruling 74)."""

    __tablename__ = "email_send"
    __table_args__ = (
        UniqueConstraint("exercise_id", "item", "audience", name="uq_email_send_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("email_send")
    item: Mapped[str] = mapped_column(String(40), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailTemplate(Base):
    """An email's template (segment AD2L; ruling 54), by the item and
    audience it is owed for: its subject and body as its Emails card last
    saved them, and ``version``, how many times it was saved, which a card
    sends back so a save from an older page is refused."""

    __tablename__ = "email_template"
    __table_args__ = (
        UniqueConstraint("exercise_id", "item", "audience", name="uq_email_template_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = _exercise_fk("email_template")
    item: Mapped[str] = mapped_column(String(40), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """One audited change, in Review Robin's envelope (ruling 74): its type,
    who, on which exercise, and `detail`, validated against the event
    type's schema on write (`applydesk/audit.py`, rung 3)."""

    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("person.id", name="fk_audit_event_actor")
    )
    exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercise.id", name="fk_audit_event_exercise"), index=True
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
