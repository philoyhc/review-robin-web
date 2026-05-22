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
from urllib.parse import urlencode

from fastapi import HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession, User
from app.services import assignments, csv_imports, date_formatting
from app.services import field_labels as field_labels_service
from app.services import instruments as instruments_service
from app.services import lifecycle_display, session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.web import breadcrumbs, views
from app.web.date_filters import (
    display_timezone_context_processor,
    format_date_filter,
    format_datetime_filter,
)
from app.web.deps import request_correlation_id


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
# Segment 13C — the set of (source_type, source_field) tag pairs a
# group-scoped instrument groups by; drives the group Display
# Fields table's Group-by / Include columns.
_templates.env.globals["group_boundary_pairs"] = (
    instruments_service.group_boundary_pairs
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
# Resolves a session's effective display zone (the raw IANA id) —
# used by the sessions-lobby Timezone column, where the table lists
# many sessions and so can't pick one zone for its timestamp cells.
_templates.env.globals["session_timezone"] = (
    sessions_service.resolve_session_timezone
)
# Compact GMT-offset label for the sessions-lobby Timezone column —
# narrower than the raw IANA id (e.g. ``GMT+8`` for ``Asia/Singapore``).
_templates.env.globals["gmt_offset_label"] = date_formatting.gmt_offset_label
# Combined form for the timezone picker datalist + initial value:
# ``"GMT+8 Asia/Singapore"`` (or ``"UTC"`` for the zero-offset case).
_templates.env.globals["gmt_offset_zone_label"] = (
    date_formatting.gmt_offset_zone_label
)
# datetime-local input value (wall-clock in a session's zone) — used
# by the sessions-lobby inline expander's Deadline edit box.
_templates.env.globals["format_datetime_local"] = (
    date_formatting.format_datetime_local
)


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
        "group_instrument_no_rule": status.HTTP_409_CONFLICT,
        "locked": status.HTTP_409_CONFLICT,
        "has_errors": status.HTTP_400_BAD_REQUEST,
        "needs_acknowledge": status.HTTP_400_BAD_REQUEST,
        "needs_confirm": status.HTTP_400_BAD_REQUEST,
    }
    return HTTPException(
        status_code=code_to_status.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=str(exc),
    )


def _can_edit_instrument(review_session: ReviewSession) -> bool:
    """Setup-side instrument / RTD mutations are blocked while the
    session is ready."""
    return not lifecycle.is_ready(review_session)


def _require_instrument_editable(review_session: ReviewSession) -> None:
    """Guard shared by the Instruments and Response-Type slices —
    reject structure mutations on a ready session."""
    if not _can_edit_instrument(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Instrument structure is locked while the session is ready"
            ),
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


# ------------------------------------------------------------------ #
# Setup-roster plumbing (cross-slice).
#
# Shared by the Reviewers / Reviewees / Relationships Setup-page
# slices (``_setup_reviewers.py`` / ``_setup_reviewees.py`` /
# ``_setup_relationships.py``). ``_handle_import`` backs only the
# Reviewers + Reviewees CSV imports; ``_redirect_keeping_selection``
# and ``_save_field_labels`` back all three.
# ------------------------------------------------------------------ #

# Row caps for the Reviewers / Reviewees / Relationships Setup tables:
# 200 unfiltered, 500 when a search / status filter is applied
# (Segment 15F PR 2). Applied after sort so the visible window
# matches the operator's chosen order.
_SETUP_DEFAULT_CAP: int = 200
_SETUP_FILTERED_CAP: int = 500


def _redirect_keeping_selection(
    base_url: str,
    selected_ids: list[int],
    *,
    filter_params: list[tuple[str, str]] | None = None,
) -> RedirectResponse:
    """303 back to a Setup page, carrying the acted-on row ids as
    ``?selected=`` params. The page re-checks those checkboxes so
    the operator clears the selection themselves rather than the
    action silently clearing it (Segment 15F).

    ``filter_params`` carries the active search / status filter
    (empty values dropped) through the action so the operator
    lands back on the same filtered view."""
    params: list[tuple[str, object]] = []
    if filter_params:
        params.extend((key, value) for key, value in filter_params if value)
    params.extend(("selected", i) for i in selected_ids)
    url = base_url if not params else base_url + "?" + urlencode(params)
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


async def _handle_import(
    *,
    request: Request,
    file: UploadFile,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> HTMLResponse | RedirectResponse:
    """Shared Reviewers / Reviewees CSV-import handler.

    ``kind`` is ``"reviewers"`` or ``"reviewees"``; the *_fn callables
    are the matching ``csv_imports`` entry points. On a parse / confirm
    / ack failure it re-renders the Setup page with the issues; on
    success it saves and 303s back to the page."""
    _require_editable(review_session)
    content = await file.read()
    result = parse_fn(content)
    if not result.is_blocked:
        result.issues.extend(
            csv_imports.check_cross_table_identity(
                db,
                session_id=review_session.id,
                rows=result.rows,
                kind=kind,
            )
        )
    existing = existing_count_fn(db, review_session.id)
    assignment_count = csv_imports.existing_assignment_count(db, review_session.id)

    if kind == "reviewers":
        template = "operator/session_reviewers.html"
        crumb_label = "Reviewers"
        list_key = "reviewers"
        list_items = assignments.list_reviewers(db, review_session.id)
    else:
        template = "operator/session_reviewees.html"
        crumb_label = "Reviewees"
        list_key = "reviewees"
        list_items = assignments.list_reviewees(db, review_session.id)

    def render(status_code: int = status.HTTP_200_OK) -> HTMLResponse:
        context: dict[str, object] = {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            list_key: list_items,
            "existing_count": existing,
            "assignment_count": assignment_count,
            "issues": result.issues,
            "filename": file.filename,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, crumb_label
            ),
        }
        if kind in ("reviewers", "reviewees"):
            # Segment 15F — the Reviewers / Reviewees templates'
            # right-side operator-actions card needs the filter / cap
            # context even on the CSV-import error-render path so the
            # form keeps reading consistent. The error render is
            # never an edit state.
            if kind == "reviewers":
                status_options = views.REVIEWERS_STATUS_OPTIONS
                search_options = views.reviewers_search_options(list_items)
                raw_fields = assignments.reviewer_fields_with_data(
                    db, review_session.id
                )
            else:
                status_options = views.REVIEWEES_STATUS_OPTIONS
                search_options = views.reviewees_search_options(list_items)
                raw_fields = assignments.reviewee_fields_with_data(
                    db, review_session.id
                )
            fields_with_data = views.friendly_fields_with_data(
                review_session, raw_fields
            )
            context.update(
                {
                    "total_row_count": len(list_items),
                    "displayed_row_count": len(list_items),
                    "filter_status": "all",
                    "filter_search": "",
                    "filter_status_options": status_options,
                    "filter_search_options": search_options,
                    "is_ready": lifecycle.is_ready(review_session),
                    "fields_with_data": fields_with_data,
                    "edit_id": None,
                    "add_mode": False,
                    "edit_values": None,
                    "edit_error": None,
                    "selected_ids": set(),
                }
            )
        return _templates.TemplateResponse(
            request, template, context, status_code=status_code
        )

    if result.is_blocked:
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and confirm_replace != "true":
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)

    save_fn(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/{kind}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _save_field_labels(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    source_type: str,
    slots: tuple[tuple[str, str], ...],
    submitted: dict[str, str],
    correlation_id: str | None,
) -> None:
    """Upsert / clear per submitted slot (Segment 15A Slice 3).

    Rejected with 409 when ``is_ready`` — labels are locked
    alongside the rest of the page's data on a live session;
    operators revert to draft to rename.
    """
    if lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to "
                "draft to rename labels."
            ),
        )
    for form_param, source_field in slots:
        value = (submitted.get(form_param) or "").strip()
        if value:
            field_labels_service.upsert(
                db,
                review_session,
                source_type=source_type,
                source_field=source_field,
                label=value,
                user=user,
                correlation_id=correlation_id,
            )
        else:
            field_labels_service.clear(
                db,
                review_session,
                source_type=source_type,
                source_field=source_field,
                user=user,
                correlation_id=correlation_id,
            )
