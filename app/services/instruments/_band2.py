"""Band 2 state slice — the operator's Band 2 selections + Band 3
response-field sync path.

Carved out of ``_instrument_crud.py`` in Segment 18N PR 2 — that
file had grown to 1,928 LOC across overlapping concerns (basic
CRUD, group / unit-of-review wiring, column widths, the Band 2
state save, bulk toggles, and the 18M ordering + page-break
helpers). The Band 2 state save was the densest concentration,
~620 LOC carrying the JSON sanitiser, the dual-write to real
``InstrumentResponseField`` rows
(``_sync_response_fields_to_db``), the display-field visibility
propagator (``_sync_display_field_visibility``), and the
authoring-shape validator. This slice owns all of that.

Cross-slice reads (all uni-directional):

- ``_state._instrument_label`` for audit-event summaries.
- ``_instrument_crud.set_column_widths`` /
  ``_instrument_crud._COLUMN_WIDTH_MIN_PX`` /
  ``_instrument_crud._COLUMN_WIDTH_MAX_PX`` for the per-response-
  field width round-trip embedded in the Band 2 payload.
- ``_response_fields`` (local imports inside the dual-write helper
  to avoid a module-load cycle).
- ``_display_fields`` (same).

``_instrument_crud.py`` reads nothing from this module — the
dependency is one-way.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    Response,
    User,
)
from app.services import audit
from app.services.instruments._instrument_crud import (
    _COLUMN_WIDTH_MAX_PX,
    _COLUMN_WIDTH_MIN_PX,
    set_column_widths,
)
from app.services.instruments._state import _instrument_label


_BAND2_ALLOWED_DISPLAY_KEYS: frozenset[str] = frozenset(
    {
        "reviewee.name",
        "reviewee.email_or_identifier",
        "reviewee.profile_link",
        "reviewee.tag_1",
        "reviewee.tag_2",
        "reviewee.tag_3",
        "pair_context.tag_1",
        "pair_context.tag_2",
        "pair_context.tag_3",
    }
)
_BAND2_ALLOWED_DATA_TYPES: frozenset[str] = frozenset(
    {"string", "integer", "decimal", "list"}
)
_BAND2_RF_BOUND_KEYS: tuple[str, ...] = (
    "min",
    "max",
    "step",
    "list_options",
)


def set_band2_state(
    db: Session,
    *,
    instrument: Instrument,
    state: dict[str, Any],
    actor: User,
    acknowledged_drop: bool = False,
) -> Instrument:
    """Persist the operator's Band 2 selections + response-field
    definitions on a new-model instrument card.

    ``state`` is the JSON blob described in the
    ``e7c2b4d9a3f1_add_instruments_band2_state`` migration docstring:

    - ``selected_display_keys``: list of canonical pill identifiers
      (``"reviewee.name"`` etc.) the operator has toggled into the
      preview row. Unknown keys are dropped silently.
    - ``response_fields``: ordered list of dicts describing each
      response-field row the operator has committed (via the ✓
      button). Each dict carries ``name`` (str, required, ≤255
      chars), ``data_type`` (one of ``string`` / ``integer`` /
      ``decimal`` / ``list``), ``min`` / ``max`` / ``step`` /
      ``list_options`` (str, optional), and ``selected`` (bool).

    Passing ``None`` (or a payload that reduces to empty
    selections + zero response_fields) clears ``band2_state``
    back to NULL — the new-model card falls back to its default
    "nothing selected, no response fields" shape.

    No-op saves (the merged payload matches what's already
    persisted) skip the audit + lifecycle side effects.
    """
    sanitised: dict[str, Any] = {}
    existing = instrument.band2_state or {}
    # Field-presence semantics: every top-level key in band2_state
    # is independently writable. A payload that *omits* a key
    # carries the existing value forward; a payload that *includes*
    # a key (even with an empty value) replaces it. This lets the
    # pill-toggle save send only ``selected_display_keys`` without
    # nuking the operator's ``response_fields`` or
    # ``sample_reviewee_name``, and lets ↻ Refresh send only
    # ``sample_reviewee_name`` without nuking the pill / RF state.
    selected_keys_in_payload = (
        isinstance(state, dict) and "selected_display_keys" in state
    )
    if selected_keys_in_payload:
        raw_keys = state.get("selected_display_keys")
        if isinstance(raw_keys, list):
            sanitised_keys: list[str] = []
            for raw in raw_keys:
                k = str(raw).strip()
                if k in _BAND2_ALLOWED_DISPLAY_KEYS and k not in sanitised_keys:
                    sanitised_keys.append(k)
            if sanitised_keys:
                sanitised["selected_display_keys"] = sanitised_keys
            # Gap 1: propagate the pill selection to
            # ``InstrumentDisplayField.visible`` so the reviewer
            # surface honours the operator's pill toggles. Locked
            # Name / Email rows stay visible regardless.
            _sync_display_field_visibility(
                db,
                instrument=instrument,
                selected_keys=set(sanitised_keys)
                if isinstance(raw_keys, list)
                else None,
                actor=actor,
            )
    else:
        existing_keys = existing.get("selected_display_keys")
        if isinstance(existing_keys, list) and existing_keys:
            sanitised["selected_display_keys"] = list(existing_keys)
    # Wave 3 PR iii — sanitised response_fields is no longer
    # persisted into band2_state JSON. It still gets built as a
    # local list, sent through ``_sync_response_fields_to_db`` to
    # land on real ``InstrumentResponseField`` rows, then dropped.
    # Per-response-field width_px values (if any) get peeled off
    # into the parallel ``column_widths`` update below.
    incoming_rfs: list[dict[str, Any]] | None = None
    rf_widths_by_id: dict[int, int] = {}
    rf_widths_by_name: dict[str, int] = {}
    if isinstance(state, dict) and "response_fields" in state:
        raw_rfs = state.get("response_fields")
        if isinstance(raw_rfs, list):
            incoming_rfs = []
            for raw in raw_rfs:
                if not isinstance(raw, dict):
                    continue
                name = str(raw.get("name") or "").strip()[:255]
                if not name:
                    continue
                data_type = str(raw.get("data_type") or "string").strip().lower()
                if data_type not in _BAND2_ALLOWED_DATA_TYPES:
                    data_type = "string"
                rf: dict[str, Any] = {"name": name, "data_type": data_type}
                raw_id = raw.get("id")
                if isinstance(raw_id, int) and raw_id > 0:
                    rf["id"] = raw_id
                elif isinstance(raw_id, str) and raw_id.strip().isdigit():
                    rf["id"] = int(raw_id)
                for bound_key in _BAND2_RF_BOUND_KEYS:
                    value = raw.get(bound_key)
                    rf[bound_key] = str(value).strip()[:255] if value is not None else ""
                rf["selected"] = bool(raw.get("selected"))
                rf["required"] = bool(raw.get("required"))
                rf["help_text_visible"] = bool(raw.get("help_text_visible"))
                help_text_raw = raw.get("help_text")
                rf["help_text"] = (
                    str(help_text_raw)[:1000] if help_text_raw is not None else ""
                )
                # Wave 3 PR iii — per-response-field column width (px)
                # moves out of band2_state JSON into the canonical
                # ``column_widths`` dict on the instrument under
                # ``rf_<id>`` keys, alongside ``df_<id>`` and
                # ``identity``. Captured here keyed by id when we know
                # one, by name otherwise; the dual-write below
                # back-fills the id and we re-key by id afterwards.
                raw_width = raw.get("width_px")
                if raw_width not in (None, ""):
                    try:
                        width_int = int(raw_width)
                    except (TypeError, ValueError):
                        width_int = 0
                    if width_int >= _COLUMN_WIDTH_MIN_PX:
                        clamped = min(width_int, _COLUMN_WIDTH_MAX_PX)
                        rf_id = rf.get("id")
                        if isinstance(rf_id, int):
                            rf_widths_by_id[rf_id] = clamped
                        else:
                            rf_widths_by_name[name] = clamped
                incoming_rfs.append(rf)
    if isinstance(state, dict) and "sample_reviewee_name" in state:
        candidate = str(state.get("sample_reviewee_name") or "").strip()[:255]
        if candidate:
            sanitised["sample_reviewee_name"] = candidate
    else:
        existing_sample = existing.get("sample_reviewee_name")
        if existing_sample:
            sanitised["sample_reviewee_name"] = str(existing_sample)[:255]
    # Gap 10: rule-surviving group member ID set persisted alongside
    # sample_reviewee_name by the preview-sample route. Present +
    # list-of-ints stores; present + None / non-list drops (e.g.
    # boundary switched off — render falls back to unconstrained
    # partition). Missing preserves existing.
    if isinstance(state, dict) and "sample_group_member_ids" in state:
        raw_ids = state.get("sample_group_member_ids")
        if isinstance(raw_ids, list):
            cleaned_ids: list[int] = []
            for raw in raw_ids:
                try:
                    rid = int(raw)
                except (TypeError, ValueError):
                    continue
                if rid > 0 and rid not in cleaned_ids:
                    cleaned_ids.append(rid)
            if cleaned_ids:
                sanitised["sample_group_member_ids"] = cleaned_ids
    else:
        existing_ids = existing.get("sample_group_member_ids")
        if isinstance(existing_ids, list) and existing_ids:
            sanitised["sample_group_member_ids"] = list(existing_ids)
    # Wave 3 PR iii — DB rows are now authoritative for response
    # fields; JSON ``response_fields`` retired. The dual-write helper
    # still runs but the previous-state reference switches from "ids
    # in the old JSON" to "ids of all current InstrumentResponseField
    # rows" so the delete contract becomes "any DB row not in the
    # incoming payload by id gets deleted." The (b) contract in
    # ``_new_model_band2_state`` (view layer) guarantees the first
    # render populates the payload from DB rows, so the JS always
    # round-trips the full id set on the next save — no row ever
    # surprises the delete check.
    if incoming_rfs is not None:
        previous_ids: set[int] = {f.id for f in instrument.response_fields}
        _sync_response_fields_to_db(
            db,
            instrument=instrument,
            sanitised_rfs=incoming_rfs,
            previous_json_ids=previous_ids,
            actor=actor,
            acknowledged_drop=acknowledged_drop,
        )
        # Now that ``_sync_response_fields_to_db`` has back-filled
        # ids on newly-created rows, re-key any name-bound widths
        # we set aside above and merge with the id-keyed widths.
        if rf_widths_by_name:
            name_to_id: dict[str, int] = {}
            for rf in incoming_rfs:
                rf_id = rf.get("id")
                if isinstance(rf_id, int):
                    name_to_id.setdefault(rf["name"], rf_id)
            for name, width in rf_widths_by_name.items():
                rf_id = name_to_id.get(name)
                if rf_id is not None:
                    rf_widths_by_id.setdefault(rf_id, width)
        # Merge incoming response-column widths into ``column_widths``.
        # Display-field widths + identity stay untouched. Refresh the
        # response_fields relationship first: ``_sync_response_fields_to_db``
        # ``db.add()``'d newly-created rows + flushed them, but the
        # relationship-loaded list on the instrument is stale, and
        # ``set_column_widths``'s validator (which builds the valid-
        # id set from that list) would otherwise drop ``rf_<new_id>``
        # keys as unknown.
        if rf_widths_by_id:
            db.refresh(instrument, attribute_names=["response_fields"])
            existing_widths = dict(instrument.column_widths or {})
            for rf_id, width in rf_widths_by_id.items():
                existing_widths[f"rf_{rf_id}"] = width
            set_column_widths(
                db,
                instrument=instrument,
                widths=existing_widths,
                actor=actor,
            )

    new_value: dict[str, Any] | None = sanitised or None
    if (instrument.band2_state or None) == new_value:
        return instrument
    old_value = instrument.band2_state
    instrument.band2_state = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.band2_state_updated",
        summary=(
            f"Updated new-model band2 state on instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes(
            {"band2_state": [old_value, new_value]}
        ),
        refs={"instrument_id": instrument.id},
    )
    return instrument


_BAND2_DATA_TYPE_TO_INLINE: dict[str, str] = {
    "string": "String",
    "integer": "Integer",
    "decimal": "Decimal",
    "list": "List",
}


def _band2_parse_float(value: Any) -> float | None:
    """Parse a band2_state numeric string ("1", "0.5", "") into a
    float. Returns ``None`` for empty / unparseable values so the
    inline column stays nullable rather than landing 0 for absent
    bounds."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _validate_response_field_shape(rf: dict[str, Any]) -> str | None:
    """Wave 3 PR ii — check a sanitised band2_state response-field
    entry against the locked-decision-11 authoring rules. Returns
    an operator-facing error message or None.

    Sanitised numeric fields arrive as strings ("" for unset);
    parse here and accept None as "no bound" for Integer / Decimal.
    For List the option set must be non-empty; for String the
    max_length (carried on the ``max`` slot) must be > 0 when set.
    """
    data_type = rf.get("data_type", "string")
    if data_type in ("integer", "decimal"):
        min_ = _band2_parse_float(rf.get("min"))
        max_ = _band2_parse_float(rf.get("max"))
        step = _band2_parse_float(rf.get("step"))
        if min_ is not None and max_ is not None and max_ < min_:
            return "Max must be at least Min."
        if step is not None and step <= 0:
            return "Step must be greater than zero."
        # Step must be reachable at least once from Min — i.e.
        # ``step <= (max - min)`` so the field has at least two
        # valid values (Min and Min+step). A larger step leaves only
        # Min as a valid value and the Step bound adds nothing the
        # operator couldn't achieve with a fixed value. Equal is
        # accepted (min=0, max=1, step=1 → values 0, 1 — useful for
        # Boolean-like numeric fields). Tiny epsilon guards against
        # float-precision drift.
        if (
            min_ is not None
            and max_ is not None
            and step is not None
            and max_ > min_
            and step > (max_ - min_) + 1e-9
        ):
            return (
                "Step must be at most (Max − Min) so the field has "
                "at least two valid values."
            )
        return None
    if data_type == "string":
        max_ = _band2_parse_float(rf.get("max"))
        if max_ is not None and max_ <= 0:
            return "Max length must be greater than zero."
        return None
    if data_type == "list":
        list_csv = (rf.get("list_options") or "").strip()
        options = [opt.strip() for opt in list_csv.split(",") if opt.strip()]
        if not options:
            return "List options must include at least one entry."
        return None
    return None


def _band2_unique_field_key(
    name: str, used_keys: set[str], existing_key: str | None = None
) -> str:
    """Slugify ``name`` to a field_key, suffixing -2 / -3 / ...
    on collision. If ``existing_key`` is supplied and already
    matches the slug of the new name (or is already taken), keep
    it unchanged (decision 9: field_key stable across renames)."""
    from app.services.instruments._response_fields import slugify_field_key

    if existing_key:
        # Decision 9 — once a field has an id, field_key never
        # changes. The caller only invokes this branch when
        # there's no existing key (new row), so this is just a
        # safety net.
        return existing_key
    base = slugify_field_key(name) or "field"
    candidate = base
    suffix = 2
    while candidate in used_keys:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _sync_response_fields_to_db(
    db: Session,
    *,
    instrument: Instrument,
    sanitised_rfs: list[dict[str, Any]],
    previous_json_ids: set[int],
    actor: User,
    acknowledged_drop: bool = False,
) -> None:
    """Wave 3 PR i — dual-write the operator-authored response-
    field JSON entries through to real ``InstrumentResponseField``
    rows.

    - JSON entry with an ``id`` matching one of this instrument's
      rows → update that row in place (label / inline type +
      bounds / required / visible / help_text / help_text_visible /
      order).
    - JSON entry without ``id`` → create a new row; back-fill
      ``id`` into the JSON entry so subsequent saves can id-match.
    - DB row whose id is absent from the JSON payload → delete
      (raises :class:`ResponsesPresentError` if the row has
      attached :class:`Response` rows; the operator-side X is
      rendered disabled when ``has_responses`` is true to prevent
      this surfacing in the typical flow).

    The reviewer-surface read path is untouched in this PR — it
    still pulls only the seeded ``DEFAULT_RESPONSE_FIELDS`` rows.
    PR ii flips the read path to ``WHERE visible=true``.

    ``sanitised_rfs`` is mutated in place: every entry has its
    ``id`` field populated on return (either preserved if already
    present, or back-filled from a newly-created row's PK).
    """
    from app.services.instruments._response_fields import (
        InvalidResponseFieldShapeError,
        ResponseFieldDropAcknowledgementRequired,
        ResponseFieldShapeChangeError,
        ResponsesPresentError,
        validation_block_from_inline,
    )

    # Wave 3 PR ii — authoring-shape validation. Reject the whole
    # payload (atomic save) when any entry has nonsensical bounds,
    # mirroring the locked-decision-11 contract.
    shape_errors: list[tuple[str, str]] = []
    for rf in sanitised_rfs:
        msg = _validate_response_field_shape(rf)
        if msg is not None:
            shape_errors.append((rf["name"], msg))
    if shape_errors:
        raise InvalidResponseFieldShapeError(shape_errors)

    existing_by_id: dict[int, InstrumentResponseField] = {
        f.id: f for f in instrument.response_fields
    }
    used_field_keys: set[str] = {
        f.field_key for f in instrument.response_fields
    }
    seen_ids: set[int] = set()

    for order_idx, rf in enumerate(sanitised_rfs):
        rf_id_raw = rf.get("id")
        rf_id: int | None = None
        if isinstance(rf_id_raw, int):
            rf_id = rf_id_raw
        elif isinstance(rf_id_raw, str) and rf_id_raw.strip().isdigit():
            rf_id = int(rf_id_raw)

        if rf_id is not None and rf_id in existing_by_id:
            field = existing_by_id[rf_id]
        else:
            # New row — slugify the name to a unique field_key.
            field = InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=_band2_unique_field_key(rf["name"], used_field_keys),
                label=rf["name"][:255],
                order=order_idx,
            )
            db.add(field)
            db.flush()  # populate field.id
            used_field_keys.add(field.field_key)
            rf["id"] = field.id

        seen_ids.add(field.id)

        # Update label + flags + order.
        field.label = rf["name"][:255]
        field.order = order_idx
        field.required = bool(rf.get("required"))
        # Band 2 response-pill "selected" flag flows through to
        # the new visible column. Mirrors how Gap 1 wired the
        # display-field pill to InstrumentDisplayField.visible.
        #
        # Segment 18K PR 4 — Visibility-drop confirm guard.
        # Un-pinning a chip whose field has saved responses drops
        # the column from every reviewer-facing render (surface,
        # summary HTML, reviewer-record CSV). Underlying ``Response``
        # rows stay in the DB for the operator-side audit / bundle
        # export (Part 5 contract), but the reviewer can no longer
        # see them. Operator must acknowledge per Part 3 item 1.
        prior_visible = bool(field.visible)
        incoming_visible = bool(rf.get("selected", True))
        if (
            prior_visible
            and not incoming_visible
            and not acknowledged_drop
        ):
            drop_response_count = db.execute(
                select(func.count(Response.id)).where(
                    Response.response_field_id == field.id
                )
            ).scalar_one()
            if drop_response_count:
                raise ResponseFieldDropAcknowledgementRequired(
                    field_label=field.label,
                    count=drop_response_count,
                )
        field.visible = incoming_visible
        help_text_raw = rf.get("help_text")
        field.help_text = (
            str(help_text_raw)[:1000] if help_text_raw else None
        )
        field.help_text_visible = bool(rf.get("help_text_visible"))

        # Inline type + bounds. Sanitised JSON uses lowercase
        # ``string`` / ``integer`` / ``decimal`` / ``list``; the
        # inline column keeps the legacy capitalised form for
        # round-trip compat with the Wave 2 _inline_* columns.
        data_type_lower = rf.get("data_type", "string")
        new_data_type = _BAND2_DATA_TYPE_TO_INLINE.get(
            data_type_lower, "String"
        )
        new_min = _band2_parse_float(rf.get("min"))
        new_max = _band2_parse_float(rf.get("max"))
        new_step = _band2_parse_float(rf.get("step"))
        new_list_csv_raw = rf.get("list_options") or ""
        new_list_csv = new_list_csv_raw if new_list_csv_raw else None

        # Wave 3 PR ii — block any data_type / bounds change on a row
        # that already has saved responses. The Band 3 row's data_type
        # select + bound inputs are rendered ``disabled`` when
        # ``has_responses`` is true; this server-side guard catches
        # direct API hits / forged sendBeacon payloads. Operator must
        # clear the responses first to re-shape the field.
        #
        # Use a counted SELECT rather than touching ``field.responses``
        # so the relationship cache stays untouched — populating it
        # here would persist a stale empty list across the request
        # boundary (sessions use ``expire_on_commit=False``) and let
        # the downstream delete-cascade check miss a freshly-attached
        # Response row.
        shape_changed: list[str] = []
        if field._inline_data_type != new_data_type:
            shape_changed.append("data_type")
        if field._inline_min != new_min:
            shape_changed.append("min")
        if field._inline_max != new_max:
            shape_changed.append("max")
        if field._inline_step != new_step:
            shape_changed.append("step")
        if field._inline_list_csv != new_list_csv:
            shape_changed.append("list_options")
        if shape_changed:
            response_count = db.execute(
                select(func.count(Response.id)).where(
                    Response.response_field_id == field.id
                )
            ).scalar_one()
            if response_count:
                raise ResponseFieldShapeChangeError(
                    field_label=field.label,
                    count=response_count,
                    changed_attrs=shape_changed,
                )

        field._inline_data_type = new_data_type
        field._inline_min = new_min
        field._inline_max = new_max
        field._inline_step = new_step
        field._inline_list_csv = new_list_csv
        # The reviewer surface reads ``cell.field.validation`` (JSON
        # column) for ``max_length`` / numeric ``min`` / ``max`` /
        # ``step`` / List ``choices`` — separate from the inline
        # columns. Recompute it from the inline state the operator
        # just authored so the surface sees the same bounds the
        # Band 2 preview shows.
        field.validation = validation_block_from_inline(
            new_data_type, new_min, new_max, new_step, new_list_csv,
        )

    # Delete rows whose ids were in the *previous* JSON state but
    # not in the new payload — i.e. operator clicked X on a row
    # that had been saved before. Rows that exist in DB but were
    # NEVER tracked in JSON (e.g. seeded DEFAULT_RESPONSE_FIELDS
    # rows on a fresh new-model instrument that the operator
    # hasn't yet round-tripped through Band 3) stay put — the
    # operator's payload reflects only what they're actively
    # managing, so missing ids without provenance mean "leave
    # alone", not "delete".
    #
    # ``cascade="all, delete-orphan"`` on the responses
    # relationship would silently cascade if we just ``db.delete``;
    # intercept by checking for attached Response rows first and
    # raising so the route surfaces the error rather than letting
    # the operator nuke saved response data invisibly.
    for rf_id in previous_json_ids - seen_ids:
        field = existing_by_id.get(rf_id)
        if field is None:
            continue
        if field.responses:
            raise ResponsesPresentError(len(field.responses))
        db.delete(field)


def _sync_display_field_visibility(
    db: Session,
    *,
    instrument: Instrument,
    selected_keys: set[str] | None,
    actor: User,
) -> None:
    """Gap 1 — propagate the operator's pill selection (Band 2's
    ``selected_display_keys``) onto each
    ``InstrumentDisplayField.visible`` so the reviewer surface
    honours the toggle.

    For every non-locked display field on the instrument: visible
    is set True when the field's canonical
    ``"{source_type}.{source_field}"`` key is in ``selected_keys``,
    False otherwise. Locked rows (Name / Email) always stay
    visible — :func:`update_display_field` would refuse the flip
    anyway, but we skip the call to keep the audit log quiet.
    """
    if selected_keys is None:
        return
    # Local import to avoid module-load circular dep:
    # _display_fields → _band2 already exists via the
    # public re-exports in __init__.py.
    from app.services.instruments._display_fields import (
        is_locked_display_source,
        update_display_field,
    )

    for field in list(instrument.display_fields):
        if is_locked_display_source(field.source_type, field.source_field):
            continue
        key = f"{field.source_type}.{field.source_field}"
        desired = key in selected_keys
        if field.visible == desired:
            continue
        update_display_field(
            db,
            field=field,
            label=field.label,
            visible=desired,
            actor=actor,
        )
