"""Instruments service package.

Was a single 2,469-line module until the §12.A ladder
(``guide/archive/major_refactor.md``) carved it into feature-area
sub-modules. The public surface is preserved here as an explicit
re-export wall so external callers — both
``from app.services import instruments`` and
``from app.services.instruments import <symbol>`` — continue to
work byte-identical to the pre-package shape.

Final layout (post-PR-4):

- ``_state.py`` — cross-slice plumbing
  (``saved_state_for_session`` + ``_instrument_label``); read by
  every other slice, never reads from them.
- ``_rtds.py`` — Response Type Definitions catalog + operator
  CRUD (PR 1).
- ``_display_fields.py`` — display-field constants, locked-row
  gates, operator CRUD, lazy-seeding helpers (PR 2).
- ``_response_fields.py`` — response-field catalog, slug helpers,
  operator CRUD, ``bulk_save_fields`` (PR 3).
- ``_instrument_crud.py`` — instrument lifecycle, default-
  instrument seeding, session-level bulk toggles (PR 4).
"""

from __future__ import annotations

# Cross-slice state. ``_SAVED_STATE_EVENT_TYPES`` stays private to
# ``_state.py`` — only ``saved_state_for_session`` is part of the
# public surface (called from ``views.py``). ``_instrument_label``
# is private but exercised by
# ``tests/integration/test_segment_11l_short_label.py`` — preserve
# it in the re-export wall so the test surface stays byte-identical.
from ._state import _instrument_label, saved_state_for_session

# Response Type Definitions (sliced in PR 1). ``ResponseTypeDefinition``
# is the model class — re-exported through the RTDs slice (which is
# its natural home) to preserve the pre-package surface where two
# route handlers reach it as ``instruments_service.ResponseTypeDefinition``.
from ._rtds import (
    SEEDED_RESPONSE_TYPE_DEFINITIONS,
    OperatorResponseTypeDefinition,
    ResponseTypeDefinition,
    RTDDeleteWouldEmptyInstrumentError,
    RTDInUseError,
    RTDLibraryConflictError,
    RTDLockedError,
    RTDPrecisionError,
    RTDValidationError,
    add_response_type_definition,
    add_rtd_from_library,
    assert_rtd_precision,
    count_rtd_dependents,
    count_rtd_session_copies,
    delete_operator_rtd,
    delete_response_type_definition,
    ensure_default_response_type_definitions,
    get_session_rtds,
    list_library_rtds_not_in_session,
    list_operator_rtds,
    save_session_rtd_to_library,
    update_response_type_definition,
    validation_block_for_rtd,
)

# Display fields (sliced in PR 2).
from ._display_fields import (
    DisplaySourceError,
    LockedDisplayFieldError,
    SortSpecError,
    add_display_field,
    delete_display_field,
    display_field_label,
    display_field_value,
    is_locked_display_source,
    move_display_field,
    prune_unpopulated_display_fields,
    seed_display_fields_from_assignments,
    seed_display_fields_from_reviewees,
    set_sort_display_fields,
    update_display_field,
)

# Response fields (sliced in PR 3). ``InstrumentResponseField`` is
# the model class — re-exported through the response-fields slice
# (its natural home) to preserve the pre-package surface where two
# route handlers reach it as
# ``instruments_service.InstrumentResponseField``.
from ._response_fields import (
    DEFAULT_RESPONSE_FIELDS,
    FieldKeyError,
    InstrumentResponseField,
    ResponsesPresentError,
    add_default_response_field,
    add_response_field,
    bulk_save_fields,
    delete_response_field,
    move_response_field,
    slugify_field_key,
    update_response_field,
)

# Instrument CRUD (sliced in PR 4 — the final slice).
from ._instrument_crud import (
    DEFAULT_INSTRUMENT_NAME,
    GROUP_KIND_SENTINEL,
    bulk_set_accepting,
    bulk_set_visibility,
    create_instrument,
    decode_group_kind,
    delete_instrument,
    encode_group_kind,
    ensure_default_instrument,
    ensure_locked_display_fields,
    group_boundary_pairs,
    replicate_instrument,
    has_unpinned,
    pin_rule_set,
    set_column_widths,
    set_group_boundary,
    set_unit_of_review,
    update_instrument_description,
    update_short_label,
)
from ._band1 import (
    Band1ParseError,
    decode_band1_state,
    parse_band1_form,
    parse_link3_form,
    set_band1_assignment_rules,
)


__all__ = [
    # Cross-slice (lives in _state.py).
    "saved_state_for_session",
    # Everything below still lives in _legacy.py and migrates out
    # across the §12.A slice PRs.
    "DEFAULT_INSTRUMENT_NAME",
    "DEFAULT_RESPONSE_FIELDS",
    "GROUP_KIND_SENTINEL",
    "SEEDED_RESPONSE_TYPE_DEFINITIONS",
    "DisplaySourceError",
    "FieldKeyError",
    "InstrumentResponseField",
    "LockedDisplayFieldError",
    "OperatorResponseTypeDefinition",
    "ResponseTypeDefinition",
    "ResponsesPresentError",
    "RTDDeleteWouldEmptyInstrumentError",
    "RTDInUseError",
    "RTDLibraryConflictError",
    "RTDLockedError",
    "RTDPrecisionError",
    "RTDValidationError",
    "SortSpecError",
    "_instrument_label",
    "add_default_response_field",
    "add_display_field",
    "add_response_field",
    "add_response_type_definition",
    "add_rtd_from_library",
    "assert_rtd_precision",
    "bulk_save_fields",
    "bulk_set_accepting",
    "bulk_set_visibility",
    "count_rtd_dependents",
    "count_rtd_session_copies",
    "create_instrument",
    "decode_group_kind",
    "delete_display_field",
    "delete_instrument",
    "encode_group_kind",
    "delete_operator_rtd",
    "delete_response_field",
    "delete_response_type_definition",
    "display_field_label",
    "display_field_value",
    "ensure_default_instrument",
    "ensure_default_response_type_definitions",
    "ensure_locked_display_fields",
    "Band1ParseError",
    "decode_band1_state",
    "parse_band1_form",
    "parse_link3_form",
    "set_band1_assignment_rules",
    "set_unit_of_review",
    "group_boundary_pairs",
    "replicate_instrument",
    "has_unpinned",
    "get_session_rtds",
    "is_locked_display_source",
    "list_library_rtds_not_in_session",
    "list_operator_rtds",
    "move_display_field",
    "move_response_field",
    "prune_unpopulated_display_fields",
    "save_session_rtd_to_library",
    "seed_display_fields_from_assignments",
    "seed_display_fields_from_reviewees",
    "set_column_widths",
    "set_group_boundary",
    "set_sort_display_fields",
    "pin_rule_set",
    "slugify_field_key",
    "update_display_field",
    "update_instrument_description",
    "update_response_field",
    "update_response_type_definition",
    "update_short_label",
    "validation_block_for_rtd",
]
