"""The email composer's field state (segment 14F rung 2b): what each box
shows, and whether the form differs from what is saved.

After Send a test to me the composer re-renders with what the operator
had typed, unsaved, so a test never discards a draft. The route hands
this the submitted values; everything else comes from the session.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.db.models import ReviewSession
from app.services import email_templates


@dataclass(frozen=True)
class ComposerFields:
    #: One dict per editable field: ``field``, ``key``, ``value`` (saved,
    #: or the default), ``default``, ``has_override``, ``shown`` (what the
    #: box holds) and ``unsaved`` (``shown`` differs from what is saved).
    rows: list[dict[str, Any]]
    #: What the confirmation tab's send-on-submit box shows.
    responses_received_enabled: bool
    #: Whether anything on the form differs from what is saved, which
    #: renders Save live.
    unsaved_edits: bool


def build_composer_fields(
    review_session: ReviewSession,
    template: str,
    *,
    edited: Mapping[str, str] | None = None,
    edited_enabled: bool | None = None,
) -> ComposerFields:
    """The composer's fields for ``template``: saved, or overlaid with
    ``edited`` (override key → typed value) and ``edited_enabled``."""
    rows: list[dict[str, Any]] = []
    for spec in email_templates.TEMPLATE_FIELDS[template]:
        override = email_templates.get_override(review_session, spec["key"])
        saved_shown = override if override is not None else ""
        shown = edited.get(spec["key"], saved_shown) if edited is not None else saved_shown
        rows.append(
            {
                "field": spec["field"],
                "key": spec["key"],
                "value": override if override is not None else spec["default"],
                "default": spec["default"],
                "has_override": override is not None,
                "shown": shown,
                "unsaved": shown != saved_shown,
            }
        )
    saved_enabled = email_templates.responses_received_enabled(review_session)
    shown_enabled = saved_enabled if edited_enabled is None else edited_enabled
    return ComposerFields(
        rows=rows,
        responses_received_enabled=shown_enabled,
        unsaved_edits=any(row["unsaved"] for row in rows) or shown_enabled != saved_enabled,
    )
