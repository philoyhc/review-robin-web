"""Session-setup card view-shapes — the Setup overview rows on
session detail and the canonical session-level status pills row.

Slice 5 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns ``SetupRow`` / ``build_setup_rows`` (the four rows on the
Session setup card on session detail) plus ``SessionStatusPills`` /
``session_status_pills`` (the standardized session-level status
row rendered by ``partials/session_setup_status_row.html``, which
appears on every session-scoped page so the chrome reads as a
single contract).

Source ranges in pre-PR-5 ``_legacy.py``: lines 37-101
(Setup card), 104-116 (``SessionStatusPills`` dataclass), 778-797
(``session_status_pills`` builder).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    EmailOutbox,
    Instrument,
    Invitation,
    Observer,
    Relationship,
    Response,
    ReviewSession,
    Reviewee,
    Reviewer,
)
from app.services import assignments, csv_imports
from app.services import field_labels as field_labels_service
from app.services._queries import slot_row_count, tag_slot_counts
from app.services import instruments as instruments_service
from app.services import invitations as invitations_service
from app.services.text import pluralize
from app.services import relationships as relationships_service


@dataclass
class SetupRow:
    label: str
    value: str
    manage_url: str
    manage_disabled: bool = False
    manage_disabled_reason: str | None = None


def build_setup_rows(
    db: Session, review_session: ReviewSession
) -> list[SetupRow]:
    """Rows for the Session setup card on session detail."""
    sid = review_session.id
    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    relationship_count = relationships_service.existing_count(db, sid)
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == sid)
        ).scalars()
    )
    instrument_count = len(instruments)
    if instrument_count == 0:
        instruments_value = "Number of instruments: 0"
    else:
        any_open = any(i.accepting_responses for i in instruments)
        all_open = all(i.accepting_responses for i in instruments)
        if all_open:
            status_word = "Open"
        elif not any_open:
            status_word = "Closed"
        else:
            status_word = "Mixed"
        instruments_value = (
            f"Number of instruments: {instrument_count}, Status: {status_word}"
        )

    return [
        SetupRow(
            label="Reviewers",
            value=f"Number of reviewers: {reviewer_count}",
            manage_url=f"/operator/sessions/{sid}/reviewers",
        ),
        SetupRow(
            label="Reviewees",
            value=f"Number of reviewees: {reviewee_count}",
            manage_url=f"/operator/sessions/{sid}/reviewees",
        ),
        SetupRow(
            label="Relationships",
            value=f"Number of relationships: {relationship_count}",
            manage_url=f"/operator/sessions/{sid}/relationships",
        ),
        SetupRow(
            label="Instruments",
            value=instruments_value,
            manage_url=f"/operator/sessions/{sid}/instruments",
        ),
        SetupRow(
            label="Email Invites",
            value="—",
            manage_url=f"/operator/sessions/{sid}/setup-invite",
        ),
    ]


@dataclass
class SessionStatusPills:
    """Counts shown on the standardized session-level status row
    (rendered by ``partials/session_setup_status_row.html``). The
    same numbers / flags appear on every session-scoped page so
    the chrome reads as a single contract."""

    reviewer_count: int
    reviewee_count: int
    relationship_count: int
    observer_count: int
    assignment_count: int
    instrument_count: int
    instruments_configured: int
    """How many of ``instrument_count`` pass
    ``instruments.is_configured`` — at least one visible response field
    and all three Band 1 links touched. The status row reports both, so
    an instrument that exists but cannot yet be answered stops reading
    as done (2026-09-07). Always ``<= instrument_count``."""

    email_invites_set_up: bool
    invitations_state: str
    """One of ``"not_created"`` / ``"not_sent"`` / ``"partial_sent"`` /
    ``"all_sent"``. Distinguishes the two flavours of pre-send (no
    ``Invitation`` rows at all vs. rows generated but no outbox email
    delivered yet) so the chrome status strip can read them apart."""
    responses_reportable: bool
    """``True`` iff the session has any response activity at all
    (``responses_drafts > 0`` or ``responses_submitted > 0``) — the Responses
    pill then reports its counts (see ``responses_label``). ``False`` (pill
    reads ``Awaiting``) only while there are no responses yet. Data-driven, not
    lifecycle-driven: a session reverted to draft after responses came in still
    reports the numbers."""
    responses_drafts: int
    """Number of **in-progress reviews** — ``include`` assignments in the
    session that have at least one saved response but **no** submitted one
    (all ``submitted_at`` still null). Mutually exclusive per assignment with
    ``responses_submitted``. Always computed."""
    responses_submitted: int
    """Number of **submitted reviews** — ``include`` assignments in the
    session with at least one response bearing a ``submitted_at`` — reported
    over ``reviewee_count`` (reviewee-centric, matching the Responses page).
    Always computed."""

    @property
    def responses_label(self) -> str:
        """Composed Responses-pill text: ``<n> drafts / <m> submitted /
        <reviewees>``, omitting whichever of drafts / submitted is zero, or
        ``"Awaiting"`` when there is no response activity at all."""
        if not self.responses_reportable:
            return "Awaiting"
        parts: list[str] = []
        if self.responses_drafts:
            parts.append(
                f"{self.responses_drafts} "
                f"{pluralize(self.responses_drafts, 'draft')}"
            )
        if self.responses_submitted:
            parts.append(f"{self.responses_submitted} submitted")
        parts.append(str(self.reviewee_count))
        return " / ".join(parts)


_INVITATION_STATES: tuple[str, ...] = (
    "not_created",
    "not_sent",
    "partial_sent",
    "all_sent",
)


def _invitations_state(db: Session, session_id: int) -> str:
    """Compute the chrome-strip ``invitations`` pill state.

    ``not_created`` — zero ``Invitation`` rows for the session.
    ``not_sent`` — invitations exist; no reviewer has a ``sent``
      outbox row for their invitation yet.
    ``partial_sent`` — at least one but not every reviewer has a
      ``sent`` outbox row.
    ``all_sent`` — every reviewer with an invitation has a ``sent``
      outbox row.
    """
    invitation_reviewer_ids: set[int] = set(
        db.execute(
            select(Invitation.reviewer_id).where(
                Invitation.session_id == session_id
            )
        ).scalars()
    )
    if not invitation_reviewer_ids:
        return "not_created"
    sent_reviewer_ids: set[int] = set(
        db.execute(
            select(EmailOutbox.reviewer_id).where(
                EmailOutbox.session_id == session_id,
                EmailOutbox.kind == invitations_service.INVITATION_KIND,
                EmailOutbox.status == "sent",
                EmailOutbox.reviewer_id.is_not(None),
            )
        ).scalars()
    )
    if not sent_reviewer_ids:
        return "not_sent"
    if sent_reviewer_ids >= invitation_reviewer_ids:
        return "all_sent"
    return "partial_sent"


def session_status_pills(
    db: Session, review_session: ReviewSession
) -> SessionStatusPills:
    sid = review_session.id
    # Responses pill: "<n> drafts / <m> submitted / <reviewees>", omitting
    # whichever of drafts / submitted is zero, or "Awaiting" while there is no
    # response activity at all. Gate is data-driven, not lifecycle-driven — a
    # session reverted to draft after responses came in keeps reporting the
    # numbers. Both aggregates run on every session page (reviewee-centric,
    # counting distinct include-assignments = "reviews").
    responses_submitted = db.execute(
        select(func.count(distinct(Response.assignment_id)))
        .select_from(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.session_id == sid,
            Assignment.include.is_(True),
            Response.submitted_at.is_not(None),
        )
    ).scalar_one()
    responses_with_any = db.execute(
        select(func.count(distinct(Response.assignment_id)))
        .select_from(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.session_id == sid,
            Assignment.include.is_(True),
        )
    ).scalar_one()
    # Drafts = assignments with saved responses but none submitted.
    responses_drafts = responses_with_any - responses_submitted
    responses_reportable = responses_with_any > 0
    instrument_total, instruments_configured = (
        instruments_service.configured_counts(db, sid)
    )
    return SessionStatusPills(
        reviewer_count=csv_imports.existing_reviewer_count(db, sid),
        reviewee_count=csv_imports.existing_reviewee_count(db, sid),
        relationship_count=relationships_service.existing_count(db, sid),
        observer_count=csv_imports.existing_observer_count(db, sid),
        assignment_count=assignments.existing_count(db, sid),
        instrument_count=instrument_total,
        instruments_configured=instruments_configured,
        # The Email Invites editor lands in Segment 15 — for now no
        # session is "set up" yet. When the editor ships, swap this
        # for a real check (e.g. a non-empty email template row).
        email_invites_set_up=False,
        invitations_state=_invitations_state(db, sid),
        responses_reportable=responses_reportable,
        responses_drafts=responses_drafts,
        responses_submitted=responses_submitted,
    )


def chip_slots(
    presence: dict[str, bool], *, prefix: str
) -> dict[str, bool]:
    """Re-key a ``{"tag_1": bool, ...}`` presence map to the chip slot
    names a page's markup actually uses.

    The column-visibility primitive knows no slot vocabulary — it
    toggles ``col-hidden-{slot}`` for whatever slot a chip names — so
    each page picks its own. The Setup rosters, Invitations and
    Responses use ``tag-1``..``tag-3``; Assignments groups nine slots
    as ``rt1``..``rt3`` / ``et1``..``et3`` / ``p1``..``p3``. Both
    shapes are ``prefix`` + the slot number, which is why one mapper
    covers all six (Segment 19I Item 12 rung 2).

    Templates then read a flag instead of computing one. Before this,
    six templates each scanned their own row list with ``selectattr``
    — the divergence that let every one of them disagree with the
    roster.
    """
    return {
        f"{prefix}{key.removeprefix('tag_')}": value
        for key, value in presence.items()
    }


@dataclass(frozen=True)
class ColumnReadout:
    """One `Populated columns` chip: the column's operator-facing name and
    how many rows of the roster carry a value in it."""

    slot: str
    label: str
    count: int


@dataclass(frozen=True)
class RosterColumnState:
    """The roster index row's chips **and** the preview table's
    column-visibility flags, from one set of queries.

    They answer the same predicate — ``col_data["tag-n"]`` is exactly
    ``counts["tag_n"] > 0`` — so asking twice would be two round trips
    for one fact, and would leave a window where a concurrent delete
    renders a chip reading ``Tag 1 (0)`` (19P.1).
    """

    readouts: list[ColumnReadout]
    col_data: dict[str, bool]


def reviewer_column_state(
    db: Session, review_session: ReviewSession
) -> RosterColumnState:
    """Populated-column chips and visibility flags for the Reviewers roster.

    Identity columns (`Name`, `Email`) are always listed — they are
    required by the CSV contract, so a zero there is itself worth
    seeing. `Profile` and each tag slot appear only when populated,
    which is the gate the column chips already used.

    Tag labels come from ``field_labels.resolve_pair``, the same
    resolver the preview table's own column headers read, so the index
    cannot disagree with the table beneath it. The identity labels are
    literals because ``field_labels.upsert`` refuses an identity slot —
    the built-in default is the only string either surface can render,
    and going through the resolver for it would suggest otherwise.
    (`Profile` is renamable, so it does go through the resolver.)

    **`Profile` was missing until 19P.3 rung 5c.** 19P.1 wrote this
    function Reviewers-shaped and deliberately guessed nothing, leaving
    the generalizing to Observers at 19P.2; `reviewee_column_state`
    then grew a profile readout and this one never did, which is an
    omission rather than a decision. The reviewer roster carries
    `profile_link` and the table renders a `Profile` column from it on
    exactly this rule.
    """
    sid = review_session.id
    counts = tag_slot_counts(db, session_id=sid, model=Reviewer)
    profile_count = slot_row_count(
        db, session_id=sid, column=Reviewer.profile_link
    )
    readouts = [
        ColumnReadout(
            slot="name",
            label="Name",
            count=slot_row_count(db, session_id=sid, column=Reviewer.name),
        ),
        ColumnReadout(
            slot="email",
            label="Email",
            count=slot_row_count(db, session_id=sid, column=Reviewer.email),
        ),
    ]
    if profile_count > 0:
        readouts.append(
            ColumnReadout(
                slot="profile",
                label=field_labels_service.resolve_pair(
                    review_session, "reviewer", "profile_link"
                ).friendly,
                count=profile_count,
            )
        )
    for n in (1, 2, 3):
        if counts[f"tag_{n}"] == 0:
            continue
        readouts.append(
            ColumnReadout(
                slot=f"tag-{n}",
                label=field_labels_service.resolve_pair(
                    review_session, "reviewer", f"tag_{n}"
                ).friendly,
                count=counts[f"tag_{n}"],
            )
        )
    return RosterColumnState(
        readouts=readouts,
        col_data={f"tag-{n}": counts[f"tag_{n}"] > 0 for n in (1, 2, 3)}
        | {"profile": profile_count > 0},
    )


def observer_column_state(
    db: Session, review_session: ReviewSession
) -> RosterColumnState:
    """Populated-column chips and visibility flags for the Observers roster.

    The second caller `reviewer_column_state` was written waiting for
    (19P.2 rung 6), and it settles what actually generalizes: **the
    readouts mirror the columns the preview table renders**, so the
    index cannot disagree with the table beneath it.

    On Reviewers that resolves to identity plus *populated* tag slots,
    because an unpopulated tag column is hidden there. On Observers it
    resolves to all three, because none are hidden — this page has one
    fixed tag slot which always renders and no column chips at all
    (19P.2 rung 3). So the rule is the same sentence; the two pages
    differ because their tables do.

    `Tag`, not a resolved friendly label: Observers carries no
    `_field_labels_editor`, so its `<th>` is a literal string, and a
    resolver call here would invent a label the table never shows. The
    digit went with the move (author's call, 19P.2 rung 6) — this page
    has exactly one tag slot, so `Tag1` numbered a series of one. The
    CSV column stays `ObserverTag1`, being an identifier in a file
    contract rather than a display label.

    ``col_data`` is empty for the same reason: no chips are rendered on
    this page, so there are no visibility flags to answer.
    """
    sid = review_session.id
    return RosterColumnState(
        readouts=[
            ColumnReadout(
                slot="name",
                label="Name",
                count=slot_row_count(
                    db, session_id=sid, column=Observer.display_name
                ),
            ),
            ColumnReadout(
                slot="email",
                label="Email",
                count=slot_row_count(
                    db, session_id=sid, column=Observer.email
                ),
            ),
            ColumnReadout(
                slot="tag-1",
                label="Tag",
                count=slot_row_count(
                    db, session_id=sid, column=Observer.tag_1
                ),
            ),
        ],
        col_data={},
    )


def reviewee_column_state(
    db: Session, review_session: ReviewSession
) -> RosterColumnState:
    """Populated-column chips and visibility flags for the Reviewees roster.

    The rule `observer_column_state` settled — **the readouts mirror the
    columns the preview table renders** — applied to the page with the
    most columns of the four. So identity (`Name`, `Email`) always, then
    `Profile` and each tag slot **only where populated**.

    Chips carry the field labels, not the table's headings: the `<th>`s
    read `Email / Identifier` and `Profile link`, the chips `Email` and
    `Profile`, because both come from `field_labels` and an operator who
    renames a field sees the rename in both places.

    "Only where populated" is this helper's own `count > 0`, deliberately
    NOT the template's `show_*` flags — those are `edit_mode or
    col_data[...]`, so in edit mode the table shows an empty column that
    the index correctly declines to list as populated.

    `Profile` is the one non-tag optional column on any roster page,
    which is why it is asked for directly rather than bending
    `tag_slot_counts` into a general shape for a single caller — the same
    reason the `col_data` map already treats it specially.
    """
    sid = review_session.id
    counts = tag_slot_counts(db, session_id=sid, model=Reviewee)
    profile_count = slot_row_count(
        db, session_id=sid, column=Reviewee.profile_link
    )
    readouts = [
        ColumnReadout(
            slot="name",
            label=field_labels_service.resolve_pair(
                review_session, "reviewee", "name"
            ).friendly,
            count=slot_row_count(db, session_id=sid, column=Reviewee.name),
        ),
        ColumnReadout(
            slot="email",
            label=field_labels_service.resolve_pair(
                review_session, "reviewee", "email_or_identifier"
            ).friendly,
            count=slot_row_count(
                db, session_id=sid, column=Reviewee.email_or_identifier
            ),
        ),
    ]
    if profile_count > 0:
        readouts.append(
            ColumnReadout(
                slot="profile",
                label=field_labels_service.resolve_pair(
                    review_session, "reviewee", "profile_link"
                ).friendly,
                count=profile_count,
            )
        )
    for n in (1, 2, 3):
        if counts[f"tag_{n}"] == 0:
            continue
        readouts.append(
            ColumnReadout(
                slot=f"tag-{n}",
                label=field_labels_service.resolve_pair(
                    review_session, "reviewee", f"tag_{n}"
                ).friendly,
                count=counts[f"tag_{n}"],
            )
        )
    return RosterColumnState(
        readouts=readouts,
        col_data={f"tag-{n}": counts[f"tag_{n}"] > 0 for n in (1, 2, 3)}
        | {"profile": profile_count > 0},
    )


def relationship_column_state(
    db: Session, review_session: ReviewSession
) -> RosterColumnState:
    """Populated-column chips and visibility flags for the Relationships
    roster.

    Same rule as the other three — the readouts mirror the columns the
    table renders — with **one column class this page has and they do
    not**, which the rule cannot reach.

    `Reviewer` and `Reviewee` are `reviewer_id` / `reviewee_id`:
    **non-nullable integer foreign keys**. A readout answers "how many
    rows carry a value in this column", and for a column that cannot be
    without one the question is malformed — the answer is the roster
    total by construction, which the readout beside it already states.

    It is also not askable with the helper that answers it.
    `slot_row_count` is a TEXT predicate — `column IS NOT NULL AND
    column != ''` — and Postgres refuses `integer <> character varying`
    outright:

        ERROR: operator does not exist: integer <> character varying

    SQLite compares across types without complaint, so the first version
    of this function passed the whole suite locally and turned the
    `ci-postgres` job red. Exactly the dialect gap `CLAUDE.md` warns
    about, met in a query rather than a migration.

    So this page lists its pair-context tags and nothing else, and on an
    empty roster its readout list is genuinely empty — which makes the
    chip row's `{% else %}` ("none yet") reachable HERE and nowhere else,
    since the other three always emit identity entries.
    """
    sid = review_session.id
    counts = tag_slot_counts(db, session_id=sid, model=Relationship)
    readouts = [
        ColumnReadout(
            slot=f"tag-{n}",
            label=field_labels_service.resolve_pair(
                review_session, "pair_context", str(n)
            ).friendly,
            count=counts[f"tag_{n}"],
        )
        for n in (1, 2, 3)
        if counts[f"tag_{n}"] > 0
    ]
    return RosterColumnState(
        readouts=readouts,
        col_data={f"tag-{n}": counts[f"tag_{n}"] > 0 for n in (1, 2, 3)},
    )


@dataclass(frozen=True)
class MissingRoster:
    """One roster a relationship needs before it can exist: the Setup
    page's URL slug and the name the session nav gives it."""

    slug: str
    label: str


@dataclass(frozen=True)
class RelationshipPrerequisites:
    """Which of the two rosters a relationship depends on are empty.

    A `Relationship` row names one `Reviewer` and one `Reviewee` through
    non-nullable foreign keys, so with either roster empty there is no
    pair to make: `Add new` is inactive and every row of an uploaded CSV
    fails validation naming the side that is missing — *"Unknown reviewer
    … import reviewers first"* or *"Unknown reviewee … import reviewees
    first"*, the two branches `relationships.parse_relationship_csv`
    checks in that order.

    The page had that fact twice and stated it once, in a `title=`
    attribute on the disabled button — invisible to anyone not hovering,
    which is how the author came to be looking at an inactive `Add new`
    over the words *"Upload a CSV or add a row to get started"* and
    unable to tell why (19O.5 rung 4). `satisfied` is now the single
    answer both surfaces read, so the button and the empty state cannot
    disagree about whether a relationship can be made.
    """

    missing: tuple[MissingRoster, ...]

    @property
    def satisfied(self) -> bool:
        return not self.missing

    @property
    def roster_noun(self) -> str:
        """`roster` or `rosters`, for the number missing."""
        return "rosters" if len(self.missing) > 1 else "roster"

    @property
    def empty_state_clause(self) -> str:
        """The verb phrase closing the empty state's first sentence.

        The template renders the roster names itself, because each is a
        link and markup does not belong in a view module — but the
        number agreement does, beside the tooltip's. Both were spelled
        out separately at first, in Python and in Jinja, so the two
        surfaces shared *which* roster was missing and not the grammar
        for saying so; a cold read caught it.
        """
        return (
            "rosters both have rows"
            if len(self.missing) > 1
            else "roster has rows"
        )

    @property
    def add_disabled_title(self) -> str:
        """The disabled `Add new`'s tooltip, naming the roster to fix.

        It read *"Add a reviewer and a reviewee first — a relationship
        needs both"* regardless of which roster was empty, so an
        operator with two hundred reviewers and no reviewees was told to
        add a reviewer. Derived from the same `missing` the empty state
        renders, so the two cannot drift; empty when nothing is missing,
        where the template renders the live button instead.
        """
        if not self.missing:
            return ""
        names = " and ".join(roster.label for roster in self.missing)
        return (
            f"Add rows to the {names} {self.roster_noun} first — "
            "a relationship needs one of each."
        )


def relationship_prerequisites(
    *, has_reviewers: bool, has_reviewees: bool
) -> RelationshipPrerequisites:
    """The two rosters a relationship depends on, in nav order.

    Order is `Reviewers` then `Reviewees` because that is the order the
    session nav and the Guide put them in, and because a relationship
    CSV names the reviewer first. Both booleans count **every** row,
    active or not, matching `list_reviewers` / `list_reviewees`: an
    inactive reviewer is still a reviewer a relationship can point at.
    """
    missing: list[MissingRoster] = []
    if not has_reviewers:
        missing.append(MissingRoster(slug="reviewers", label="Reviewers"))
    if not has_reviewees:
        missing.append(MissingRoster(slug="reviewees", label="Reviewees"))
    return RelationshipPrerequisites(missing=tuple(missing))
