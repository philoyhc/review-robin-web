from __future__ import annotations

from typing import TYPE_CHECKING, Any

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    column,
    func,
    select,
    table,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.assignment import Assignment
    from app.db.models.instrument_field import (
        InstrumentDisplayField,
        InstrumentResponseField,
    )
    from app.db.models.instrument_view_policy import InstrumentViewPolicy
    from app.db.models.review_session import ReviewSession

# Segment 19Y Item 1 — the intro layouts an instrument may take, in the
# order the instrument card's chip cycles them. A later layout appends.
INTRO_LAYOUTS: tuple[str, ...] = ("layout_1", "layout_2")
INTRO_LAYOUT_DEFAULT = "layout_1"


def _next_session_seq(context: Any) -> int:
    """``max(session_seq) + 1`` within the row's session, 19Q Item 6.

    A context-sensitive column default: SQLAlchemy calls it per insert
    with the pending parameters, so it reads the ``session_id`` being
    written and never needs the caller to supply a number.

    ``max + 1``, not ``count + 1``. That makes an *interior* delete
    safe — remove the second of three and the next created is 4 — but
    **a trailing delete does hand the number back**: delete the newest
    of 1, 2, 3 and the next instrument is 3 again. A monotonic sequence
    needs a high-water mark this column does not keep. Measured, not
    inferred, and **accepted** (author, 2026-09-19): a trailing slot has
    no successor, so recycling there disturbs no ordering the operator
    can see. Pinned by
    ``test_a_trailing_delete_hands_the_number_back``.

    The clone path does not reach here — ``session_clone`` copies every
    mapped column, so an explicit ``session_seq`` is already in the
    parameters and the default is skipped. That is what preserves a
    source reading 1, 3, 2 as 1, 3, 2.

    **Several rows in one flush are numbered in turn.** The ORM batches
    them into one ``executemany``, and every row's default runs before
    any row is written, so each query would read the same ``max``. The
    numbers already handed out are kept on the execution context, which
    the batch shares, and a later row continues from them. Before 19V
    Item 3 the batch took one number twice; ``uq_instruments_session_seq``
    would now refuse it.
    """
    table = Instrument.__table__
    session_id = context.get_current_parameters()["session_id"]
    handed_out: dict[int, int] = context.__dict__.setdefault(
        "_rrw_session_seq", {}
    )
    if session_id in handed_out:
        highest = handed_out[session_id]
    else:
        highest = context.connection.execute(
            select(func.max(table.c.session_seq)).where(
                table.c.session_id == session_id
            )
        ).scalar()
    handed_out[session_id] = (highest or 0) + 1
    return handed_out[session_id]


def _session_self_reviews_active(context: Any) -> bool:
    """The owning session's ``self_reviews_active``, read at insert —
    the seed for :attr:`Instrument.self_reviews_active` (findings E3,
    2026-10-17).

    Context-sensitive like ``_next_session_seq`` above, so every creation
    path gets the seed without remembering it. A path that carries the
    flag itself — Duplicate copies every mapped column, the Settings
    import passes the file's value when the file has one — supplies an
    explicit value and this default is skipped. The ORM flushes a
    pending change to the session row before inserting its instruments,
    so the value read here is the one in memory.
    """
    sessions = table(
        "sessions", column("id"), column("self_reviews_active", Boolean)
    )
    params = context.get_current_parameters()
    value = context.connection.execute(
        select(sessions.c.self_reviews_active).where(
            sessions.c.id == params["session_id"]
        )
    ).scalar()
    return True if value is None else bool(value)


class Instrument(Base, TimestampMixin):
    __tablename__ = "instruments"
    __table_args__ = (
        # The observer's CSV address names an instrument by this pair
        # (19V Item 3), so two rows must never share it.
        UniqueConstraint(
            "session_id", "session_seq", name="uq_instruments_session_seq"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_label: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(2000))
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    session_seq: Mapped[int] = mapped_column(
        Integer, default=_next_session_seq, nullable=False
    )
    """19Q Item 6 — the instrument's per-session identity.

    Assigned once at creation (``_next_session_seq`` below) and
    never updated, so it is the operator-facing number in the
    ``Instrument_{N}`` fallback label and the key for the card tint.
    Deliberately *not* ``order``: instrument drag-and-drop ships
    (``POST .../instruments/order``), and a number that moved under the
    drag is the defect this column exists to remove.

    Gaps are expected and correct. Deleting the second of three leaves
    1, 3 — closing the gap would be renumbering, which is the thing a
    stable handle must not do. See ``_next_session_seq`` for the one
    case where the handle is *not* stable. Cloning a session copies the value
    verbatim (``session_clone`` copies every mapped column), so a
    source reading 1, 3, 2 reproduces as 1, 3, 2.

    Assigned by a context-sensitive column default rather than by each
    creation path, so no path can forget it and none has to remember:
    ``ensure_default_instrument``, ``create_instrument``,
    ``replicate_instrument`` and the config importer all get it free.
    There is no *server* default, so a row inserted outside SQLAlchemy
    still fails loudly instead of minting ``Instrument_0``.

    Unique per session (``uq_instruments_session_seq``, 19V Item 3): the
    observer's collation CSV is addressed by it, so a duplicate is an
    insert error rather than two instruments behind one address.
    """
    accepting_responses: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    starts_new_page: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    """Segment 18M page-break flag. ``true`` = "this instrument
    starts a new page on the reviewer surface" (i.e. there's a
    page break between this instrument and the previous one in
    ``Instrument.order`` sequence). Meaningful only for instruments
    at position ≥ 2; the value on the first instrument is ignored
    at render time. Backfilled to ``True`` on existing rows by
    revision ``e5c1a3b9d472`` so today's one-instrument-per-page
    reviewer behaviour is preserved on deploy; new instruments
    created post-migration default to ``False`` (continue current
    page). Manipulated via
    ``app.services.instruments.create_page_break_after`` /
    ``clear_page_break`` / ``reorder_instruments`` (Segment 18M
    PR 1)."""
    self_reviews_active: Mapped[bool] = mapped_column(
        Boolean,
        default=_session_self_reviews_active,
        server_default=true(),
        nullable=False,
    )
    """Whether this instrument's self-review rows are included — the
    Assignments page's per-instrument **Self review** toggle (findings
    E3, 2026-10-17). Prepare / Generate writes a self-review row whose
    sides are both active with this value, so the toggle survives the
    next regenerate; before this column the toggle lived only in the
    rows' ``include`` and Prepare reset it from the session's flag.
    Seeded from ``ReviewSession.self_reviews_active`` at creation
    (``_session_self_reviews_active``); backfilled the same way by
    revision ``f3a7c1e9d5b2``."""
    intro_layout: Mapped[str] = mapped_column(
        String(16),
        default=INTRO_LAYOUT_DEFAULT,
        server_default=INTRO_LAYOUT_DEFAULT,
        nullable=False,
    )
    """Which arrangement the instrument's intro takes on the reviewer
    surface and the Instruments page preview (segment 19Y Item 1):
    ``layout_1`` puts the heading card, holding the help texts, left and
    the visibility card right; ``layout_2`` the heading and visibility left
    and one card of help texts right (19Y Item 2). One of :data:`INTRO_LAYOUTS`; the instrument card's
    layout chip sets it (``instruments.set_intro_layout``). Revision
    ``c4e9a2f7b1d3`` gave every existing row the default."""
    deadline_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    sort_display_fields: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    """Operator-defined default sort spec for this instrument's
    reviewer-surface table (Segment 13B). Each entry shapes as
    ``{"display_field_id": int, "dir": "asc"|"desc"}`` per the
    canonical functional spec at ``spec/sort_by_reviewee.md``.
    NULL or ``[]`` = "no operator default" (the reviewer-surface
    render falls back to its current sort policy of instrument
    order then insertion order). Maximum 3 entries; service-layer
    ``instruments.set_sort_display_fields`` enforces length /
    duplicate / direction validators and drops an id that is not
    this instrument's display field.

    Column shipped inert in Segment 13D PR 5 (#701, 2026-05-09);
    13B PR 1 (#TBD) lit up the reviewer-surface render-path
    consumer + the service writer."""
    group_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """Group-scoping flag + group-boundary spec for Segment 13C's
    group-scoped instruments — one shared answer covers a whole
    group of reviewees instead of per-reviewee. NULL = "regular
    per-reviewee instrument". Any non-null value flags the
    instrument group-scoped.

    The non-null value encodes the group-boundary spec: an ordered,
    comma-joined list of tag key-codes (``r1``-``r3`` reviewee
    tags, ``p1``-``p3`` pair-context tags) — e.g. ``r1`` or
    ``r1,p2``. A reviewer's rule-eligible universe is partitioned
    into groups by the shared values of those boundary tags
    (additive). A group-scoped instrument with no boundary tag
    keeps the sentinel ``"both"`` so the column stays non-null.
    Encoded / decoded by ``app.services.instruments`` —
    ``encode_group_kind`` / ``decode_group_kind`` /
    ``set_group_boundary``. See ``spec/instruments.md`` "Link 3 — Unit
    of review"."""
    rule_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_rule_sets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    """The per-session ``session_rule_sets`` row currently applied to
    this instrument (Segment 15B). NULL = "no RuleSet currently
    selected" — the initial state for every existing instrument
    post-13D PR 4 and the state after a reset-assignments action.

    Targets the per-session copy table, not the operator library
    (``operator_rule_sets``), so deleting an instrument disposes
    of the pointer without touching the session's RuleSet copy,
    and deleting from the operator library doesn't touch any
    instrument pointer (session copies survive library deletes
    via ``session_rule_sets.library_origin_id`` SET NULL — see
    13D PR 2)."""

    # Wave 5 PR 5.3 — ``is_new_model`` column dropped. Every
    # instrument is implicitly a (former) new-model instrument
    # post-collapse; legacy individual / group cards retired.

    band1_touched_links: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    """Sticky per-link set of Band 1 link pills the operator has
    deliberately clicked into a set state. Each Band 1 link
    (Link 1 / Link 2 / Link 3 = Pool of reviewers / Pool of those
    reviewed / Unit of review) starts at ``"Not set"`` on a fresh
    instrument; clicking the pill once flips the link into its
    default set state (``"All"`` for Link 1 + 2, ``"Individual"``
    for Link 3) and the link id is unioned into this column.

    Until all three link ids appear here, ``is_configured`` reports
    False — the workflow card surfaces the instrument as not yet
    set up, forcing the operator to make a deliberate choice
    instead of silently shipping the default Full Matrix
    (Wave 5 follow-up "Not set" pill safety gate). Stored values
    are a subset of ``{"link1", "link2", "link3"}``; NULL reads
    as the empty set."""

    column_widths: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    """Per-column pixel widths the operator set by drag-resizing the
    Band 2 preview table on a new-model instrument. Shape:
    ``{"identity": 200, "df_<id>": 150, ...}`` — ``identity`` is the
    always-rendered Reviewee / Group identity column;
    ``df_<display_field_id>`` is each operator-chosen display field.
    Values are positive integer pixels. Missing keys mean "use the
    auto-sized default". When at least one entry is present, the
    reviewer-surface table renders with ``table-layout: fixed`` so
    the widths take hold; an entirely NULL ``column_widths`` keeps
    today's auto-layout behaviour unchanged."""

    band2_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    """Operator's Band 2 choices on the instrument card. Shape:
    ``{"selected_display_keys": ["reviewee.name", ...],
      "sample_reviewee_name": str,
      "sample_group_member_ids": [int, ...]}``, every key optional.
    Response fields are not stored here: ``set_band2_state``
    (``app/services/instruments/_band2.py``) writes them to
    ``instrument_response_fields`` rows. NULL = nothing selected."""

    cached_group_pair_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    cached_group_pair_stamp: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    """Lazy persisted cache for the reviewer-group pair count shown
    on a group-scoped instrument's rule card (Segment 13C PR 4
    slice 4b). ``cached_group_pair_stamp`` is a content-hash of the
    roster + the pinned rule's definition + ``group_kind``; a
    mismatch on read recomputes. Per-instrument (not per-rule, like
    ``session_rule_sets.cached_eligible_pair_count``) because the
    count depends on the instrument's boundary tags. Both NULL on a
    per-reviewee instrument or an un-pinned one — never populated.

    *(The parenthetical above named `session_rule_sets`'
    ``cached_eligible_pair_count``. Wave 5 PR 5.2 dropped that column
    with the rest of the library tier, so the comparison is kept for
    the reasoning and no longer points at a live column — 19R Item 2
    rung 1.)*"""

    cached_reconcile_stamp: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    cached_reconcile_stale: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    cached_reconcile_eligible: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    cached_reconcile_self_reviews_excluded: Mapped[int | None] = (
        mapped_column(Integer, nullable=True)
    )
    """Lazy persisted cache for this instrument's
    ``InstrumentReconcileState`` — *would regenerating change which
    pairs exist?* — against a content stamp of what the verdict is
    derived from (19R Item 2; the cost it removes is measured in
    ``docs/performance.md``).

    **Four columns, not a verdict and a stamp.** The surfaces render
    the whole state: ``app/web/views/_assignments.py`` reads
    ``eligible`` and ``self_reviews_excluded`` as well as ``stale``, so
    a verdict-only cache would leave the engine running on the page the
    cache exists to speed up.

    **Read as one unit.** A NULL or mismatched
    ``cached_reconcile_stamp`` is a miss and the other three are
    ignored, so they are never interpreted on their own. The stamp is
    ``String(80)`` rather than the ``String(64)`` beside it because it
    carries a version prefix ahead of its hash: a change to the stamp's
    shape then reads as a miss rather than as a silent hit on a value
    computed some other way.

    All four land NULL and stay NULL until the read-through and
    write-through arrive (rung 3); a NULL stamp is exactly the cache
    miss the reader will already handle."""

    session: Mapped[ReviewSession] = relationship(back_populates="instruments")
    display_fields: Mapped[list[InstrumentDisplayField]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        order_by="InstrumentDisplayField.order",
    )
    response_fields: Mapped[list[InstrumentResponseField]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        order_by="InstrumentResponseField.order",
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    view_policies: Mapped[list[InstrumentViewPolicy]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
