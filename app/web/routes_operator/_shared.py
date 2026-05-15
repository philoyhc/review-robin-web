"""Cross-slice plumbing for the operator route package.

Owns the single ``Jinja2Templates`` instance used by every operator
sub-module (so custom Jinja globals / filters register exactly once),
the lifecycle / edit-lock guards called from multiple slices, and the
Quick Setup cookie naming primitive.

Per ``guide/archive/major_refactor.md`` §3.0, slice modules import from this
file but ``_shared`` itself imports nothing from the package — that
invariant rules out import cycles regardless of how the slice graph
evolves.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession
from app.services import date_formatting
from app.services import field_labels as field_labels_service
from app.services import instruments as instruments_service
from app.services import lifecycle_display, session_lifecycle as lifecycle
from app.web.date_filters import (
    display_timezone_context_processor,
    format_date_filter,
    format_datetime_filter,
)


# ------------------------------------------------------------------ #
# Template factory + Jinja globals — single source of truth.
#
# ``__file__`` here is ``app/web/routes_operator/_shared.py``; the
# templates live one level up at ``app/web/templates``, hence
# ``.parent.parent``. The pre-package file resolved with a single
# ``.parent``; the extra hop is the most likely regression point in
# the package conversion, so the PR 0 smoke test pins it down by
# rendering ``GET /operator/sessions``.
# ------------------------------------------------------------------ #
_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "templates"),
    context_processors=[display_timezone_context_processor],
)
_templates.env.globals["app_version"] = settings.app_version
_templates.env.globals["display_field_label"] = (
    instruments_service.display_field_label
)
_templates.env.globals["is_locked_display_source"] = (
    instruments_service.is_locked_display_source
)
# Friendly-label resolver globals — Segment 15A Slice 2.
# ``field_label`` returns just the resolved string (friendly →
# canonical default → fallback). ``field_label_pair`` returns the
# ``LabelPair(friendly, canonical, has_override)`` used by the
# two-line operator-surface header render.
_templates.env.globals["field_label"] = field_labels_service.resolve
_templates.env.globals["field_label_pair"] = field_labels_service.resolve_pair
_templates.env.filters["lifecycle_label"] = (
    lifecycle_display.lifecycle_display_label
)
# Canonical date / time display formatting — Segment 18B PR 1 / PR 2.
# Context-aware: the filters resolve their display zone from the
# ``display_timezone`` context key the processor above injects.
_templates.env.filters["format_datetime"] = format_datetime_filter
_templates.env.filters["format_date"] = format_date_filter
# Mirrors the date_formatting.SHOW_ZONE_TOKEN switch into templates
# so the two timezone-card live previews match the server render.
_templates.env.globals["show_zone_token"] = date_formatting.SHOW_ZONE_TOKEN


# ------------------------------------------------------------------ #
# Lifecycle / edit-lock guards (cross-slice).
# ------------------------------------------------------------------ #

# Operations-row pages whose forms can override the default
# "redirect back to Session Home" behaviour after a workflow-card
# action (Activate / Revert / Create invites / Send invites / Send
# reminders). Form posts include a hidden ``return_to`` field carrying
# one of these slugs; the route honours the override only when it
# matches.
_REVERT_RETURN_TO = {
    "reviewers",
    "reviewees",
    "assignments",
    "instruments",
    "validate",
    "previews",
    "invitations",
    "responses",
}


def _require_editable(review_session: ReviewSession) -> None:
    """Reject mutating operator actions while session is not draft/validated."""
    if not lifecycle.is_editable(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to draft to edit"
            ),
        )


def _require_response_loss_ack(
    db: Session, review_session: ReviewSession, ack: str | None
) -> None:
    """When responses exist, require explicit acknowledge_response_loss=true."""
    if not lifecycle.session_has_responses(db, review_session):
        return
    if ack != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Existing reviewer responses will be discarded; tick "
                "'acknowledge response loss' to proceed"
            ),
        )


def _lifecycle_error_response(exc: lifecycle.LifecycleError) -> HTTPException:
    code_to_status = {
        "not_draft": status.HTTP_409_CONFLICT,
        "not_ready": status.HTTP_409_CONFLICT,
        "session_not_ready": status.HTTP_409_CONFLICT,
        "deadline_passed": status.HTTP_409_CONFLICT,
        "locked": status.HTTP_409_CONFLICT,
        "has_errors": status.HTTP_400_BAD_REQUEST,
        "needs_acknowledge": status.HTTP_400_BAD_REQUEST,
        "needs_confirm": status.HTTP_400_BAD_REQUEST,
    }
    return HTTPException(
        status_code=code_to_status.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=str(exc),
    )


# ------------------------------------------------------------------ #
# Quick Setup cookie naming.
#
# The companion regex ``_QUICK_SETUP_COOKIE_RE`` lives in
# ``app/main.py`` and drives the navigation middleware that expires
# the unlock cookie when the operator leaves Session Home. If you
# rename the prefix here, update the regex literal there too — both
# files cross-reference each other in comments.
# ------------------------------------------------------------------ #
_QUICK_SETUP_COOKIE_PREFIX = "qsu"


def _quick_setup_cookie_name(session_id: int) -> str:
    return f"{_QUICK_SETUP_COOKIE_PREFIX}_{session_id}"


def _quick_setup_unlocked(
    request: Request, review_session: ReviewSession
) -> bool:
    """``True`` when the operator's last lock-toggle action was Unlock.

    Read from the per-session cookie set by
    ``POST /sessions/{id}/quick-setup/lock``. Absent ⇒ default locked.
    """
    return (
        request.cookies.get(_quick_setup_cookie_name(review_session.id)) == "1"
    )
