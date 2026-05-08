"""Instruments service package.

Was a single 2,469-line module until the §12.A ladder
(``guide/major_refactor.md``) carved it into feature-area
sub-modules. The public surface is preserved here as an explicit
re-export wall so external callers — both
``from app.services import instruments`` and
``from app.services.instruments import <symbol>`` — continue to
work byte-identical to the pre-package shape.

Slice modules (``_rtds.py``, ``_display_fields.py``,
``_response_fields.py``, ``_instrument_crud.py``) get carved out
of ``_legacy.py`` across PRs 1-4 of the §12.A ladder. ``_state.py``
already houses ``saved_state_for_session`` plus its companion
constant — those are read by every slice and live at the top to
keep the import graph one-way (slices → _state, never the other
direction).
"""

from __future__ import annotations

# Cross-slice state. ``_SAVED_STATE_EVENT_TYPES`` stays private to
# ``_state.py`` — only ``saved_state_for_session`` is part of the
# public surface (called from ``views.py``). ``_instrument_label``
# is private but exercised by
# ``tests/integration/test_segment_11l_short_label.py`` — preserve
# it in the re-export wall so the test surface stays byte-identical.
from ._state import _instrument_label, saved_state_for_session

# Response Type Definitions (sliced in PR 1).
from ._rtds import (
    SEEDED_RESPONSE_TYPE_DEFINITIONS,
    RTDDeleteWouldEmptyInstrumentError,
    RTDInUseError,
    RTDLockedError,
    RTDPrecisionError,
    RTDValidationError,
    add_response_type_definition,
    assert_rtd_precision,
    count_rtd_dependents,
    delete_response_type_definition,
    ensure_default_response_type_definitions,
    get_session_rtds,
    update_response_type_definition,
    validation_block_for_rtd,
)

# Display fields (sliced in PR 2).
from ._display_fields import (
    DisplaySourceError,
    LockedDisplayFieldError,
    add_display_field,
    delete_display_field,
    display_field_label,
    display_field_value,
    is_locked_display_source,
    move_display_field,
    prune_unpopulated_display_fields,
    seed_display_fields_from_assignments,
    seed_display_fields_from_reviewees,
    update_display_field,
)

# Everything else still in the legacy container; carved out by
# PRs 3-4.
#
# Model-class re-exports (``InstrumentResponseField``,
# ``ResponseTypeDefinition``) preserve the pre-package surface —
# the flat module surfaced these as attributes via its own
# ``from app.db.models import ...`` block, and a couple of route
# handlers reach them as ``instruments_service.<Model>``. Callers
# could import from ``app.db.models`` directly; cleaning those up
# is out of scope for the §12.A pure-relocation ladder.
from ._legacy import (
    DEFAULT_INSTRUMENT_NAME,
    DEFAULT_RESPONSE_FIELDS,
    FieldKeyError,
    InstrumentResponseField,
    ResponseTypeDefinition,
    ResponsesPresentError,
    add_default_response_field,
    add_response_field,
    bulk_save_fields,
    bulk_set_accepting,
    bulk_set_visibility,
    create_instrument,
    delete_instrument,
    delete_response_field,
    ensure_default_instrument,
    ensure_locked_display_fields,
    move_response_field,
    slugify_field_key,
    update_instrument_description,
    update_response_field,
    update_short_label,
)


__all__ = [
    # Cross-slice (lives in _state.py).
    "saved_state_for_session",
    # Everything below still lives in _legacy.py and migrates out
    # across the §12.A slice PRs.
    "DEFAULT_INSTRUMENT_NAME",
    "DEFAULT_RESPONSE_FIELDS",
    "SEEDED_RESPONSE_TYPE_DEFINITIONS",
    "DisplaySourceError",
    "FieldKeyError",
    "InstrumentResponseField",
    "LockedDisplayFieldError",
    "ResponseTypeDefinition",
    "ResponsesPresentError",
    "RTDDeleteWouldEmptyInstrumentError",
    "RTDInUseError",
    "RTDLockedError",
    "RTDPrecisionError",
    "RTDValidationError",
    "_instrument_label",
    "add_default_response_field",
    "add_display_field",
    "add_response_field",
    "add_response_type_definition",
    "assert_rtd_precision",
    "bulk_save_fields",
    "bulk_set_accepting",
    "bulk_set_visibility",
    "count_rtd_dependents",
    "create_instrument",
    "delete_display_field",
    "delete_instrument",
    "delete_response_field",
    "delete_response_type_definition",
    "display_field_label",
    "display_field_value",
    "ensure_default_instrument",
    "ensure_default_response_type_definitions",
    "ensure_locked_display_fields",
    "get_session_rtds",
    "is_locked_display_source",
    "move_display_field",
    "move_response_field",
    "prune_unpopulated_display_fields",
    "seed_display_fields_from_assignments",
    "seed_display_fields_from_reviewees",
    "slugify_field_key",
    "update_display_field",
    "update_instrument_description",
    "update_response_field",
    "update_response_type_definition",
    "update_short_label",
    "validation_block_for_rtd",
]
