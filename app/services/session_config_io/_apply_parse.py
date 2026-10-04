"""Parse-phase orchestration — row-level dispatch + cross-row validation.

``_parse_rows`` walks every CSV row, dispatches the section-specific
``_apply_*_kv`` routers via :func:`_route_row`, then runs
``_cross_row_errors`` to surface uniqueness / required-field issues.
"""
from __future__ import annotations

from ._apply_data_shape import _apply_data_shape_kv
from ._apply_email import _apply_email_kv
from ._apply_instrument import _apply_instrument_kv
from ._apply_rule_set import _apply_rule_set_kv
from ._apply_session import SESSION_FALLBACK_KEYS, _apply_session_kv
from ._apply_session_tag import _apply_session_tag_kv
from ._apply_shared import (
    _VALID_DATA_TYPES,
    _ParsedConfig,
    _ParseError,
)
from ._rows import Row
from app.services.instruments._band2 import INTEGER_WHOLE_BOUNDS_MESSAGE
from app.services.instruments._response_fields import (
    DEFAULT_RESPONSE_FIELDS,
    _inline_kwargs_from_default_spec,
)

# The Band 3 per-cell rules live with the editor's validator; the import
# borrows them rather than keeping a second copy. `_PER_CELL_VALID_MODES`
# is the single table both writers answer to (19C Item 9).
from app.services.visibility_policies import (
    VisibilityPolicyError,
    decode_mode,
    valid_modes_for_cell,
)


# ApplyError is used by both this module (cross-row errors) and the
# orchestrator ``_apply.py``; defined here to keep the dependency
# graph acyclic.
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import ReviewSession

# 19T Item 10 — the type a response field without a data_type imports as.
_DEFAULT_DATA_TYPE = _inline_kwargs_from_default_spec(DEFAULT_RESPONSE_FIELDS[0])[
    "_inline_data_type"
]


@dataclass(frozen=True)
class ApplyError:
    """One validation / parse error from
    ``apply_session_config``."""

    row_number: int
    """1-based CSV row number; ``0`` for global / cross-row errors
    (e.g. an unresolved ``rule_set_name`` reference)."""

    field: str
    message: str


def _parse_rows(rows: list[Row]) -> tuple[_ParsedConfig, list[ApplyError]]:
    plan = _ParsedConfig()
    errors: list[ApplyError] = []

    for index, row in enumerate(rows, start=1):
        field_path = (row.field or "").strip()
        if not field_path:
            continue
        data_type = (row.data_type or "").strip().lower()
        if data_type and data_type not in _VALID_DATA_TYPES:
            errors.append(
                ApplyError(
                    row_number=index,
                    field=field_path,
                    message=(
                        f"unknown data_type {row.data_type!r}; expected "
                        f"one of {sorted(_VALID_DATA_TYPES)}"
                    ),
                )
            )
            continue

        try:
            _route_row(plan, index, field_path, row.value, data_type)
        except _ParseError as exc:
            errors.append(
                ApplyError(
                    row_number=index,
                    field=field_path,
                    message=str(exc),
                )
            )

    # Cross-row validations. These run after row parsing so the
    # error list orders parse errors first.
    errors.extend(_cross_row_errors(plan))
    _drop_retired_view_policy_modes(plan)
    errors.extend(_view_policy_cell_errors(plan))
    errors.extend(_branch_errors(plan))
    errors.extend(_length_errors(plan))
    return plan, errors


def _column_length(model: type, name: str) -> int | None:
    """The declared length of ``model``'s ``name`` column, or ``None``
    when there is no such column or it has no cap (``Text``)."""
    column = model.__table__.columns.get(name)
    return getattr(column.type, "length", None) if column is not None else None


def _length_errors(plan: _ParsedConfig) -> list[ApplyError]:
    """A value longer than the column it lands in passes SQLite and
    fails phase 2 on Postgres as a ``DataError`` — a 500, not a report
    (findings D32). Check every string the import writes against its
    column's declared length, so the limits cannot drift from the
    schema. Tags are checked by ``normalize_tag`` already."""
    from dataclasses import fields as _fields

    from app.db.models import (
        DataShape,
        Instrument,
        InstrumentDisplayField,
        InstrumentResponseField,
        ReviewSession,
        SessionRuleSet,
    )

    errors: list[ApplyError] = []

    def check(field: str, value: object, limit: int | None) -> None:
        if isinstance(value, str) and limit is not None and len(value) > limit:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=field,
                    message=(
                        f"{len(value)} characters; at most {limit} fit"
                    ),
                )
            )

    def check_spec(prefix: str, spec: object, model: type) -> None:
        for f in _fields(spec):
            check(
                f"{prefix}.{f.name}",
                getattr(spec, f.name),
                _column_length(model, f.name),
            )

    # The fallback keys land only where the destination is blank, which
    # phase 1 cannot see; ``session_fallback_length_errors`` checks them
    # against the destination.
    for key, value in plan.session_overrides.items():
        if key in SESSION_FALLBACK_KEYS:
            continue
        check(f"session.{key}", value, _column_length(ReviewSession, key))
    for n, instrument in sorted(plan.instruments.items()):
        check_spec(f"instruments[{n}]", instrument, Instrument)
        for m, df in sorted(instrument.display_fields.items()):
            check_spec(
                f"instruments[{n}].display_fields[{m}]",
                df,
                InstrumentDisplayField,
            )
        for m, rf in sorted(instrument.response_fields.items()):
            check_spec(
                f"instruments[{n}].response_fields[{m}]",
                rf,
                InstrumentResponseField,
            )
    for n, rule_set in sorted(plan.session_rule_sets.items()):
        check_spec(f"session_rule_sets[{n}]", rule_set, SessionRuleSet)
    for n, shape in sorted(plan.data_shapes.items()):
        # Only the shapes phase 2 writes, as for the duplicate-name
        # rule; ``self_review_handling`` is coerced to a known value
        # there, so its raw length never reaches the column.
        if not shape.name or shape.axis not in ("reviewer", "reviewee"):
            continue
        check(f"data_shapes[{n}].name", shape.name, _column_length(DataShape, "name"))
        for f in _fields(shape):
            if f.name in ("name", "self_review_handling"):
                continue
            check(
                f"data_shapes[{n}].{f.name}",
                getattr(shape, f.name),
                _column_length(DataShape, f.name),
            )
    return errors


def session_fallback_length_errors(
    plan: _ParsedConfig, review_session: ReviewSession
) -> list[ApplyError]:
    """The length check for the ``session.*`` fallback keys, which land
    only where ``review_session``'s value is blank. A long value the
    destination ignores is not an error."""
    from app.db.models import ReviewSession

    errors: list[ApplyError] = []
    for key in SESSION_FALLBACK_KEYS:
        value = plan.session_overrides.get(key)
        if not isinstance(value, str):
            continue
        if getattr(review_session, key, None) not in (None, ""):
            continue
        limit = _column_length(ReviewSession, key)
        if limit is not None and len(value) > limit:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"session.{key}",
                    message=f"{len(value)} characters; at most {limit} fit",
                )
            )
    return errors


@dataclass
class _PlannedField:
    """A parsed response field in the shape the branching rules read
    (``app.services.responses.BranchField``), keyed by its CSV position."""

    id: int
    label: str
    order: int
    required: bool
    visible: bool
    branch_parent_id: int | None
    branch_op: str | None
    branch_value: str | None
    _inline_data_type: str | None
    _inline_list_csv: str | None
    branch_mode: str | None = None


def _branch_errors(plan: _ParsedConfig) -> list[ApplyError]:
    """19T Item 10 — each instrument's parsed fields against the
    branching rules, before anything is applied: a ``branch_parent``
    names a ``field_key`` of the same instrument, and the fields keep two
    levels at most (19T Item 14), a non-String parent with a valid condition, a required governed
    field only beside an active required ungoverned one (19T Item 11), and
    a branch directly after its parent. A file that breaks one is refused
    with the rule named rather than applied with the branch dropped."""
    from app.services.responses import (
        branch_structure_errors,
        hide_below_hidden_parents,
    )

    errors: list[ApplyError] = []
    for n, instrument in sorted(plan.instruments.items()):
        specs = sorted(instrument.response_fields.items())
        # Any of the branch cells, so a lone ``branch_value`` (or, from 19T
        # Item 13, ``branch_mode``) is an orphaned condition refused here,
        # not stored (Codex on #2642).
        if not any(
            rf.branch_parent or rf.branch_op or rf.branch_value or rf.branch_mode
            for _, rf in specs
        ):
            continue
        position_by_key = {rf.field_key: m for m, rf in specs if rf.field_key}
        planned: list[_PlannedField] = []
        for m, rf in specs:
            parent_position = None
            if rf.branch_parent:
                parent_position = position_by_key.get(rf.branch_parent)
                if parent_position is None:
                    errors.append(
                        ApplyError(
                            row_number=0,
                            field=(
                                f"instruments[{n}].response_fields[{m}]"
                                ".branch_parent"
                            ),
                            message=(
                                f"no response field {rf.branch_parent!r} on "
                                "this instrument"
                            ),
                        )
                    )
                    continue
            planned.append(
                _PlannedField(
                    id=m,
                    label=rf.label or rf.field_key or f"response_fields[{m}]",
                    order=m,
                    required=rf.required,
                    visible=rf.visible,
                    branch_parent_id=parent_position,
                    branch_op=rf.branch_op,
                    branch_value=rf.branch_value,
                    # An absent data_type imports as the default field's
                    # (``_apply_instruments``), so it is judged as one.
                    _inline_data_type=rf.data_type or _DEFAULT_DATA_TYPE,
                    _inline_list_csv=rf.list_csv,
                    branch_mode=rf.branch_mode,
                )
            )
        # A hidden parent hides its branch when the file is applied
        # (``_apply_branches``), so the rules judge a governed field the
        # same way here: both phases give ``branch_structure_errors`` the
        # same visibility (19T Item 11's cumulative read), at either level
        # (19T Item 14).
        hide_below_hidden_parents(planned)
        errors.extend(
            ApplyError(
                row_number=0,
                field=f"instruments[{n}].response_fields",
                message=f"{label}: {msg}",
            )
            for label, msg in branch_structure_errors(planned)
        )
    return errors

_VP_WINDOWS: tuple[str, ...] = ("while_ongoing", "after_release")


def _drop_retired_view_policy_modes(plan: _ParsedConfig) -> None:
    """Read a retired mode in an older bundle as off, before the cell
    check refuses it.

    The reviewer's "Responses released" cell lost ``summarized``
    (``aggregated`` + ``deidentified``) on 2026-10-02 (findings A18): no
    reviewer summary view was ever built, so since #2723 such a grant
    hid the reviewer's answers like an off cell. A bundle exported
    before then imports that cell as off rather than refusing the whole
    apply. Only that exact pair is rewritten; a half-set or incoherent
    pair is left for :func:`_view_policy_cell_errors` to refuse.
    """
    for instrument in plan.instruments.values():
        vp = instrument.view_policies.get("peer_reviewer")
        if vp is None:
            continue
        if (
            vp.after_release_granularity == "aggregated"
            and vp.after_release_identification == "deidentified"
        ):
            vp.after_release_granularity = None
            vp.after_release_identification = None


def _view_policy_cell_errors(plan: _ParsedConfig) -> list[ApplyError]:
    """Refuse a visibility cell the visibility editor would refuse.

    Two writers create ``instrument_view_policies`` rows.
    ``visibility_policies.upsert_policy`` validates the
    ``(audience, window)`` cell against ``_PER_CELL_VALID_MODES``;
    the import writer (``_apply_instrument``) builds the row from
    this plan. Until 19C Item 9 only the *vocabulary* was checked
    here — ``row`` / ``aggregated``, ``identified`` /
    ``deidentified`` — never the cell the values landed in, so a
    Settings CSV could persist what the editor refuses. The one
    that mattered is ``("reviewee", "while_ongoing")``, whose only
    legal mode is ``None``: a reviewee may never read responses
    while the review is running, and an imported row saying
    otherwise was honoured by the resolver like any other.

    A cell is a **pair** of rows, so this cannot live in the row
    router — it runs here, once both rows are parsed, and before
    ``_apply_plan`` writes anything.

    Three distinct failures, deliberately not collapsed:

    * one half of the pair set and the other empty — not a mode at
      all. ``decode_pair_to_mode`` reads that as "off", which would
      let a half-authored cell pass as ``None``;
    * both set but not a stored pair (the reserved-incoherent
      ``aggregated`` + ``identified``); and
    * a real mode in a cell that does not accept it.
    """
    errors: list[ApplyError] = []
    for n, instrument in sorted(plan.instruments.items()):
        for audience in sorted(instrument.view_policies):
            vp = instrument.view_policies[audience]
            for window in _VP_WINDOWS:
                granularity = getattr(vp, f"{window}_granularity")
                identification = getattr(vp, f"{window}_identification")
                field = (
                    f"instruments[{n}].view_policies[{audience}]"
                    f".{window}_granularity"
                )
                if (granularity is None) != (identification is None):
                    errors.append(
                        ApplyError(
                            row_number=0,
                            field=field,
                            message=(
                                f"view-policy cell {audience!r} "
                                f"{window} is half-set "
                                f"(granularity={granularity!r}, "
                                f"identification={identification!r}); "
                                "set both or neither"
                            ),
                        )
                    )
                    continue
                if granularity is None:
                    mode: str | None = None
                else:
                    try:
                        mode = decode_mode(granularity, identification)
                    except VisibilityPolicyError as exc:
                        errors.append(
                            ApplyError(
                                row_number=0,
                                field=field,
                                message=(
                                    f"view-policy cell {audience!r} "
                                    f"{window}: {exc.message}"
                                ),
                            )
                        )
                        continue
                allowed = valid_modes_for_cell(audience, window)
                if mode not in allowed:
                    errors.append(
                        ApplyError(
                            row_number=0,
                            field=field,
                            message=(
                                f"audience {audience!r} {window} cell "
                                f"only accepts modes in "
                                f"{sorted(repr(v) for v in allowed)}; "
                                f"got {mode!r}"
                            ),
                        )
                    )
    return errors



def _route_row(
    plan: _ParsedConfig,
    index: int,
    field_path: str,
    value: str,
    data_type: str,
) -> None:
    if field_path.startswith("session."):
        _apply_session_kv(plan, field_path, value)
        return
    if field_path.startswith("email_overrides."):
        _apply_email_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("instruments["):
        _apply_instrument_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("session_rule_sets["):
        _apply_rule_set_kv(plan, field_path, value, data_type)
        return
    # ``field_labels.*`` (retired 19C Item 1 — roster headers carry
    # labels now) and ``rtds[`` (retired with the
    # ``response_type_definitions`` table on 2026-05-26) both fall
    # through to the unknown-key silent-ignore below. Neither needs a
    # branch of its own: an old bundle carrying them imports with the
    # rows dropped, which is what a branch would have done anyway.
    if field_path.startswith("data_shapes["):
        _apply_data_shape_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("session_tags["):
        _apply_session_tag_kv(plan, field_path, value)
        return
    del index
    # Unknown field path — silently ignore. Defensive: the export
    # is the canonical key vocabulary; future export-side keys
    # should land before importer-side support, so unknown keys
    # are forward-compatible padding.


def _cross_row_errors(plan: _ParsedConfig) -> list[ApplyError]:
    errors: list[ApplyError] = []
    # RuleSet-name uniqueness within the snapshot.
    seen_names: dict[str, int] = {}
    for n, spec in sorted(plan.session_rule_sets.items()):
        if not spec.name:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"session_rule_sets[{n}].name",
                    message="name is required",
                )
            )
            continue
        if spec.name in seen_names:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"session_rule_sets[{n}].name",
                    message=(
                        f"duplicate session_rule_sets name {spec.name!r} "
                        f"(also at session_rule_sets[{seen_names[spec.name]}])"
                    ),
                )
            )
        else:
            seen_names[spec.name] = n
    # Per-instrument ``rule_set_name`` resolves against either a
    # ``session_rule_sets[N]`` block in the same CSV.
    # Wave 5 PR 5.2 retired the seeded set, so seeded names no
    # longer auto-resolve — every referenced rule_set_name must
    # appear as a session_rule_sets[N] block in the CSV.
    valid_rule_set_names = set(seen_names)
    for n, instrument in sorted(plan.instruments.items()):
        if (
            instrument.rule_set_name
            and instrument.rule_set_name not in valid_rule_set_names
        ):
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"instruments[{n}].rule_set_name",
                    message=(
                        f"no such RuleSet on this session: "
                        f"{instrument.rule_set_name!r}"
                    ),
                )
            )
    # Per-response-field ``response_type`` was a per-session RTD
    # name lookup pre-2026-05-26; the table retired and the value
    # now stores verbatim into ``_inline_response_type``. Any
    # non-empty string is accepted.
    # Instrument required fields + display-/response-field required
    # fields.
    for n, instrument in sorted(plan.instruments.items()):
        if not instrument.name:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"instruments[{n}].name",
                    message="name is required",
                )
            )
        for m, df in sorted(instrument.display_fields.items()):
            if not df.source_type:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].display_fields[{m}]"
                            ".source_type"
                        ),
                        message="source_type is required",
                    )
                )
        # ``field_key`` is unique within an instrument
        # (``uq_instrument_field_key``); a repeat would reach the
        # constraint in phase 2 as an ``IntegrityError``.
        seen_keys: dict[str, int] = {}
        for m, rf in sorted(instrument.response_fields.items()):
            if not rf.field_key:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}].field_key"
                        ),
                        message="field_key is required",
                    )
                )
            elif rf.field_key in seen_keys:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}].field_key"
                        ),
                        message=(
                            f"duplicate field_key {rf.field_key!r} "
                            f"(also at instruments[{n}].response_fields"
                            f"[{seen_keys[rf.field_key]}])"
                        ),
                    )
                )
            else:
                seen_keys[rf.field_key] = m
            # Band 2 refuses a fractional bound on an Integer field
            # (``_band2._integer_bounds_error``). The import must too:
            # its ``validation`` block casts bounds with ``int``, so
            # 1.5 would be stored as 1 for the reviewer while the
            # field's own Min still read 1.5.
            if rf.data_type == "Integer":
                for key in ("min", "max", "step"):
                    value = getattr(rf, key)
                    if value is not None and not float(value).is_integer():
                        errors.append(
                            ApplyError(
                                row_number=0,
                                field=(
                                    f"instruments[{n}].response_fields"
                                    f"[{m}].{key}"
                                ),
                                message=INTEGER_WHOLE_BOUNDS_MESSAGE,
                            )
                        )
            if not rf.label:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}].label"
                        ),
                        message="label is required",
                    )
                )
            if not rf.response_type:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}]"
                            ".response_type"
                        ),
                        message="response_type is required",
                    )
                )
    # Data-shape names are unique within a session
    # (``uq_data_shape_session_name``). Only the shapes phase 2 writes
    # count: one with no name or an unknown axis is skipped there
    # (``_apply_data_shapes``), so it cannot collide.
    seen_shapes: dict[str, int] = {}
    for n, shape in sorted(plan.data_shapes.items()):
        if not shape.name or shape.axis not in ("reviewer", "reviewee"):
            continue
        if shape.name in seen_shapes:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"data_shapes[{n}].name",
                    message=(
                        f"duplicate data_shapes name {shape.name!r} "
                        f"(also at data_shapes[{seen_shapes[shape.name]}])"
                    ),
                )
            )
        else:
            seen_shapes[shape.name] = n
    return errors
