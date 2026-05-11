"""View-shape adapter package.

Was a single 3,483-line module until the §12.B ladder
(``guide/archive/major_refactor.md``) carved it into per-page / per-entity
sub-modules. The public surface is preserved here as an explicit
re-export wall so external callers — both
``from app.web import views`` and
``from app.web.views import <symbol>`` — continue to work
byte-identical to the pre-package shape.

Final layout (post-PR-10):

- ``_responses.py``      — Responses page rows
- ``_extract_data.py``   — Extract Data card
- ``_invitations.py``    — Invitations page rows
- ``_filters.py``        — shared filter / search helpers
- ``_setup.py``          — Setup overview rows + status pills
- ``_instruments.py``    — Instruments page context
- ``_quick_setup.py``    — Quick Setup card
- ``_validate.py``       — Validate page
- ``_previews.py``       — Email + reviewer-surface previews
- ``_rule_builder.py``   — Rule Builder + Rule Based card

The ``views.py`` seam is the canonical "view-shape adapter" layer
(per CLAUDE.md / AGENTS.md): translates domain objects into the
dataclasses / row tuples templates iterate over. Routes import
from this package; templates do not.
"""

from __future__ import annotations

# Responses page rows (sliced in PR 1).
from ._responses import ResponsesRow, build_responses_rows

# Extract Data card on Session Home (sliced in PR 2).
from ._extract_data import (
    ExtractDataContext,
    ExtractDataRow,
    build_extract_data_context,
)

# Manage Invitations page rows (sliced in PR 3).
from ._invitations import InvitationsRow, build_invitations_rows

# Filter / search helpers shared by Invitations + Responses
# (sliced in PR 4).
from ._filters import (
    INVITATIONS_STATUS_OPTIONS,
    RESPONSES_STATUS_OPTIONS,
    filter_invitations_rows,
    filter_responses_rows,
    invitations_search_options,
    responses_search_options,
)

# Setup overview rows + standardized status-pills row (sliced in
# PR 5).
from ._setup import (
    SessionStatusPills,
    SetupRow,
    build_setup_rows,
    session_status_pills,
)

# Instruments page context + reviewer-surface heading / page-button
# helpers (sliced in PR 6).
from ._instruments import (
    InstrumentHeading,
    PageButton,
    build_instruments_context,
    constraint_summary_for_field,
    instrument_heading,
    page_button_label,
    placeholder_for_field,
)

# Quick Setup card on Session Home + new-session preview variant
# (sliced in PR 7).
from ._quick_setup import (
    QuickSetupContext,
    QuickSetupSlot,
    build_new_session_quick_setup_context,
    build_quick_setup_context,
)

# Validate page view-shape adapter (sliced in PR 8).
from ._validate import (
    IssueSourceGroup,
    SetupCoverageRow,
    SeverityChip,
    ValidateContext,
    build_validate_context,
    validate_lifecycle_copy,
)

# Previews page view-shapes (sliced in PR 9): reviewer picker,
# three-tab email previews, merge-tag editor strip, reviewer-
# surface preview card.
from ._previews import (
    EMAIL_PREVIEW_TABS,
    PREVIEW_INVITE_URL_PLACEHOLDER,
    PREVIEW_PICKER_REVIEWEE_PEEK_COUNT,
    EmailBody,
    EmailPreviewTab,
    PreviewPickerContext,
    PreviewPickerOption,
    SurfacePreviewContext,
    SurfacePreviewMissing,
    build_email_preview_body,
    build_preview_picker_context,
    build_surface_preview_context,
    email_preview_from_display,
    merge_tags_for_template,
    resolve_email_preview_tab,
)

# Rule Builder + Rule Based card on Setup → Assignments
# (sliced in PR 10 — the final slice).
from ._rule_builder import (
    RULE_BUILDER_BLANK_SENTINEL_ID,
    RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION,
    AvailableRuleSetEntry,
    EditableRule,
    RuleBasedCardContext,
    RuleBasedLastGenerated,
    RuleBasedSelectorOption,
    RuleBuilderContext,
    RuleBuilderOption,
    RuleLine,
    build_rule_based_card_context,
    build_rule_builder_context,
)

# Audit log viewer (Segment 16C PR 1 + PR 2 + PR 3).
from ._audit_log import (
    AuditDetailChangeRow,
    AuditDetailKVRow,
    AuditDetailRender,
    AuditDetailSection,
    AuditDetailSetChanges,
    AuditLogFilterFormContext,
    AuditLogRowsContext,
    AuditLogTableRow,
    build_audit_log_filter_form,
    build_audit_log_rows,
    filters_querystring,
    format_audit_detail,
    parse_audit_log_filters,
)

__all__ = [
    # Module-level constants.
    "EMAIL_PREVIEW_TABS",
    "INVITATIONS_STATUS_OPTIONS",
    "PREVIEW_INVITE_URL_PLACEHOLDER",
    "PREVIEW_PICKER_REVIEWEE_PEEK_COUNT",
    "RESPONSES_STATUS_OPTIONS",
    "RULE_BUILDER_BLANK_SENTINEL_ID",
    "RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION",
    # Dataclasses / context shapes.
    "AvailableRuleSetEntry",
    "EditableRule",
    "EmailBody",
    "EmailPreviewTab",
    "ExtractDataContext",
    "ExtractDataRow",
    "InstrumentHeading",
    "InvitationsRow",
    "IssueSourceGroup",
    "PageButton",
    "PreviewPickerContext",
    "PreviewPickerOption",
    "QuickSetupContext",
    "QuickSetupSlot",
    "ResponsesRow",
    "RuleBasedCardContext",
    "RuleBasedLastGenerated",
    "RuleBasedSelectorOption",
    "RuleBuilderContext",
    "RuleBuilderOption",
    "RuleLine",
    "SessionStatusPills",
    "SetupCoverageRow",
    "SetupRow",
    "SeverityChip",
    "SurfacePreviewContext",
    "SurfacePreviewMissing",
    "ValidateContext",
    # Builders / helpers.
    "build_email_preview_body",
    "build_extract_data_context",
    "build_instruments_context",
    "build_invitations_rows",
    "build_new_session_quick_setup_context",
    "build_preview_picker_context",
    "build_quick_setup_context",
    "build_responses_rows",
    "build_rule_based_card_context",
    "build_rule_builder_context",
    "build_setup_rows",
    "build_surface_preview_context",
    "build_validate_context",
    "constraint_summary_for_field",
    "email_preview_from_display",
    "filter_invitations_rows",
    "filter_responses_rows",
    "instrument_heading",
    "invitations_search_options",
    "merge_tags_for_template",
    "AuditDetailChangeRow",
    "AuditDetailKVRow",
    "AuditDetailRender",
    "AuditDetailSection",
    "AuditDetailSetChanges",
    "AuditLogFilterFormContext",
    "AuditLogRowsContext",
    "AuditLogTableRow",
    "build_audit_log_filter_form",
    "build_audit_log_rows",
    "filters_querystring",
    "format_audit_detail",
    "parse_audit_log_filters",
    "page_button_label",
    "placeholder_for_field",
    "resolve_email_preview_tab",
    "responses_search_options",
    "session_status_pills",
    "validate_lifecycle_copy",
]
