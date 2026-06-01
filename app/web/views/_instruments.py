"""Instruments page view-shapes — operator's per-session
``/operator/sessions/{id}/instruments`` page plus the reviewer-
surface heading + page-button helpers and the per-field render
hints (placeholder / constraint summary).

Slice 6 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns the ``InstrumentHeading`` dataclass + the
``instrument_heading`` builder that drives
the reviewer-surface composition table per
``spec/reviewer-surface.md``, the per-field render hints
(``placeholder_for_field`` / ``constraint_summary_for_field``),
and the operator-page context builder ``build_instruments_context``
that runs the per-request idempotent backfills + state-machine
derivation.

Source range in pre-PR-6 ``_legacy.py``: lines 38-335.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import field_labels
from app.services import instruments as instruments_service
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
from app.services._queries import slot_has_data
from app.services.instruments._field_presets import LIST_PRESETS as _BAND3_LIST_PRESETS
from app.web import breadcrumbs

from ._setup import session_status_pills


# Sentinel value the rule-picker `<select>` posts when the operator
# chose the "— No rule —" option. Anything else is an int that
# resolves to a ``session_rule_sets.id``. Lives at module scope so
# both the template (via the form's hidden input default) and the
# route handler agree on the literal.
RULE_PICKER_NO_RULE_VALUE = ""


@dataclass(frozen=True)
class InstrumentHeading:
    """Title + optional subtitle for the per-instrument heading card.

    Title lands on the H2; subtitle on a `.muted` body-weight `<p>`
    below it inside `.card.rs-instrument-card`, which sits in column 1
    of the per-instrument intro grid (`.rs-intro-grid`). Either or
    both can be ``None`` — the template only renders the heading card
    when ``title`` is truthy.

    Composition rules per `spec/reviewer-surface.md` "Above the table
    — heading + help block":

    | total_count | short_label | description | title | subtitle |
    |---|---|---|---|---|
    | >1 | set     | set       | "#{N}: {short_label}" | description |
    | >1 | set     | unset     | "#{N}: {short_label}" | None |
    | >1 | unset   | set       | "#{N}"                | description |
    | >1 | unset   | unset     | "#{N}"                | None |
    | 1  | set     | set       | "{short_label}"            | description |
    | 1  | set     | unset     | "{short_label}"            | None |
    | 1  | unset   | set       | "{description}" *          | None *     |
    | 1  | unset   | unset     | None                       | None |

    \\* The single-instrument-only-description row preserves the
    legacy heading behaviour (description renders as the H2 text)
    so operators who haven't migrated to ``short_label`` yet don't
    silently lose their per-instrument context. The spec's strict
    reading was "no heading; description shown elsewhere", but
    there's no other display path for ``Instrument.description``
    today; preserving it here is a small spec deviation in service
    of operator continuity.
    """

    title: str | None
    subtitle: str | None


def instrument_heading(
    *, instrument: Instrument, position: int, total_count: int
) -> InstrumentHeading:
    """Build the per-instrument heading title + subtitle for the
    reviewer surface, per the composition table on
    :class:`InstrumentHeading`.
    """
    short = (instrument.short_label or "").strip()
    desc = (instrument.description or "").strip() or None
    if total_count == 1:
        if short:
            return InstrumentHeading(title=short, subtitle=desc)
        if desc:
            # Legacy behaviour preserved — see the docstring's note.
            return InstrumentHeading(title=desc, subtitle=None)
        return InstrumentHeading(title=None, subtitle=None)
    # Multi-instrument: position prefix is the safety-net default.
    if short:
        return InstrumentHeading(title=f"#{position}: {short}", subtitle=desc)
    return InstrumentHeading(title=f"#{position}", subtitle=desc)


def _format_band2_bound(value: float) -> str:
    """Format a Wave-2 ``_inline_min`` / ``_inline_max`` / ``_inline_step``
    float for re-serialisation back into the band2_state JSON
    shape (which carries strings, not numbers). Trim trailing
    ``.0`` so an integer-valued float renders as ``"1"`` not
    ``"1.0"`` — matches what the operator would have typed."""
    if value == int(value):
        return str(int(value))
    return str(value)


def placeholder_for_field(field: InstrumentResponseField) -> str:
    """Short hint shown inside the input box when empty, so reviewers
    know what shape a value should take. Mirrors the RTD's validation
    block; returns ``""`` for List rows or when the validation block is
    incomplete (e.g. an Integer RTD missing ``step``)."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)} to {int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return (
                f"{int(min_)} to {int(max_)}, steps of {int(step)}"
            )
        return f"{min_:.1f} to {max_:.1f}, steps of {step:.1f}"
    return ""


def constraint_summary_for_field(field: InstrumentResponseField) -> str:
    """Short ``min-max[, steps of step]`` summary used in the
    above-table constraint row on the reviewer surface. Distinct from
    ``placeholder_for_field`` (``a to b``) — this one uses the dash
    notation requested for the summary line. Returns ``""`` when the
    validation block is incomplete or absent."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)}-{int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return f"{int(min_)}-{int(max_)}, steps of {int(step)}"
        return f"{min_:.1f}-{max_:.1f}, steps of {step:.1f}"
    # List rows are omitted from the constraint summary — the
    # ``<select>`` already constrains the choice in the input itself.
    return ""


def numeric_column_ch_width(field: InstrumentResponseField) -> int | None:
    """A ``ch``-unit width for a numeric response column.

    Keeps a small-range numeric input (e.g. a 1-5 Rating) from
    sprawling across a fixed-layout group-scoped instrument table.
    Sized to the wider of the header label (plus room for the
    ``required`` mark and the sort button) and the digit span of
    the field's RTD min / max range. Returns ``None`` for
    non-numeric fields — the caller skips the width hint for those.
    """
    if field.data_type not in ("Integer", "Decimal"):
        return None
    validation = field.validation or {}

    def _digits(value: object) -> int:
        if value is None:
            return 0
        if field.data_type == "Integer":
            return len(str(int(value)))
        return len(f"{float(value):g}")

    digit_span = max(
        _digits(validation.get("min")),
        _digits(validation.get("max")),
        1,
    )
    # The header must fit the label, the optional " *" required
    # mark, and the sort button; the input must fit the widest
    # value. The constants pad for cell padding / the sort glyph
    # and want a visual tune.
    header_ch = len(field.label) + (2 if field.required else 0) + 4
    input_ch = digit_span + 3
    return max(header_ch, input_ch)


# Calibration constants for ``textarea_rows_for``. Tuned against
# ``td.rs-textlong { min-width: 14em }`` in ``base.html`` and the
# default proportional sans-serif body font stack. Revisit if the
# font stack or default column width changes.
_DEFAULT_RESPONSE_COL_WIDTH_PX = 224  # 14em @ 16px body font
_PX_PER_CHAR = 8                       # proportional sans-serif average
_TYPICAL_RESPONSE_FRACTION = 0.5       # operators rarely use full max_chars
_MIN_TEXTAREA_ROWS = 2
_MAX_TEXTAREA_ROWS = 8
_MIN_CHARS_PER_ROW = 20                # floor for absurdly narrow columns


def textarea_rows_for(
    max_chars: int | None, column_width_px: int | None
) -> int:
    """Derive a ``rows`` attribute for a String response-field
    textarea on the reviewer surface.

    Sizes the textarea to hold a *typical* response (assumed to
    cluster around 50% of the configured ``max_chars``, not the
    full cap) at the column's current width — so the operator can
    pre-size the input by tightening / widening the column on
    Band 2 of the new-model card without touching another knob.
    Falls back to the default ``td.rs-textlong`` width (14em ≈
    224px) when the operator hasn't dragged the column.

    Clamped to ``[2, 8]`` so single-line String inputs never
    collapse to a 1-row textarea (the reviewer-surface contract
    only emits a textarea when ``max_chars > 100``) and a
    2000-char field doesn't dwarf the page. Reviewers can still
    drag the native textarea corner at runtime — this just sets
    the initial height.
    """
    if max_chars is None or max_chars <= 0:
        return _MIN_TEXTAREA_ROWS
    width = column_width_px or _DEFAULT_RESPONSE_COL_WIDTH_PX
    typical_chars = max_chars * _TYPICAL_RESPONSE_FRACTION
    chars_per_row = max(_MIN_CHARS_PER_ROW, width / _PX_PER_CHAR)
    raw = math.ceil(typical_chars / chars_per_row)
    return max(_MIN_TEXTAREA_ROWS, min(_MAX_TEXTAREA_ROWS, raw))


def _bulk_state(values: list[bool]) -> str:
    """Three-state value for a bulk toggle: ``all-on`` / ``all-off`` / ``mixed``."""
    if not values:
        return "all-off"
    on = sum(1 for v in values if v)
    if on == 0:
        return "all-off"
    if on == len(values):
        return "all-on"
    return "mixed"


# Wave 5 PR 5.1 — ``InstrumentRulePickerOption`` /
# ``InstrumentRulePickerContext`` / ``_build_rule_picker_options`` /
# ``build_instrument_rule_picker_contexts`` retired alongside the
# per-instrument Assignment Rule sub-card. Legacy instruments keep
# any existing ``rule_set_id`` pin (driving generate); they retire
# entirely in PR 5.3.


def _new_model_band2_state(
    db: Session,
    instrument: Instrument,
    *,
    active_reviewees: list[Reviewee],
) -> dict[str, Any]:
    """For the new-model card's Band 2 ("Review Instrument") preview:
    every display field on the instrument whose source slot has data
    somewhere in the session, plus the sample data the client-side
    preview row builder needs to compose a reviewer-surface row.

    Filters out display fields whose underlying source column has no
    populated value in the session — same "Fields with data" UX as
    the Reviewers / Reviewees / Relationships Setup pages (which
    consume the parallel
    :func:`app.services.assignments.reviewee_fields_with_data` family
    over the shared :func:`app.services._queries.slot_has_data`
    primitive).

    ``active_reviewees`` is fetched once per page render and passed
    in by :func:`build_instruments_context` — see Segment 18J Wave 1
    Rec D1.

    Returns a dict with:

    - ``fields`` — one entry per populated display field, each
      carrying ``{key, label, source_type, source_field, value,
      selectable_in_group}``. ``key`` is the canonical
      ``"{source_type}.{source_field}"`` identifier the client uses
      to track selection. ``selectable_in_group`` is ``False`` for
      ``reviewee.email_or_identifier`` / ``reviewee.profile_link``
      and all pair-context tags, mirroring the actual reviewer
      surface's group row (which composes group identity from
      reviewee tag boundary values + member names only).
    - ``sample_names`` — up to
      :data:`~app.web.routes_reviewer._surface.GROUP_MEMBER_NAME_LIMIT`
      reviewee names sorted alphabetically, for the Group-mode
      preview's member-name line.
    - ``sample_extra_count`` — count of active reviewees beyond the
      shown sample names; drives the ``+N more`` suffix.
    """
    # Local import to avoid a top-of-file circular dep (routes import
    # from views).
    from app.web.routes_reviewer._surface import GROUP_MEMBER_NAME_LIMIT

    review_session = instrument.session
    # Respect the operator's last "↻ Refresh preview" pick (stored
    # on band2_state.sample_reviewee_name). Falls back to the first
    # active reviewee by name when the saved sample no longer exists
    # (deleted / deactivated) or when nothing has been refreshed
    # yet.
    saved_sample_name = (
        (instrument.band2_state or {}).get("sample_reviewee_name") or ""
    )
    sample: Reviewee | None = None
    if saved_sample_name:
        sample = next(
            (r for r in active_reviewees if r.name == saved_sample_name),
            None,
        )
    if sample is None and active_reviewees:
        sample = active_reviewees[0]
    # Group-mode partitioning: when the instrument is set to Group
    # mode with reviewee boundary tags, the preview row's member-
    # name list should reflect *one* group (the one the sample
    # reviewee belongs to), not the entire roster. Otherwise the
    # preview falsely shows the whole roster as a single group.
    # Pair-context boundary tags need a specific reviewer's
    # relationships to compute, so they're skipped for the preview
    # — the partition falls back to all reviewees when the only
    # boundary is pair-context-side.
    boundary_pairs = instruments_service.decode_group_kind(
        instrument.group_kind
    )
    reviewee_boundary_fields = [
        field for (src, field) in boundary_pairs if src == "reviewee"
    ]
    if sample is not None and reviewee_boundary_fields:
        sample_key = tuple(
            getattr(sample, field, "") or ""
            for field in reviewee_boundary_fields
        )
        group_members = [
            r
            for r in active_reviewees
            if tuple(
                getattr(r, field, "") or ""
                for field in reviewee_boundary_fields
            )
            == sample_key
        ]
        # Gap 10: intersect with the rule-surviving member-ID set
        # persisted at the last Refresh. The Refresh path runs the
        # engine and writes the surviving IDs onto
        # ``band2_state.sample_group_member_ids`` so the preview
        # member list honours Links 1+2, not just the boundary
        # partition. Falls back to the boundary-only partition when
        # the key is absent (legacy band2_state from before
        # Gap 10 shipped — render reflects the pre-Gap-10 view
        # until the next Refresh writes the new key).
        persisted_member_ids = (instrument.band2_state or {}).get(
            "sample_group_member_ids"
        )
        if isinstance(persisted_member_ids, list) and persisted_member_ids:
            allowed = {int(i) for i in persisted_member_ids if isinstance(i, int)}
            group_members = [r for r in group_members if r.id in allowed]
    else:
        group_members = active_reviewees
    all_names = [r.name for r in group_members]
    sample_names = all_names[:GROUP_MEMBER_NAME_LIMIT]
    sample_extra_count = max(0, len(all_names) - len(sample_names))
    # Roster payload for client-side dynamic partitioning. Lets the
    # Band 2 preview-builder JS re-compute group membership on the
    # fly when the operator picks / changes a Link 3 boundary tag
    # before saving (the server-rendered ``sample_names`` above
    # reflects the SAVED group_kind, not the in-progress edit).
    roster = [
        {
            # ``id`` is consumed by ``partitionedSampleNames`` in
            # instruments_index.html to intersect the boundary
            # partition against the rule-surviving member-ID set
            # (Gap 10). Without it the intersection silently
            # rejects every reviewee and the preview falls back to
            # the unintersected boundary partition.
            "id": r.id,
            "name": r.name,
            "tag_1": r.tag_1 or "",
            "tag_2": r.tag_2 or "",
            "tag_3": r.tag_3 or "",
        }
        for r in active_reviewees
    ]

    # Pills cover every display field that has data — including ones
    # the operator has currently toggled off (visible=False) so the
    # pill remains clickable in edit mode (Gap 1). Selection state is
    # derived from ``visible`` at render time below.
    fields: list[dict[str, Any]] = []
    for f in instrument.display_fields:
        if not _display_field_has_data(db, review_session.id, f):
            continue
        label = field_labels.resolve(
            review_session,
            f.source_type,
            _label_slot(f.source_type, f.source_field),
        )
        value: str | None
        if sample is None:
            value = None
        elif f.source_type == "reviewee":
            raw = getattr(sample, f.source_field, None)
            value = raw if raw else None
        else:
            value = None  # pair_context — needs a relationship to resolve
        fields.append(
            {
                "key": f"{f.source_type}.{f.source_field}",
                "label": label,
                "source_type": f.source_type,
                "source_field": f.source_field,
                "value": value,
                "selectable_in_group": _is_selectable_in_group(
                    f.source_type, f.source_field
                ),
                "display_field_id": f.id,
                "width_px": (instrument.column_widths or {}).get(
                    f"df_{f.id}"
                ),
                "reorderable": not instruments_service.is_locked_display_source(
                    f.source_type, f.source_field
                ),
            }
        )
    identity_width_px = (instrument.column_widths or {}).get("identity")
    # Gap 1: selected_display_keys is derived from
    # ``InstrumentDisplayField.visible`` (the source of truth that
    # the reviewer surface honours), not from the band2_state JSON.
    # The JSON slot stays for back-compat with code that round-trips
    # the dict but is no longer authoritative — set_band2_state
    # writes both together via _sync_display_field_visibility.
    selected_display_keys = {
        f"{f.source_type}.{f.source_field}"
        for f in instrument.display_fields
        if f.visible
    }
    # Wave 3 PR iii — DB rows are the only source of truth for
    # response-field metadata. ``band2_state.response_fields`` JSON
    # retired; PR i's (b)-contract read path is now the unconditional
    # read path. width_px reads from ``column_widths["rf_<id>"]``
    # (migrated out of the JSON entry into the canonical widths dict).
    column_widths_map = instrument.column_widths or {}
    response_fields: list[dict[str, Any]] = []
    for rf in sorted(instrument.response_fields, key=lambda f: f.order):
        data_type_lower = (rf._inline_data_type or "String").lower()
        entry: dict[str, Any] = {
            "id": rf.id,
            "name": rf.label,
            "data_type": data_type_lower,
            "min": ""
            if rf._inline_min is None
            else _format_band2_bound(rf._inline_min),
            "max": ""
            if rf._inline_max is None
            else _format_band2_bound(rf._inline_max),
            "step": ""
            if rf._inline_step is None
            else _format_band2_bound(rf._inline_step),
            "list_options": rf._inline_list_csv or "",
            "selected": rf.visible,
            "required": rf.required,
            "help_text": rf.help_text or "",
            "help_text_visible": rf.help_text_visible,
        }
        width = column_widths_map.get(f"rf_{rf.id}")
        if width is not None:
            entry["width_px"] = width
        response_fields.append(entry)
    # Wave 3 PR i — annotate each entry with ``has_responses`` so
    # the Band 3 template can render the X button disabled for
    # fields with attached reviewer responses (cascade-blocked
    # delete). Segment 18K PR 4 promotes the same query to a
    # GROUP BY count and also surfaces ``response_count`` so the
    # Band 2 chip click handler can name the count in its
    # un-pin confirm dialog. Entries without an id (newly
    # authored, not yet saved) carry ``response_count=0`` /
    # ``has_responses=False``.
    rf_ids_with_id = [
        rf.get("id") for rf in response_fields
        if isinstance(rf, dict) and isinstance(rf.get("id"), int)
    ]
    response_count_by_id: dict[int, int] = {}
    if rf_ids_with_id:
        rows = db.execute(
            select(
                Response.response_field_id,
                func.count(Response.id),
            )
            .where(Response.response_field_id.in_(rf_ids_with_id))
            .group_by(Response.response_field_id)
        ).all()
        response_count_by_id = {fid: count for fid, count in rows}
    for rf in response_fields:
        if isinstance(rf, dict):
            rf_id = rf.get("id")
            count = (
                response_count_by_id.get(rf_id, 0)
                if isinstance(rf_id, int)
                else 0
            )
            rf["response_count"] = count
            rf["has_responses"] = count > 0
    sort_spec = list(instrument.sort_display_fields or [])
    return {
        "fields": fields,
        "sample_names": sample_names,
        "sample_extra_count": sample_extra_count,
        "identity_width_px": identity_width_px,
        "selected_display_keys": selected_display_keys,
        "response_fields": response_fields,
        "roster": roster,
        "sample_reviewee_name": sample.name if sample is not None else "",
        # Rule-surviving group-member IDs from the last Refresh
        # (Gap 10). ``partitionedSampleNames`` in
        # instruments_index.html intersects its boundary-key
        # partition against this set so the client-side rebuild
        # honours Links 1+2 too — without it the JS preview lists
        # every reviewee with the matching boundary tag value,
        # even ones the rule engine actually excluded. Empty list
        # = "no constraint" (legacy band2_state from before the
        # field shipped, or a session whose only boundary is
        # pair-context-side).
        "sample_group_member_ids": list(
            (instrument.band2_state or {}).get(
                "sample_group_member_ids"
            ) or []
        ),
        # Comma-joined list of reviewee-side boundary field names
        # (``tag_1`` / ``tag_2`` / ``tag_3``) so the preview JS can
        # partition in view mode, where the live ``link3_boundary``
        # <select>s aren't reachable as form-field inputs.
        "saved_reviewee_boundary_fields": ",".join(reviewee_boundary_fields),
        # Gap 3 (18J Wave 1) — per-instrument sort spec, shared with
        # the legacy card's hidden-inputs slot.
        # ``[{"display_field_id": N, "dir": "asc|desc"}, ...]`` in
        # cascade order (Segment 13B PR 2 contract).
        "sort_spec": sort_spec,
    }


def _is_selectable_in_group(source_type: str, source_field: str) -> bool:
    """Which display fields the operator can include in the Group-mode
    preview row. Mirrors the actual reviewer surface's group cell
    (``app/web/templates/reviewer/review_surface.html`` ~line 264):
    group identity = boundary tag values + member name list; email,
    profile link, and pair-context tags don't compose meaningfully
    there.
    """
    if source_type != "reviewee":
        return False
    return source_field in {"name", "tag_1", "tag_2", "tag_3"}


def _display_field_has_data(
    db: Session, session_id: int, field: InstrumentDisplayField
) -> bool:
    """``True`` iff the display field's underlying source column has
    at least one populated row in the session. Reuses
    :func:`slot_has_data` for the column-level check; pair-context
    rows are gated on ``status == "active"`` to mirror the rule
    engine's view (the same gate ``_new_model_usable_tags`` applies)."""
    if field.source_type == "reviewee":
        col = getattr(Reviewee, field.source_field, None)
        if col is None:
            return False
        return slot_has_data(db, session_id=session_id, column=col)
    if field.source_type == "pair_context":
        col = getattr(Relationship, f"tag_{field.source_field}", None)
        if col is None:
            return False
        return slot_has_data(
            db, session_id=session_id, column=col, active_only=True
        )
    return False


def _label_slot(source_type: str, source_field: str) -> str:
    """Map a display-field ``source_field`` to the
    ``field_labels.resolve(...)`` slot name. Reviewee fields pass
    through; pair-context strips the ``tag_`` prefix (the registry
    keys pair-context slots as ``"1"`` / ``"2"`` / ``"3"``)."""
    if source_type == "pair_context" and source_field.startswith("tag_"):
        return source_field.split("_", 1)[1]
    return source_field


def _new_model_usable_tags(
    db: Session, review_session: ReviewSession
) -> dict[str, list[tuple[str, str]]]:
    """For the Instrument Builder new-model card: which tag slots are
    populated for the session, paired with their friendly labels.

    Returns a dict keyed by namespace (``reviewer`` / ``reviewee`` /
    ``pair_context``) where each value is a list of
    ``(canonical_key, friendly_label)`` tuples for slots that have
    at least one non-empty value in the session. The canonical keys
    follow the rule engine's vocabulary (``reviewer.tag1`` etc.).
    Pair-context slots only count rows whose ``status == "active"``.
    """
    result: dict[str, list[tuple[str, str]]] = {
        "reviewer": [],
        "reviewee": [],
        "pair_context": [],
    }
    # The dropdown option label is just the operator's friendly
    # name for the tag — no per-namespace prefix. The per-dropdown
    # caption above each select ("Reviewer tag" / "Reviewee tag")
    # carries the namespace hint now, so the in-option ``R-`` /
    # ``E-`` prefixes are retired.
    namespace_specs = [
        ("reviewer", Reviewer, "reviewer.tag", False),
        ("reviewee", Reviewee, "reviewee.tag", False),
        ("pair_context", Relationship, "pair_context.tag", True),
    ]
    for namespace, model, canonical_prefix, active_only in namespace_specs:
        for slot in (1, 2, 3):
            column_name = f"tag_{slot}"
            if not slot_has_data(
                db,
                session_id=review_session.id,
                column=getattr(model, column_name),
                active_only=active_only,
            ):
                continue
            # Field labels store pair_context slots as "1" / "2" / "3"
            # (without the "tag_" prefix); reviewer / reviewee use
            # "tag_1" / "tag_2" / "tag_3".
            label_field = (
                str(slot) if namespace == "pair_context" else column_name
            )
            friendly = field_labels.resolve(
                review_session, namespace, label_field
            )
            result[namespace].append(
                (f"{canonical_prefix}{slot}", friendly)
            )
    return result


def build_instruments_context(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    editing: int | None = None,
    saved: int | None = None,
    rf_save_error: str | None = None,
    sort_save_error: str | None = None,
    sort_save_error_instrument_id: int | None = None,
) -> dict[str, Any]:
    """Build the template context for the operator instruments index.

    Runs the per-request idempotent display-field backfills
    (locked-row safety net + lazy seeds + stale-row prune),
    derives the editing-state machine, and packages the URL-driven
    error / cascade query params into the dict the template expects.
    Commits the backfill side-effects before returning so subsequent
    queries see the seeded rows.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Make sure every instrument has its locked Name / Email Display
    # Fields rows. The Alembic migration backfills existing instruments;
    # this is the per-request safety net for any sessions that slip
    # through (e.g. created before the migration ran).
    for instrument in instruments:
        instruments_service.ensure_locked_display_fields(
            db, instrument=instrument
        )
    # Prune Display Fields rows whose underlying data source no longer
    # has any populated value (locked Name / Email rows are exempt and
    # always kept). Runs before the lazy seeds so the canonical seed
    # order — reviewee.* before pair_context.* — falls out naturally:
    # any stale rows are gone, then the seeds append fresh in the
    # canonical sequence.
    instruments_service.prune_unpopulated_display_fields(db, review_session)
    # Per-request idempotent backfill of the lazy-seeded display
    # fields. The reviewee / assignment imports already trigger these
    # in the happy path; calling them on every GET catches sessions
    # whose roster or assignments were imported before the lazy-seed
    # logic landed (PR #203). Cheap — both helpers short-circuit when
    # there's nothing to seed.
    instruments_service.seed_display_fields_from_reviewees(db, review_session)
    instruments_service.seed_display_fields_from_assignments(db, review_session)
    db.commit()
    # The session runs ``expire_on_commit=False``, so the commit
    # above leaves any already-loaded ``display_fields`` collections
    # stale — they miss rows the lazy seeds added this request (e.g.
    # tag rows on an instrument created after the reviewee import).
    # Expire so the render below reloads them fresh.
    db.expire_all()

    is_ready = lifecycle.is_ready(review_session)
    can_edit = not is_ready
    # State machine: ``?editing={instrument_id}`` opens that card for
    # editing. The yellow lock card on a ``ready`` session overrides
    # everything — every per-instrument card stays locked.
    editing_instrument_id = None if is_ready else editing

    # "Saved" / "not saved" pill on each per-instrument card's status
    # sub-card. An instrument is "saved" if it has at least one audit
    # event indicating an operator-driven persistence of its field
    # tables (display fields saved via bulk save, edit, add, delete,
    # or move). Pure draft instruments — only seeded rows, never
    # touched — render as "not saved".
    instrument_saved_state = instruments_service.saved_state_for_session(
        db, session_id=review_session.id
    )

    # Per-instrument "Set up" / "Not set up" pill (locked decision in
    # Segment 18M follow-up). Same predicate the workflow card uses;
    # rendered on each per-instrument <summary> in place of the
    # retired accepting / showing-when-closed pills.
    is_configured_by_instrument = {
        inst.id: instruments_service.is_configured(db, inst)
        for inst in instruments
    }

    return {
        "user": user,
        "session": review_session,
        "status_pills": session_status_pills(db, review_session),
        "instruments": instruments,
        "is_ready": is_ready,
        "can_edit": can_edit,
        "bulk_accepting_state": _bulk_state(
            [i.accepting_responses for i in instruments]
        ),
        "bulk_visibility_state": _bulk_state(
            [i.responses_visible_when_closed for i in instruments]
        ),
        "editing_instrument_id": editing_instrument_id,
        "instrument_saved_state": instrument_saved_state,
        "is_configured_by_instrument": is_configured_by_instrument,
        "saved_instrument_id": saved,
        "rf_save_error": rf_save_error,
        "is_some_instrument_editing": editing_instrument_id is not None,
        "sort_save_error": sort_save_error,
        "sort_save_error_instrument_id": sort_save_error_instrument_id,
        "breadcrumbs": breadcrumbs.operator_session_child(
            review_session, "Instruments"
        ),
        "new_model_tags": _new_model_usable_tags(db, review_session),
        "new_model_band1_state": {
            instrument.id: instruments_service.decode_band1_state(
                instrument, db
            )
            for instrument in instruments
        },
        "new_model_link3_state": {
            instrument.id: {
                "mode": "individual" if instrument.group_kind is None else "grouped",
                "boundary_pairs": instruments_service.decode_group_kind(
                    instrument.group_kind
                ),
                "touched": "link3" in (instrument.band1_touched_links or []),
            }
            for instrument in instruments
        },
        "new_model_band2_state": _new_model_band2_states_for(
            db, instruments
        ),
        # Band 3 type-picker quick-fill presets (each one writes
        # ``data_type=list`` + a pre-filled comma-separated
        # ``list_options``; identity-less at storage time).
        "band3_list_presets": list(_BAND3_LIST_PRESETS),
        # Band 3 visibility editor — per-instrument, per-audience
        # state for the Visibility table. Missing rows surface as
        # the audience's default (disabled + default mode +
        # default visible_when). See
        # ``spec/visibility_policy.md`` for the contract.
        "band3_visibility_by_instrument": _band3_visibility_states_for(
            db, instruments
        ),
    }


# Per-audience UI defaults for the Band 3 visibility editor when
# no row exists yet on ``instrument_view_policies`` for that
# audience. The default mode for ``peer_reviewer`` is locked at
# ``raw`` (the UI greys the What chip); the default
# ``visible_when`` mirrors the placeholder template's pre-S12
# selection — ``while_ongoing`` for peer_reviewer (the legacy
# "While session ongoing" pill), ``after_release`` for reviewee /
# observer (the placeholder's "After release" cycle default).
_BAND3_VISIBILITY_DEFAULTS: dict[str, dict[str, object]] = {
    "peer_reviewer": {
        "enabled": False,
        "mode": "raw",
        "visible_when": "while_ongoing",
        "observer_tag": None,
    },
    "reviewee": {
        "enabled": False,
        "mode": "anonymized",
        "visible_when": "after_release",
        "observer_tag": None,
    },
    "observer": {
        "enabled": False,
        "mode": "anonymized",
        "visible_when": "after_release",
        "observer_tag": None,
    },
}


def _band3_visibility_states_for(
    db: Session, instruments: list[Instrument]
) -> dict[int, dict[str, dict[str, object]]]:
    """Build the Band 3 visibility editor state for every instrument
    on the page. Returns ``{instrument_id: {audience: state}}``
    where ``state`` is a dict carrying ``enabled`` / ``mode`` /
    ``visible_when`` / ``observer_tag``. Audiences with no
    persisted row fall back to
    :data:`_BAND3_VISIBILITY_DEFAULTS`."""
    result: dict[int, dict[str, dict[str, object]]] = {}
    for instrument in instruments:
        persisted = visibility_policies.list_for_instrument(
            db, instrument.id
        )
        per_audience: dict[str, dict[str, object]] = {}
        for audience in visibility_policies.AUDIENCES:
            row = persisted.get(audience)
            defaults = _BAND3_VISIBILITY_DEFAULTS[audience]
            if row is None:
                per_audience[audience] = dict(defaults)
                continue
            try:
                mode = visibility_policies.decode_mode(
                    row.granularity, row.identification
                )
            except visibility_policies.VisibilityPolicyError:
                # The reserved-incoherent (aggregated, identified)
                # combo is rejected by upsert, but the column
                # types accept it — fall back to defaults rather
                # than 500 on render.
                mode = str(defaults["mode"])
            per_audience[audience] = {
                "enabled": bool(row.enabled),
                "mode": mode,
                "visible_when": (
                    row.visible_when
                    or str(defaults["visible_when"])
                ),
                "observer_tag": row.observer_tag,
            }
        result[instrument.id] = per_audience
    return result


def _new_model_band2_states_for(
    db: Session, instruments: list[Instrument]
) -> dict[int, dict[str, Any]]:
    """Build the ``new_model_band2_state`` dict for every new-model
    instrument on the page, sharing one active-reviewees fetch across
    them (Segment 18J Wave 1 Rec D1).
    """
    # Wave 5 PR 5.3 — every instrument is implicitly new-model.
    new_model_instruments = list(instruments)
    if not new_model_instruments:
        return {}
    review_session = new_model_instruments[0].session
    active_reviewees = list(
        db.execute(
            select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .where(Reviewee.status == "active")
            .order_by(Reviewee.name, Reviewee.id)
        ).scalars()
    )
    return {
        instrument.id: _new_model_band2_state(
            db, instrument, active_reviewees=active_reviewees
        )
        for instrument in new_model_instruments
    }
