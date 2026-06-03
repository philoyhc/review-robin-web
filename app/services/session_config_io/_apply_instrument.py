"""``instruments[N].*`` parse + apply (including the wipe-and-replace prelude).

The biggest section module — instruments carry display_fields[] +
response_fields[] sub-sections, each with the per-attribute parser
above the apply phase that re-creates the rows from scratch in one
transaction.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ReviewSession,
    SessionRuleSet,
)
from app.services.instruments._response_fields import (
    DEFAULT_RESPONSE_FIELDS,
    _inline_kwargs_from_default_spec,
    _validation_block_from_default_spec,
    validation_block_from_inline,
)

from ._apply_shared import (
    _RX_INSTRUMENT,
    _RX_INSTRUMENT_DF,
    _RX_INSTRUMENT_RF,
    _VALID_DF_SOURCE_TYPES,
    _DisplayFieldSpec,
    _InstrumentSpec,
    _ParsedConfig,
    _ParseError,
    _ResponseFieldSpec,
    _parse_bool,
    _parse_decimal,
    _parse_group_kind,
    _parse_int,
    _parse_json,
)


class _ApplyConflict(Exception):
    """Raised by the apply phase when a cross-row reference
    can't be resolved against the in-progress session state
    (e.g. an unknown RTD reference). The caller's transaction
    handler rolls back."""


def _apply_instrument_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    df_match = _RX_INSTRUMENT_DF.match(field_path)
    if df_match is not None:
        n, m, attr = (
            int(df_match.group(1)),
            int(df_match.group(2)),
            df_match.group(3),
        )
        instrument = plan.instruments.setdefault(n, _InstrumentSpec())
        df = instrument.display_fields.setdefault(m, _DisplayFieldSpec())
        if attr == "source_type":
            if value and value not in _VALID_DF_SOURCE_TYPES:
                raise _ParseError(
                    f"unknown display-field source_type {value!r}; "
                    f"expected one of {sorted(_VALID_DF_SOURCE_TYPES)}"
                )
            df.source_type = value or None
        elif attr == "source_field":
            df.source_field = value or None
        elif attr == "label":
            # 15A Slice 1 — display-field per-instrument label
            # retired. Legacy Settings CSVs may still carry this
            # row; tolerate it and silently drop the value so
            # round-trip imports continue to succeed.
            pass
        elif attr == "visible":
            df.visible = _parse_bool(value, default=True)
        else:
            raise _ParseError(
                f"unknown display_fields[] attribute {attr!r}"
            )
        return

    rf_match = _RX_INSTRUMENT_RF.match(field_path)
    if rf_match is not None:
        n, m, attr = (
            int(rf_match.group(1)),
            int(rf_match.group(2)),
            rf_match.group(3),
        )
        instrument = plan.instruments.setdefault(n, _InstrumentSpec())
        rf = instrument.response_fields.setdefault(m, _ResponseFieldSpec())
        if attr == "field_key":
            rf.field_key = value or None
        elif attr == "label":
            rf.label = value or None
        elif attr == "response_type":
            rf.response_type = value or None
        elif attr == "required":
            rf.required = _parse_bool(value)
        elif attr == "help_text":
            rf.help_text = value or None
        elif attr == "help_text_visible":
            rf.help_text_visible = _parse_bool(value, default=True)
        # Segment 18N PR 5 — inline type + bounds + per-field
        # visibility. The serializer carries these as ``data_type``
        # (capitalised: ``String`` / ``Integer`` / ``Decimal`` /
        # ``List``), four ``decimal`` cells for the numeric
        # bounds (NULL → empty cell), ``list_csv`` for List
        # options, and a ``boolean`` for the Band 2 chip flag.
        elif attr == "data_type":
            rf.data_type = value or None
        elif attr == "min":
            rf.min = _parse_decimal(value)
        elif attr == "max":
            rf.max = _parse_decimal(value)
        elif attr == "step":
            rf.step = _parse_decimal(value)
        elif attr == "list_csv":
            rf.list_csv = value or None
        elif attr == "visible":
            rf.visible = _parse_bool(value, default=True)
        else:
            raise _ParseError(
                f"unknown response_fields[] attribute {attr!r}"
            )
        return

    inst_match = _RX_INSTRUMENT.match(field_path)
    if inst_match is None:
        raise _ParseError(f"unrecognised instruments[] key {field_path!r}")
    n, attr = int(inst_match.group(1)), inst_match.group(2)
    instrument = plan.instruments.setdefault(n, _InstrumentSpec())
    if attr == "name":
        instrument.name = value or None
    elif attr == "short_label":
        instrument.short_label = value or None
    elif attr == "description":
        instrument.description = value or None
    elif attr == "order":
        instrument.order = _parse_int(value)
    elif attr == "accepting_responses":
        instrument.accepting_responses = _parse_bool(value)
    elif attr == "responses_visible_when_closed":
        instrument.responses_visible_when_closed = _parse_bool(value)
    elif attr == "sort_display_fields":
        instrument.sort_display_fields = _parse_json(value, default=[])
    elif attr == "group_kind":
        instrument.group_kind = _parse_group_kind(value)
    elif attr == "rule_set_name":
        instrument.rule_set_name = value or None
    # Segment 18N PR 5 — three operator-input fields the pre-PR-5
    # round-trip silently dropped.
    elif attr == "column_widths":
        instrument.column_widths = _parse_json(value, default={}) or None
    elif attr == "starts_new_page":
        instrument.starts_new_page = _parse_bool(value)
    elif attr == "band2_state":
        instrument.band2_state = _parse_json(value, default={}) or None
    else:
        raise _ParseError(f"unknown instruments[] attribute {attr!r}")
    del data_type  # unused; type-checked by parser per attr


def _wipe_instruments_and_dependents(
    db: Session, review_session: ReviewSession
) -> None:
    """Wipe-and-replace prelude for the settings re-import.

    Drops the session's Responses + Assignments + Instrument rows
    so the downstream apply step can rebuild the instrument tree
    from scratch. The pre-2026-05-26 ``_apply_rtds`` did the same
    instrument wipe as a prelude to RTD upsert; the RTD table
    retired but the wipe-and-replace shape is still load-bearing
    for instrument re-import.
    """
    # Responses FK ``assignments``; the bulk Core delete below would
    # trip that constraint on a session reverted from ``ready`` (which
    # keeps its responses) unless they go first. The settings
    # re-import rebuilds the whole instrument structure, so these
    # responses cannot survive it regardless — clear them explicitly.
    db.execute(
        Response.__table__.delete().where(
            Response.assignment_id.in_(
                select(Assignment.id).where(
                    Assignment.session_id == review_session.id
                )
            )
        )
    )
    db.execute(
        Assignment.__table__.delete().where(
            Assignment.session_id == review_session.id
        )
    )
    instruments_to_delete = (
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
        )
        .scalars()
        .all()
    )
    for instrument in instruments_to_delete:
        db.delete(instrument)
    db.flush()


def _apply_instruments(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> dict[str, int]:
    """Re-create instruments + display_fields + response_fields
    from the CSV. ``_apply_rtds`` already wiped any pre-existing
    instruments + their child rows in this same transaction."""

    counts = {
        "instruments": 0,
        "display_fields": 0,
        "response_fields": 0,
    }
    # Per-instrument rule pin (Segment 15B Slice 2b). The session-tier
    # ``session_rule_sets`` rows are upserted by
    # ``_apply_session_rule_sets`` earlier in the apply pipeline.
    # Wave 5 PR 5.2 retired the seed-materialiser safety net here —
    # seeded RuleSets no longer ship on new sessions.
    rule_set_id_by_name = {
        snap.name: snap.id
        for snap in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }

    for n in sorted(plan.instruments.keys()):
        spec = plan.instruments[n]
        assert spec.name is not None  # cross-row check enforced
        if spec.rule_set_name:
            resolved_rule_set_id = rule_set_id_by_name.get(spec.rule_set_name)
            if resolved_rule_set_id is None:
                raise _ParseError(
                    f"rule set {spec.rule_set_name!r} not found in this "
                    f"session — add it to the session's RuleSet pool first "
                    f"(instruments[{n}].rule_set_name)"
                )
        else:
            resolved_rule_set_id = None
        instrument = Instrument(
            session_id=review_session.id,
            name=spec.name,
            short_label=spec.short_label,
            description=spec.description,
            order=n,  # 1-based CSV position wins over ``order`` cell
            accepting_responses=spec.accepting_responses,
            responses_visible_when_closed=spec.responses_visible_when_closed,
            sort_display_fields=spec.sort_display_fields,
            group_kind=spec.group_kind,
            rule_set_id=resolved_rule_set_id,
            # Segment 18N PR 5 — three round-trip-added columns
            # the pre-PR-5 import would silently NULL out.
            column_widths=spec.column_widths,
            starts_new_page=spec.starts_new_page,
            band2_state=spec.band2_state,
        )
        db.add(instrument)
        db.flush()  # populate ``instrument.id``
        counts["instruments"] += 1

        for m in sorted(spec.display_fields.keys()):
            df_spec = spec.display_fields[m]
            assert df_spec.source_type is not None
            db.add(
                InstrumentDisplayField(
                    instrument_id=instrument.id,
                    label=df_spec.label or "",
                    source_type=df_spec.source_type,
                    source_field=df_spec.source_field or "",
                    order=m,
                    visible=df_spec.visible,
                )
            )
            counts["display_fields"] += 1

        # Per-session ``response_type_definitions`` table retired
        # 2026-05-26. Type + bounds + list options now live inline
        # on ``_inline_*`` columns. Segment 18N PR 5 wires the
        # serializer to carry those + ``visible`` + recomputes the
        # ``validation`` JSON block from the imported inline state
        # via the same helper the operator-edit path uses (so the
        # reviewer surface, which reads ``validation``, lines up
        # with the inline state after a round-trip).
        #
        # When the CSV doesn't carry inline state (pre-PR-5 export,
        # or a hand-edited Settings CSV that omits the new keys),
        # fall back to the seeded Rating-Integer 1-5 default so
        # the import still produces a usable response field —
        # matches the pre-PR-5 behaviour for backwards compat.
        default_spec = DEFAULT_RESPONSE_FIELDS[0]
        default_inline = _inline_kwargs_from_default_spec(default_spec)
        default_validation = _validation_block_from_default_spec(default_spec)
        for m in sorted(spec.response_fields.keys()):
            rf_spec = spec.response_fields[m]
            inline_kwargs = dict(default_inline)
            if rf_spec.response_type:
                inline_kwargs["_inline_response_type"] = rf_spec.response_type
            if rf_spec.data_type is not None:
                inline_kwargs["_inline_data_type"] = rf_spec.data_type
                inline_kwargs["_inline_min"] = rf_spec.min
                inline_kwargs["_inline_max"] = rf_spec.max
                inline_kwargs["_inline_step"] = rf_spec.step
                inline_kwargs["_inline_list_csv"] = rf_spec.list_csv
                # Recompute the ``validation`` JSON to match the
                # imported inline state — mirrors the dual-write
                # the operator's Band 3 save path lands (Segment
                # 18K's ``validation_block_from_inline`` seam).
                validation_block = validation_block_from_inline(
                    rf_spec.data_type,
                    rf_spec.min,
                    rf_spec.max,
                    rf_spec.step,
                    rf_spec.list_csv,
                )
            else:
                validation_block = default_validation
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=rf_spec.field_key or "",
                    label=rf_spec.label or "",
                    required=rf_spec.required,
                    order=m,
                    validation=validation_block,
                    help_text=rf_spec.help_text,
                    help_text_visible=rf_spec.help_text_visible,
                    visible=rf_spec.visible,
                    **inline_kwargs,
                )
            )
            counts["response_fields"] += 1

    return counts
