"""Parse-phase orchestration — row-level dispatch + cross-row validation.

``_parse_rows`` walks every CSV row, dispatches the section-specific
``_apply_*_kv`` routers via :func:`_route_row`, then runs
``_cross_row_errors`` to surface uniqueness / required-field issues.
"""
from __future__ import annotations

from ._apply_data_shape import _apply_data_shape_kv
from ._apply_email import _apply_email_kv
from ._apply_field_label import _apply_field_label_kv
from ._apply_instrument import _apply_instrument_kv
from ._apply_rule_set import _apply_rule_set_kv
from ._apply_session import _apply_session_kv
from ._apply_shared import (
    _VALID_DATA_TYPES,
    _ParsedConfig,
    _ParseError,
)
from ._rows import Row


# ApplyError is used by both this module (cross-row errors) and the
# orchestrator ``_apply.py``; defined here to keep the dependency
# graph acyclic.
from dataclasses import dataclass


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
    return plan, errors


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
    if field_path.startswith("rtds["):
        # Per-session ``response_type_definitions`` table retired
        # 2026-05-26 — old bundles may carry these rows. Silently
        # accept and drop; the response field bounds + data_type now
        # round-trip inline on the response_field_* rows.
        return
    if field_path.startswith("instruments["):
        _apply_instrument_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("session_rule_sets["):
        _apply_rule_set_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("field_labels."):
        _apply_field_label_kv(plan, field_path, value)
        return
    if field_path.startswith("data_shapes["):
        _apply_data_shape_kv(plan, field_path, value, data_type)
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
    return errors
