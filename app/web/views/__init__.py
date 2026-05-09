"""View-shape adapter package.

Was a single 3,483-line module until the §12.B ladder
(``guide/major_refactor.md``) carved it into per-page / per-entity
sub-modules. The public surface is preserved here as an explicit
re-export wall so external callers — both
``from app.web import views`` and
``from app.web.views import <symbol>`` — continue to work
byte-identical to the pre-package shape.

Slice modules get carved out of ``_legacy.py`` across PRs 1-9 of
the §12.B ladder (smallest first):

- PR 1  ``_responses.py``      — Responses page rows
- PR 2  ``_extract_data.py``   — Extract Data card
- PR 3  ``_invitations.py``    — Invitations page rows
- PR 4  ``_filters.py``        — shared filter / search helpers
- PR 5  ``_setup.py``           — Setup overview rows + status pills
- PR 6  ``_instruments.py``    — Instruments page context
- PR 7  ``_quick_setup.py``    — Quick Setup card
- PR 8  ``_validate.py``       — Validate page
- PR 9  ``_previews.py``       — Email + reviewer-surface previews
- PR 10 ``_rule_builder.py``   — Rule Builder + Rule Based card

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
    QuickSetupRuleSetOption,
    QuickSetupSlot,
    build_new_session_quick_setup_context,
    build_quick_setup_context,
)

# Everything else still in the legacy container; carved out by
# PRs 8-10.
from ._legacy import (
    EMAIL_PREVIEW_TABS,
    PREVIEW_INVITE_URL_PLACEHOLDER,
    PREVIEW_PICKER_REVIEWEE_PEEK_COUNT,
    RULE_BUILDER_BLANK_SENTINEL_ID,
    RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION,
    AvailableRuleSetEntry,
    EditableRule,
    EmailBody,
    EmailPreviewTab,
    IssueSourceGroup,
    PreviewPickerContext,
    PreviewPickerOption,
    RuleBasedCardContext,
    RuleBasedLastGenerated,
    RuleBasedSelectorOption,
    RuleBuilderContext,
    RuleBuilderOption,
    RuleLine,
    SetupCoverageRow,
    SeverityChip,
    SurfacePreviewContext,
    SurfacePreviewMissing,
    ValidateContext,
    build_email_preview_body,
    build_preview_picker_context,
    build_rule_based_card_context,
    build_rule_builder_context,
    build_surface_preview_context,
    build_validate_context,
    email_preview_from_display,
    merge_tags_for_template,
    resolve_email_preview_tab,
    validate_lifecycle_copy,
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
    "QuickSetupRuleSetOption",
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
    "page_button_label",
    "placeholder_for_field",
    "resolve_email_preview_tab",
    "responses_search_options",
    "session_status_pills",
    "validate_lifecycle_copy",
]
