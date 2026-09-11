"""Coverage / staleness / counts + roster queries.

Read-only (with one destructive tail — ``delete_all_assignments``)
summaries the Validate page, the Workflow card, and the Assignments
page consume. Writes nothing apart from the explicit
``delete_all_assignments`` destructive op.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    case,
    collate,
    String,
    cast,
    false as sa_false,
    func,
    literal,
    nullslast,
    or_,
    select,
)
from sqlalchemy.orm import Session, aliased, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import audit, session_lifecycle as lifecycle
from app.services._queries import session_scoped, slot_has_data


PAIR_PREVIEW_LIMIT = 200


def reviewer_fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of reviewer fields that hold at least one value."""
    labels: list[str] = []
    has_any = (
        db.execute(
            session_scoped(Reviewer.id, session_id).limit(1)
        ).first()
        is not None
    )
    if has_any:
        labels.extend(["ReviewerName", "ReviewerEmail"])
    for slot in (1, 2, 3):
        if slot_has_data(
            db, session_id=session_id, column=getattr(Reviewer, f"tag_{slot}")
        ):
            labels.append(f"ReviewerTag{slot}")
    return labels


def reviewee_fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of reviewee fields that hold at least one value."""
    labels: list[str] = []
    has_any = (
        db.execute(
            session_scoped(Reviewee.id, session_id).limit(1)
        ).first()
        is not None
    )
    if has_any:
        labels.extend(["RevieweeName", "RevieweeEmail"])
    if slot_has_data(
        db, session_id=session_id, column=Reviewee.profile_link
    ):
        labels.append("PhotoLink")
    for slot in (1, 2, 3):
        if slot_has_data(
            db, session_id=session_id, column=getattr(Reviewee, f"tag_{slot}")
        ):
            labels.append(f"RevieweeTag{slot}")
    return labels


def assignment_fields_with_data(db: Session, session_id: int) -> list[str]:
    """CSV column names of assignment fields that hold at least one value.

    Pair-context columns (``PairContextN``) reflect the post-15D
    state — values come from the ``relationships`` table now,
    not the retired ``Assignment.context`` JSON column. The
    ``AssignmentContextN`` family retired entirely in 15D PR 6b
    (operator-typed via the manual CSV only; manual CSV no longer
    writes context after the column drop).
    """

    labels: list[str] = []
    has_any = (
        db.execute(
            session_scoped(Assignment.id, session_id).limit(1)
        ).first()
        is not None
    )
    if not has_any:
        return labels
    labels.extend(["ReviewerEmail", "RevieweeEmail", "IncludeAssignment"])
    for slot in (1, 2, 3):
        if slot_has_data(
            db,
            session_id=session_id,
            column=getattr(Relationship, f"tag_{slot}"),
        ):
            labels.append(f"PairContext{slot}")
    return labels


def display_source_presence(db: Session, session_id: int) -> dict[str, bool]:
    """Composed view: which display-source CSV column names are populated.

    Reuses the three per-table helpers so we don't run a parallel set of
    queries dedicated to the instruments page.
    """
    fields = (
        set(reviewer_fields_with_data(db, session_id))
        | set(reviewee_fields_with_data(db, session_id))
        | set(assignment_fields_with_data(db, session_id))
    )
    return {key: True for key in fields}


def get_or_create_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    """Return the session's default instrument, creating it if missing.

    Thin alias for ``app.services.instruments.ensure_default_instrument``;
    kept here as the seam ``replace_assignments`` uses to pick the target
    instrument for newly generated rows.
    """
    from app.services.instruments import ensure_default_instrument

    return ensure_default_instrument(db, review_session)


def existing_count(
    db: Session,
    session_id: int,
    *,
    instrument_id: int | None = None,
) -> int:
    """Count ``Assignment`` rows for the session, optionally scoped to
    a single instrument.
    """
    stmt = session_scoped(Assignment.id, session_id)
    if instrument_id is not None:
        stmt = stmt.where(Assignment.instrument_id == instrument_id)
    return len(db.execute(stmt).all())


def included_count_per_instrument(
    db: Session, session_id: int
) -> dict[int, int]:
    """Materialised ``Assignment`` row count keyed by
    ``instrument_id``, restricted to rows where ``include=True``.

    Drives the per-instrument **Included** count on the Assignments
    page status table — the counterpart of
    :func:`existing_count_per_instrument`, which surfaces the total
    row count regardless of ``include``.
    """
    rows = db.execute(
        session_scoped(
            Assignment.instrument_id, session_id
        ).add_columns(func.count(Assignment.id))
        .where(Assignment.include.is_(True))
        .group_by(Assignment.instrument_id)
    ).all()
    return {instrument_id: count for instrument_id, count in rows}


def existing_count_per_instrument(
    db: Session, session_id: int
) -> dict[int, int]:
    """Materialised ``Assignment`` row count keyed by ``instrument_id``.

    Drives the per-instrument **Generated** count on the Slice 3a
    Assignments page status blocks. Instruments with zero rows
    (never generated, or wiped after a roster edit) are absent from
    the dict — callers default-to-zero on lookup.
    """
    rows = db.execute(
        session_scoped(
            Assignment.instrument_id, session_id
        ).add_columns(func.count(Assignment.id))
        .group_by(Assignment.instrument_id)
    ).all()
    return {instrument_id: count for instrument_id, count in rows}


def compute_staleness(
    rule_id: int | None,
    eligible_count: int,
    generated_count: int,
) -> bool:
    """Return ``True`` when the instrument is pinned but its
    materialised pair count diverges from what the engine would
    produce now. ``False`` when no rule is pinned or counts match.

    Catches: never-generated pinned instruments
    (``eligible > 0``, ``generated == 0``), instruments whose
    pinned rule changed post-Generate, instruments whose roster /
    relationships changed post-Generate. The view-shape
    ``InstrumentStatusBlock.is_stale`` field, the per-page
    ``any_stale`` aggregate, and the ``instruments.stale_generated``
    validation rule all share this one definition.
    """
    return rule_id is not None and eligible_count != generated_count


def latest_generated_event_per_instrument(
    db: Session, session_id: int
) -> dict[int, Any]:
    """Latest ``assignments.generated`` ``AuditEvent`` keyed by
    ``refs.instrument_id`` for the given session.

    Reads only events with an integer ``refs.instrument_id`` slot —
    pre-Slice-1 aggregated events (no instrument scope) are skipped.
    Drives the "last generated …" timestamp on the per-instrument
    status blocks introduced in Slice 3a.
    """
    from app.db.models import AuditEvent

    events = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == session_id,
            AuditEvent.event_type == "assignments.generated",
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).scalars()
    latest: dict[int, AuditEvent] = {}
    for event in events:
        detail = event.detail or {}
        refs = detail.get("refs") or {}
        instrument_id = refs.get("instrument_id")
        if not isinstance(instrument_id, int):
            continue
        # First seen wins — events are pre-sorted desc by created_at.
        latest.setdefault(instrument_id, event)
    return latest


def list_reviewers(db: Session, session_id: int) -> list[Reviewer]:
    return list(
        db.execute(
            session_scoped(Reviewer, session_id).order_by(Reviewer.id)
        ).scalars()
    )


def list_reviewees(db: Session, session_id: int) -> list[Reviewee]:
    return list(
        db.execute(
            session_scoped(Reviewee, session_id).order_by(Reviewee.id)
        ).scalars()
    )


def _tag_matches(term: str, *columns):
    """Whole-value tag predicates for ``term`` (Segment 19I Item 7).

    The tag half of Item 1's per-column rule, expressed in SQL:
    **text matches by substring, tags by whole value**, both
    case-insensitive and ignoring surrounding whitespace. Whole-value
    is what keeps ``Team A`` from dragging in ``Team A2``; substring
    on names is what makes a partial name useful.

    Returns ``[]`` for an empty term so a whitespace-only search
    cannot match every row whose tag slot is blank.

    **The rule lives twice.** The roster Setup pages run it in Python
    over a loaded list (``app/web/views/_filters.py::_matches_row``);
    this page runs it in SQL, because ``count_pairs`` and the 200-row
    cap both run in the query and the ``Showing N of M`` count keeps
    its meaning. ``tests/integration/test_assignments_search_tags.py``
    holds one table of cases against both paths so the two cannot
    drift apart silently.

    Known limit of the second expression: Python ``str.casefold`` and
    SQL ``lower`` agree on ASCII but not everywhere (``ß`` folds to
    ``ss`` in Python, stays ``ß`` in SQL). The conformance table is
    ASCII, so a non-ASCII tag is the one place the two rules could
    still disagree.
    """
    folded = term.strip().casefold()
    if not folded:
        return []
    return [func.lower(func.trim(column)) == folded for column in columns]


def _apply_status(stmt, status: str):
    """Filter a pairs query by `Assignment.include` (Segment 19I Item
    9).

    `include` is the boolean the Assignments strip's **Inactivate** /
    **Activate** buttons flip, and dimmed rows already show it — it
    was visible and unfilterable, so an operator could inactivate in
    bulk and have no way to list the result back.

    `all`, and anything unrecognised, falls through to everything —
    the roster pages' own rule (`views/_filters.py`). `is_(True)`
    rather than `== True` keeps the SQL portable: `IS true` is what
    Postgres wants, and `CLAUDE.md` records `= 1` as one of the
    SQLite-permissive forms that has bitten this repo.
    """
    if status == "active":
        return stmt.where(Assignment.include.is_(True))
    if status == "inactive":
        return stmt.where(Assignment.include.is_(False))
    return stmt


def _apply_pair_search(
    stmt,
    search: str,
    search_by: str = "all",
    picked_reviewer_handle: str | None = None,
    picked_reviewee_handle: str | None = None,
):
    """Add the reviewer / reviewee free-text filter to a pairs query.

    Name and handle match by **case-insensitive substring** (Segment
    13C); ``tag_1..3`` on each side match by **whole value** (Segment
    19I Item 7 — they were invisible to this search until then, so a
    tag an operator could see on the roster pages returned nothing
    here). ``search_by`` scopes which side is matched: ``reviewer`` /
    ``reviewee`` match only that side, including that side's tags;
    anything else (``all``) matches either.

    Tags scope for free because they belong to the reviewer and the
    reviewee individually — which is why this page needs no separate
    tag control.
    """
    term = f"%{search.strip()}%"
    stmt = stmt.join(
        Reviewer, Assignment.reviewer_id == Reviewer.id
    ).join(Reviewee, Assignment.reviewee_id == Reviewee.id)

    # Segment 19I Item 9 — a typeahead label the operator picked
    # resolves to that side's handle, matched by **equality**. Without
    # this the pick returns nothing at all: `%Ana Lim
    # (ana@example.edu)%` is a substring of no name and no email, so
    # the substring path below yields zero rows. Equality is also what
    # separates `ana@example.edu` from `ana2@example.edu`, which a
    # name substring cannot.
    if picked_reviewer_handle or picked_reviewee_handle:
        sides = []
        if picked_reviewer_handle:
            sides.append(
                (
                    "reviewer",
                    func.lower(func.trim(Reviewer.email))
                    == picked_reviewer_handle.strip().casefold(),
                )
            )
        if picked_reviewee_handle:
            sides.append(
                (
                    "reviewee",
                    func.lower(func.trim(Reviewee.email_or_identifier))
                    == picked_reviewee_handle.strip().casefold(),
                )
            )
        allowed = [
            clause for side, clause in sides if search_by in ("all", side)
        ]
        if not allowed:
            # The pick names a side the scope excludes — nothing
            # matches, rather than falling back to a substring search
            # that would ignore the operator's scope.
            return stmt.where(sa_false())
        return stmt.where(or_(*allowed))

    reviewer_match = or_(
        Reviewer.name.ilike(term),
        Reviewer.email.ilike(term),
        *_tag_matches(
            search, Reviewer.tag_1, Reviewer.tag_2, Reviewer.tag_3
        ),
    )
    reviewee_match = or_(
        Reviewee.name.ilike(term),
        Reviewee.email_or_identifier.ilike(term),
        *_tag_matches(
            search, Reviewee.tag_1, Reviewee.tag_2, Reviewee.tag_3
        ),
    )
    if search_by == "reviewer":
        return stmt.where(reviewer_match)
    if search_by == "reviewee":
        return stmt.where(reviewee_match)
    return stmt.where(or_(reviewer_match, reviewee_match))


# --------------------------------------------------------------------- #
# Sorting the pair list in SQL — Segment 19J.5 rung 4.
#
# Until rung 4 the Assignments page fetched 200 rows and sorted *those*
# in Python, via ``views.apply_cookie_sort``. That was invisible while
# 200 was all an operator could ever see; paging makes it a lie, because
# page 2 would be sorted within page 2. So the sort moves into the
# query, where it can order the whole matching set before the window is
# cut.
#
# The contract to preserve is ``apply_cookie_sort``'s, exactly — the
# operator's rows must not reshuffle on the day this lands:
#
#   1. an empty string is *not* a value; it collapses to NULL
#      (``NULLIF(col, '')``);
#   2. NULL sorts **last** whichever direction the column is sorted;
#   3. text compares by code point, the way Python's ``<`` does;
#   4. ties fall through to the next key, then to a stable order.
#
# Rule 3 is the one with teeth. Measured 2026-09-11 on Postgres 16:
# under a locale-aware collation the same seven names order
# ``_edge | alpha | ana lim | Ana Lim | Bravo | charlie | Delta``, and
# under ``C`` (and SQLite's default BINARY) they order
# ``Ana Lim | Bravo | Delta | _edge | alpha | ana lim | charlie`` — the
# second being what this app has always rendered. The ``ci-postgres``
# container initialises as ``C.UTF-8``, so an unqualified ORDER BY would
# have passed CI and reordered every sorted table on a production
# database with a locale-aware collation. Hence the explicit collation
# below, applied on Postgres only: SQLite's default already is rule 3.
# --------------------------------------------------------------------- #


def _code_point(db: Session, expression):
    """Order ``expression`` by code point on either dialect.

    SQLite's default collation is BINARY, which already is code-point
    order. Postgres follows its database collation, which may not be —
    see the note above.
    """
    if db.get_bind().dialect.name == "postgresql":
        return collate(expression, "C")
    return expression


def _instrument_label_sql(instrument):
    """The SQL form of ``instruments._instrument_label``: the trimmed
    ``short_label`` when it holds anything, else ``Instrument_{id}``.

    Kept beside the Python original rather than derived from it,
    because there is no way to derive it — and pinned against it by
    ``tests/unit/test_pair_sort_sql.py`` so the two cannot drift.
    """
    trimmed = func.trim(func.coalesce(instrument.short_label, ""))
    return case(
        (trimmed != "", trimmed),
        # ``||`` on both dialects: SQLite only grew a ``concat()``
        # function in 3.44, and the operator has always worked.
        else_=literal("Instrument_") + cast(instrument.id, String),
    )


def _pair_sort_order(db: Session, stmt, sort: list[tuple[str, str]] | None):
    """Translate a cookie sort spec into ``ORDER BY``, joining only what
    the active keys need — an unsorted page must stay the single-table
    query it was.

    Returns ``(stmt, order_clauses)``. Unknown keys are skipped: the
    route validates them against ``_ASSIGNMENT_SORT_KEYS`` first, and a
    cookie is operator-editable.
    """
    order: list = []
    if not sort:
        return stmt, order

    joined: dict[str, Any] = {}

    def _reviewer():
        if "reviewer" not in joined:
            alias = aliased(Reviewer)
            joined["reviewer"] = alias
            return alias, True
        return joined["reviewer"], False

    def _reviewee():
        if "reviewee" not in joined:
            alias = aliased(Reviewee)
            joined["reviewee"] = alias
            return alias, True
        return joined["reviewee"], False

    for key, direction in sort:
        expression = None

        if key == "reviewer" or key.startswith("reviewer_tag_"):
            alias, fresh = _reviewer()
            if fresh:
                stmt = stmt.outerjoin(
                    alias, Assignment.reviewer_id == alias.id
                )
            column = (
                alias.name
                if key == "reviewer"
                else getattr(alias, f"tag_{key.rsplit('_', 1)[-1]}")
            )
            expression = _code_point(db, func.nullif(column, ""))

        elif key == "reviewee" or key.startswith("reviewee_tag_"):
            alias, fresh = _reviewee()
            if fresh:
                stmt = stmt.outerjoin(
                    alias, Assignment.reviewee_id == alias.id
                )
            column = (
                alias.name
                if key == "reviewee"
                else getattr(alias, f"tag_{key.rsplit('_', 1)[-1]}")
            )
            expression = _code_point(db, func.nullif(column, ""))

        elif key.startswith("pair_tag_"):
            # The pair's own tags live on ``relationships``, and only an
            # *active* relationship contributes them — the Python
            # resolver returned None for any other status, and the rule
            # engine agrees. An assignment with no relationship row, or
            # an inactive one, therefore sorts as NULL: last, which is
            # where it landed before.
            if "relationship" not in joined:
                alias = aliased(Relationship)
                joined["relationship"] = alias
                stmt = stmt.outerjoin(
                    alias,
                    (alias.session_id == Assignment.session_id)
                    & (alias.reviewer_id == Assignment.reviewer_id)
                    & (alias.reviewee_id == Assignment.reviewee_id)
                    & (alias.status == "active"),
                )
            alias = joined["relationship"]
            column = getattr(alias, f"tag_{key.rsplit('_', 1)[-1]}")
            expression = _code_point(db, func.nullif(column, ""))

        elif key == "instrument":
            if "instrument" not in joined:
                alias = aliased(Instrument)
                joined["instrument"] = alias
                stmt = stmt.outerjoin(
                    alias, Assignment.instrument_id == alias.id
                )
            expression = _code_point(
                db, _instrument_label_sql(joined["instrument"])
            )

        elif key == "include":
            # Render-text parity: the Python resolver sorted the strings
            # "no" < "yes", which is False < True. The column is NOT
            # NULL, so null placement never arises.
            expression = Assignment.include

        if expression is None:
            continue

        clause = (
            expression.desc() if direction == "desc" else expression.asc()
        )
        # Rule 2: NULL last in **both** directions — not the default
        # either dialect would pick, and the reason every clause is
        # wrapped rather than only the ascending ones.
        order.append(nullslast(clause))

    return stmt, order


def list_pairs(
    db: Session,
    session_id: int,
    *,
    limit: int = PAIR_PREVIEW_LIMIT,
    offset: int = 0,
    sort: list[tuple[str, str]] | None = None,
    search: str | None = None,
    search_by: str = "all",
    status: str = "all",
    picked_reviewer_handle: str | None = None,
    picked_reviewee_handle: str | None = None,
) -> list[Assignment]:
    """Return saved Assignment rows with reviewer + reviewee + instrument
    eagerly loaded.

    Ordered by the operator's ``sort`` spec when one is given, then
    always by (reviewer_id, reviewee_id, instrument_id) — which matches
    the FullMatrix preview shape, keeps instrument rows next to each
    other within the same pair, and gives the total order that
    ``offset`` needs to be meaningful. ``search`` (when set) filters to rows whose reviewer
    and/or reviewee name / email matches the term, scoped by
    ``search_by`` (``all`` / ``reviewer`` / ``reviewee``).
    """
    stmt = session_scoped(Assignment, session_id).options(
        joinedload(Assignment.reviewer),
        joinedload(Assignment.reviewee),
        joinedload(Assignment.instrument),
    )
    if search and search.strip():
        stmt = _apply_pair_search(
            stmt,
            search,
            search_by,
            picked_reviewer_handle,
            picked_reviewee_handle,
        )
    stmt = _apply_status(stmt, status)
    # Segment 19J.5 rung 4 — the operator's sort is applied here, not
    # over the fetched window, so ``offset`` cuts a page out of the
    # whole ordered set rather than out of an arbitrary 200.
    stmt, sort_order = _pair_sort_order(db, stmt, sort)
    stmt = stmt.order_by(
        # The pair order is the tie-breaker now, and it is what makes
        # paging deterministic: without a total order two pages can
        # show the same row or neither.
        *sort_order,
        Assignment.reviewer_id,
        Assignment.reviewee_id,
        Assignment.instrument_id,
    )
    if offset:
        stmt = stmt.offset(offset)
    return list(db.execute(stmt.limit(limit)).unique().scalars())


def count_pairs(
    db: Session,
    session_id: int,
    *,
    search: str | None = None,
    search_by: str = "all",
    status: str = "all",
    picked_reviewer_handle: str | None = None,
    picked_reviewee_handle: str | None = None,
) -> int:
    """Count saved Assignment rows for the session, optionally
    filtered by the reviewer / reviewee free-text ``search``
    (scoped by ``search_by``)."""
    stmt = session_scoped(Assignment.id, session_id)
    if search and search.strip():
        stmt = _apply_pair_search(
            stmt,
            search,
            search_by,
            picked_reviewer_handle,
            picked_reviewee_handle,
        )
    stmt = _apply_status(stmt, status)
    return len(db.execute(stmt).all())


def delete_all_assignments(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
    instrument_id: int | None = None,
) -> int:
    """Remove ``Assignment`` rows from the session.

    ``instrument_id=None`` (default): clears every row and resets
    ``assignment_mode`` to NULL. ``instrument_id=<id>``: scoped delete
    that leaves rows on other instruments untouched and does NOT
    clear ``assignment_mode``.
    """
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="assignments_deleted_all",
        correlation_id=correlation_id,
    )
    stmt = session_scoped(Assignment, review_session.id)
    if instrument_id is not None:
        stmt = stmt.where(Assignment.instrument_id == instrument_id)
    rows = list(db.execute(stmt).scalars())
    deleted = len(rows)
    for row in rows:
        db.delete(row)
    if instrument_id is None:
        review_session.assignment_mode = None
    db.flush()

    refs: dict[str, int] | None = (
        {"instrument_id": instrument_id} if instrument_id is not None else None
    )
    audit.write_event(
        db,
        event_type="assignments.deleted_all",
        summary=f"Deleted all {deleted} assignments",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(deleted=deleted),
        refs=refs,
        correlation_id=correlation_id,
    )
    db.commit()
    return deleted
