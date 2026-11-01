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

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from cordware.graph import Directory, GraphError, directory_for

from app.config import settings
from app.db.models import (
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import assignments, csv_imports, date_formatting, directory_accounts
from app.services import field_labels as field_labels_service
from app.services.users import is_verified as users_service_is_verified
from app.services import instruments as instruments_service
from app.services import (
    held_uploads,
    lifecycle_display,
    operator_settings,
    roster_bulk,
    scheduled_events,
)
from app.services import session_lifecycle as lifecycle
from app.services import session_owners, session_tags
from app.services import sessions as sessions_service
from app.services import unit_of_work
from app.services.responses import GroupAnswersWouldClear
from app.web import breadcrumbs, views
from app.web.date_filters import (
    display_timezone_context_processor,
    format_date_filter,
    format_datetime_filter,
)
from app.web.deps import request_correlation_id, require_session_operator
from app.web import urls


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
urls.install(_templates)
_templates.env.globals["app_version"] = settings.app_version
# 19Z, accounts item: a ``users`` row bound to its person in the directory.
_templates.env.globals["account_verified"] = users_service_is_verified
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
# A stored instant as the session tables' client sort key, so a header
# click orders Deadline / Created / Archived as a reload does.
_templates.env.filters["sort_instant"] = views.instant_sort_value
# A status's lifecycle position, the session tables' Status sort key.
_templates.env.filters["sort_status"] = views.status_sort_cell
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
# ``YYYY-MM-DDTHH:MM`` wall-clock in a session's zone — Session Home's
# ``data-tz-utc`` seeds, which the zone-conversion script reads.
_templates.env.globals["format_datetime_local"] = (
    date_formatting.format_datetime_local
)
# A date-time field's 24-hour text (19X Item 6) — the sessions-lobby
# inline expander's Deadline box seeds from it.
_templates.env.globals["format_datetime_box"] = date_formatting.format_datetime_box
# Per-numeric-column ``ch`` width for the fixed-layout group-scoped
# instrument table (Segment 13C). Registered on the reviewer
# ``_templates`` as well; the operator preview route
# (``_preview_surface.py``) renders ``reviewer/review_surface.html``
# through this operator instance, and the template references this
# helper inside the group-scoped branch — so without this global,
# previewing a session whose page-2+ holds a group-scoped instrument
# 500s on render.
_templates.env.globals["numeric_column_ch_width"] = (
    views.numeric_column_ch_width
)
_templates.env.globals["profile_column_ch_width"] = (
    views.profile_column_ch_width
)
_templates.env.globals["is_web_link"] = views.is_web_link
# Reviewer-progress pill: one state → (css, label) mapping (audit V2).
_templates.env.globals["progress_pill"] = views.progress_pill
# Operator-facing instrument label resolver
# (``short_label > Instrument_{session_seq}`` per the 2026-05-28 operator-
# identifier policy in ``spec/instruments.md``). Registered as a
# Jinja global so operator templates can call ``instrument_label(...)``
# inline without the view shape having to pre-compute every cell.
_templates.env.globals["instrument_label"] = (
    instruments_service._instrument_label
)


# ------------------------------------------------------------------ #
# Lifecycle / edit-lock guards (cross-slice).
# ------------------------------------------------------------------ #

# Operations-row pages whose forms can override the default
# "redirect back to Session Home" behaviour after a workflow-card
# action (Activate / Revert / Send invites / Send reminders; Create
# invites retired at 19Q Item 2 rung 3). Form posts include a hidden
# ``return_to`` field carrying
# one of these slugs; the route honours the override only when it
# matches.
#
# Segment 19H Item 6 rung 1 — ``relationships`` and ``observers``
# were missing while both templates posted them, so reverting from
# either lock card fell through to Session Home: the operator asked
# to revert *so they could edit relationships* and landed somewhere
# else. Silent, because a 303 to a real page looks like success.
# Measured before the fix:
#     revert-to reviewers      -> /operator/sessions/1/reviewers
#     revert-to relationships  -> /operator/sessions/1
_REVERT_RETURN_TO = {
    "reviewers",
    "reviewees",
    "relationships",
    "observers",
    "assignments",
    "instruments",
    "validate",
    "invitations",
    "responses",
    "extract-data",
}


# 20B rung 1 — the symmetric-review scaffold. ``?symmetric_preview=``
# ``plain`` or ``marked`` renders the mode-on states (the greyed
# Reviewees slot, the read-only Reviewees page, and the Reviewees tab
# unmarked or marked) so the author can judge them before the setting
# exists. Inert: nothing reads or writes a setting. Rung 2 replaces it
# with ``session.symmetric_review`` and deletes this.
SYMMETRIC_PREVIEW_VALUES = ("plain", "marked")


def symmetric_preview(raw: str | None) -> str | None:
    """The scaffold's preview variant, or ``None`` for anything else."""
    return raw if raw in SYMMETRIC_PREVIEW_VALUES else None


def acknowledged_loss(raw: object) -> int:
    """The count a ``Yes, clear them`` tick was shown on a Save refused
    for clearing group answers (``acknowledge_response_loss``), or 0
    with no tick. The tick carries the count rather than ``true`` so a
    tick left on after further edits cannot approve a different clear
    (``responses.clear_changed_groups``)."""
    text = str(raw or "").strip()
    # ``isdecimal``, not ``isdigit``: ``"²"`` is a digit ``int`` refuses.
    return int(text) if text.isdecimal() else 0


@dataclass(frozen=True)
class UploadIn:
    """The file a Setup upload card sent: the one chosen, or, with
    none chosen, the one its last ask held (segment 19W). ``token`` is
    the hold in play, if any; ``lost`` says a hold was named but had
    expired or was not this operator's and session's."""

    content: bytes
    filename: str | None
    token: str | None
    lost: bool = False


async def read_upload(
    db: Session,
    *,
    file: UploadFile | None,
    held_token: str | None,
    user: User,
    review_session: ReviewSession,
    slot: str,
) -> UploadIn:
    """Read a Setup upload card's file, falling back to the held one.

    A newly chosen file wins over the hold, even an empty one: a file
    is chosen when it has a filename, as Quick Setup's ``_attached``
    reads it, since an untouched input posts an empty-named part. An
    empty chosen file is then refused as a fresh empty upload is
    (findings S2). The held
    bytes are parsed again by the caller, exactly as a fresh upload's
    would be."""
    token = (held_token or "").strip() or None
    content = await file.read() if file is not None else b""
    chosen = file is not None and bool(file.filename)
    if content or chosen or token is None:
        return UploadIn(
            content=content,
            filename=file.filename if file is not None else None,
            token=token,
        )
    held = held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ).get(slot)
    if held is None:
        return UploadIn(content=b"", filename=None, token=None, lost=True)
    return UploadIn(content=held.content, filename=held.filename, token=token)


def hold_for_ask(
    db: Session,
    *,
    upload: UploadIn,
    user: User,
    review_session: ReviewSession,
    slot: str,
) -> dict[str, str] | None:
    """Hold the file of an upload refused with a question, so the
    operator answers it without choosing the file again (segment 19W).
    Commits the hold: the refusal re-renders at 400 without one. Returns
    the template's ``held_upload`` (token and filename), or ``None`` when
    nothing could be held (an empty file, or one over the cap)."""
    token = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={
            slot: held_uploads.HeldFile(
                filename=upload.filename or "upload.csv",
                content=upload.content,
            )
        },
        token=upload.token,
    )
    db.commit()
    if token is None:
        return None
    # Name what the hold holds, not what was sent: a file it skipped (an
    # empty or oversized one) is not held, and must not read as held.
    held = held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ).get(slot)
    if held is None:
        return None
    return {"token": token, "filename": held.filename}


def release_hold(
    db: Session,
    *,
    token: str | None,
    user: User,
    review_session: ReviewSession,
) -> None:
    """End a hold once its upload is done with: saved, refused for good,
    or dismissed. A token that is not this operator's and this session's
    deletes nothing."""
    token = (token or "").strip()
    if not token:
        return
    if held_uploads.discard(
        db, token=token, user=user, session_id=review_session.id
    ):
        db.commit()


def observe_scheduled_events_on_load(
    request: Request,
    db: Session,
    review_sessions: Iterable[ReviewSession],
) -> None:
    """Run the lazy scheduled-event pass (``spec/lifecycle.md`` §8.3)
    for each session an operator GET shows, before the page reads it.

    The callers are Session Home, the four Operations pages (Validate,
    Assignments, Invitations, Responses) and the Sessions lobby, which
    passes every session it lists. The pass is
    ``scheduled_events.observe_scheduled_events``; a session with
    nothing due returns before any query. Each session runs at most
    once per request, tracked on ``request.state``. ``build_invite_url``
    closes over the request so the invite and reminder sends can build
    absolute URLs.
    """
    done: set[int] = getattr(request.state, "scheduled_events_observed", set())
    request.state.scheduled_events_observed = done
    correlation_id = request_correlation_id()

    def build_invite_url(token: str) -> str:
        return str(request.url_for("reviewer_invite", token=token))

    for review_session in review_sessions:
        if review_session.id in done:
            continue
        done.add(review_session.id)
        scheduled_events.observe_scheduled_events(
            db,
            review_session,
            correlation_id=correlation_id,
            build_invite_url=build_invite_url,
        )


def _require_editable(review_session: ReviewSession) -> None:
    """Reject mutating operator actions while session is not draft/validated."""
    if not lifecycle.is_editable(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to draft to edit"
            ),
        )


def _require_not_archived(review_session: ReviewSession) -> None:
    """Reject mutating operator actions only when archived.

    Used by every Observers route — the roster's upload, add, edit,
    status, delete and cohort-rule writes. Observers govern which parts
    of response data become visible rather than the response data or
    the review's roster shape, so editing them mid-session (ready /
    expired) is the legitimate flow; only the archived hard-stop is
    enforced.
    """
    if lifecycle.is_archived(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is archived; observer edits are not allowed.",
        )


def _require_not_ready(review_session: ReviewSession) -> None:
    """Reject Session Home's Delete Data and Delete session while ``ready``.

    The author's ruling of 2026-10-02 (C7 = G7): both are allowed in
    ``draft``, ``validated``, ``expired`` and ``archived`` — a finished
    session is the natural time to clean up — and refused only while
    the session is Activated, where Session Home also greys them out.
    """
    if lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is ready; revert to draft first to delete.",
        )


def require_relationships_enabled_session(
    review_session: ReviewSession = Depends(require_session_operator),
) -> ReviewSession:
    """Route gate for the per-session ``relationships_enabled``
    toggle (``guide/archive/participant_model_upgrade.md`` §3.8).

    Returns 404 when the feature is off so deep links to a tab
    the operator hasn't enabled cleanly miss rather than render
    an orphan page. Wraps ``require_session_operator`` so the
    permission check still runs first.
    """
    if not review_session.relationships_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return review_session


def require_observers_enabled_session(
    review_session: ReviewSession = Depends(require_session_operator),
) -> ReviewSession:
    """Route gate for the per-session ``observers_enabled``
    toggle — symmetric to ``require_relationships_enabled_session``.
    """
    if not review_session.observers_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return review_session


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


def _require_delete_confirm(confirm: str | None) -> None:
    """The server half of the strip's confirmation checkbox.

    The client gate (a selection enables the box, the box enables the
    button) is a convenience; this is the check that counts, and it is
    the same ``confirm != "true"`` refusal the Danger Zone's
    ``delete-all`` uses (Segment 19I Item 2).
    """
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )


def _require_selected_response_loss_ack(
    db: Session, *, model: type, ids: list[int], ack: str | None
) -> int:
    """``_require_response_loss_ack`` narrowed to the rows going.

    That function asks whether the *session* has responses, which is
    the only question ``delete-all`` can ask. A selected delete knows
    which rows it is taking, so it asks whether **those** rows carry
    responses and can name the number — the same gate with a true
    sentence instead of a categorical one. Returns the count, which is
    zero (and the gate a no-op) for Observers and Relationships, since
    nothing references them.
    """
    _assignments, responses = roster_bulk.cascade_counts(
        db, model=model, ids=ids
    )
    if responses and ack != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Deleting the selected rows will discard {responses} saved "
                f"response{'' if responses == 1 else 's'}; tick "
                "'acknowledge response loss' to proceed"
            ),
        )
    return responses


def _lifecycle_error_response(exc: lifecycle.LifecycleError) -> HTTPException:
    if isinstance(exc, lifecycle.SessionStateConflict):
        # A state gate re-read under the lock (findings Bc4) — the 409
        # every route-level gate answers with, whatever its code.
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
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


def session_payload_error(exc: ValidationError) -> HTTPException:
    """A session payload's field errors (a Name over 255 characters, say)
    as the 422 every session form answers with, rather than a 500
    (findings C4). The lobby expander, Session Home's Details Save and
    Create share it."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="; ".join(
            f"{'.'.join(map(str, error['loc'])) or 'session'}: {error['msg']}"
            for error in exc.errors()
        ),
    )


def parse_session_deadline(
    deadline: str | None, timezone_name: str
) -> datetime | None:
    """Parse an operator-entered wall-clock deadline in the session's
    display timezone, or ``None`` when blank. Raises
    ``HTTPException(422)`` on a malformed value.

    Shared by the two surfaces that edit a session's deadline — the
    Sessions-lobby expander Save (``_lobby.py``) and the Session Home
    config-card write (``_session_home._apply_session_config_form``) —
    so the parse + error contract lives in one place (audit R8). The
    two routes' *gate* semantics deliberately differ (the lobby
    expander silently ignores name/code/deadline when the session is
    not editable; the config card hard-requires an editable session),
    so only the parse is shared, not the gate.
    """
    if not deadline:
        return None
    try:
        return date_formatting.parse_local_datetime(deadline, timezone_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="deadline must be ISO-8601",
        ) from exc


def _redirect_url(
    session_id: str,
    return_to: str | None,
    *,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: bool = False,
) -> str:
    """Resolve the post-action redirect target for the workflow +
    lifecycle actions. ``return_to`` honours the revert allowlist;
    anything else falls through to Session Home. Failure diagnostics
    ride along as ``super_*`` query params (rendered as the Session
    Home flash banner), and the reconcile detour bounces with
    ``prepare_confirm=responses``. ``super_button`` names the button
    that failed so the workflow card's failure banner can headline
    it: one of ``"prepare"``, ``"activate"``, ``"close"``,
    ``"release_responses"`` or ``"stop_release"``. The map from
    those to operator-facing labels lives in
    ``partials/next_action_card.html``; an unrecognised value
    headlines the generic "Action failed" rather than a named
    button. ``super_error`` is a code, never a sentence: the card maps
    it to fixed copy and shows nothing for an unlisted one (findings
    O7).

    Lives here (not in ``_workflow.py``) so the Session-Home
    ``/activate`` handler and the Workflow-card ``/workflow/activate``
    handler build the **same** failure flash — audit R2.
    """
    if return_to in _REVERT_RETURN_TO:
        base = f"/operator/sessions/{session_id}/{return_to}"
    else:
        base = f"/operator/sessions/{session_id}"
    if prepare_confirm:
        return f"{base}?{urlencode({'prepare_confirm': 'responses'})}"
    if super_status is None:
        return base
    params = {"super_status": super_status}
    if super_button:
        params["super_button"] = super_button
    if super_step:
        params["super_step"] = super_step
    if super_error:
        params["super_error"] = super_error
    return f"{base}?{urlencode(params)}"


async def require_json_object(request: Request, *, label: str) -> dict:
    """Parse an AJAX request body as a JSON object, else raise
    ``HTTPException(400)`` with a ``"{label} body must be …"`` message.

    Shared by the instrument-card AJAX endpoints (`_instruments*.py`),
    which each hand-rolled this same parse-and-check (audit R4). It
    deliberately keeps the hand-rolled 400 + tailored-message contract
    the client JS expects, rather than a Pydantic 422 — the
    extract-data sub-API remains the blessed Pydantic pattern for *new*
    endpoints (see ``spec/architecture.md`` § "Route conventions").
    """
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} body must be a JSON object",
        )
    return body


def _can_edit_instrument(review_session: ReviewSession) -> bool:
    """Setup-side instrument / RTD mutations follow the same
    lifecycle rule as every other setup surface: ``draft`` or
    ``validated``.

    Segment 19I Item 6. This was ``not is_ready``, which protected
    the instrument surface exactly while the session was *collecting*
    and stopped protecting it the moment collection **ended** — so on
    ``expired`` and ``archived`` a delete succeeded and took the
    instrument's assignments and their submitted responses with it
    (``Instrument`` cascades both, ``delete-orphan``). Those are the
    states where the data has become the record.

    Changing the predicate here rather than at the ~24
    ``_require_instrument_editable`` call sites is deliberate: the
    call sites already ask "is this editable"; the helper answered
    the wrong question.
    """
    return lifecycle.is_editable(review_session)


def _require_instrument_editable(review_session: ReviewSession) -> None:
    """Guard shared by the Instruments and Response-Type slices —
    reject structure mutations on a session that is not editable."""
    if not _can_edit_instrument(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Instrument structure is locked while the session is "
                f"{review_session.status}"
            ),
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


@dataclass(frozen=True)
class SetupWindow:
    """The slice of a roster one Setup page renders, plus what the
    page needs to say about it (Segment 19J.5 rung 2).

    ``edit_id`` comes back because resolving it can clear it: an id
    naming a row that no longer exists drops edit mode rather than
    rendering an editor over nothing.
    """

    rows: list
    offset: int
    pager: views.Pager | None
    edit_id: int | None


def _setup_row_window(
    *,
    filtered: list,
    all_rows: list,
    is_filtered: bool,
    offset: int = 0,
    edit_id: int | None = None,
    locate_id: int | None = None,
) -> SetupWindow:
    """Cut the page the operator asked for out of a sorted, filtered
    roster — shared by the four Setup roster slices.

    **Unfiltered is paged**: 200 rows a page, ``offset`` clamped onto a
    real boundary so a stale link lands on the last page rather than a
    404, and a pager describing the whole roster.

    **Filtered is not.** The operator's own partition of the roster
    wins and a second one stacked on it is two mental models for one
    table, so a filtered view keeps the 500 cap it has always had and
    gets no pager — the count line speaks for it instead.

    **The edit target is always on screen.** Before 19J.5 a row being
    edited from outside the cap was prepended to the table, because
    there was nowhere else to put it. On a paged view there now is:
    the operator lands on the page that actually holds the row, which
    also leaves the pager honest about where they are. The prepend
    survives for the two cases that still need it — a filtered view,
    and a row the filter itself excludes.
    """
    if is_filtered:
        rows = filtered[:_SETUP_FILTERED_CAP]
        offset = 0
        pager = None
    else:
        offset = views.clamp_offset(
            offset, total=len(filtered), page_size=_SETUP_DEFAULT_CAP
        )
        rows = filtered[offset : offset + _SETUP_DEFAULT_CAP]
        pager = views.build_pager(
            total=len(filtered), offset=offset, page_size=_SETUP_DEFAULT_CAP
        )

    # A row to land on that is not being edited: a create appends past
    # the end of an unfiltered roster, so on anything over one page the
    # new row is not in this window and the redirect's `#<noun>-row-<id>`
    # would name a row the response does not render (19P.1). Same page
    # arithmetic as the edit relocation below, deliberately narrower: it
    # only moves the unfiltered window, and never prepends a row a
    # filter excludes.
    if (
        edit_id is None
        and locate_id is not None
        and not is_filtered
        and locate_id not in {r.id for r in rows}
    ):
        index = next(
            (i for i, r in enumerate(filtered) if r.id == locate_id), None
        )
        if index is not None:
            offset = (index // _SETUP_DEFAULT_CAP) * _SETUP_DEFAULT_CAP
            rows = filtered[offset : offset + _SETUP_DEFAULT_CAP]
            pager = views.build_pager(
                total=len(filtered),
                offset=offset,
                page_size=_SETUP_DEFAULT_CAP,
            )

    if edit_id is None or edit_id in {r.id for r in rows}:
        return SetupWindow(rows=rows, offset=offset, pager=pager, edit_id=edit_id)

    # The edited row is off the current window. Resolve it against the
    # *unfiltered* roster: an operator editing a row the filter hides
    # is still editing a real row.
    edited = next((r for r in all_rows if r.id == edit_id), None)
    if edited is None:
        return SetupWindow(rows=rows, offset=offset, pager=pager, edit_id=None)

    if not is_filtered:
        index = next(
            (i for i, r in enumerate(filtered) if r.id == edit_id), None
        )
        if index is not None:
            offset = (index // _SETUP_DEFAULT_CAP) * _SETUP_DEFAULT_CAP
            rows = filtered[offset : offset + _SETUP_DEFAULT_CAP]
            pager = views.build_pager(
                total=len(filtered),
                offset=offset,
                page_size=_SETUP_DEFAULT_CAP,
            )
            return SetupWindow(
                rows=rows, offset=offset, pager=pager, edit_id=edit_id
            )

    return SetupWindow(
        rows=[edited, *rows], offset=offset, pager=pager, edit_id=edit_id
    )


def _redirect_keeping_selection(
    request: Request, base_url: str,
    selected_ids: list[int],
    *,
    filter_params: list[tuple[str, str]] | None = None,
    offset: int = 0,
    anchor: str | None = None,
    extra_params: list[tuple[str, object]] | None = None,
) -> RedirectResponse:
    """303 back to a Setup page, carrying the acted-on row ids as
    ``?selected=`` params. The page re-checks those checkboxes so
    the operator clears the selection themselves rather than the
    action silently clearing it (Segment 15F).

    ``filter_params`` carries the active search / status filter
    (empty values dropped) through the action so the operator
    lands back on the same filtered view.

    ``offset`` carries the pager position. Without it a row action on
    page 2 answered with page 1 — the acted-on row was not even in the
    response, so the operator lost their place entirely and no anchor
    could have found the row (19P.1).

    ``extra_params`` carries anything that is not a filter — today only
    ``focus``, which tells the next render to page to a row the caller
    just created rather than answering with page 1 and an anchor naming
    a row that is not there.

    ``anchor`` is the fragment to land on, normally the first acted-on
    row. A bare 303 lands at the top of the document: measured at 821px
    of jump from a mid-table action. Callers that have no row to land on
    (a delete removes them) pass the table card instead. A fragment that
    does not resolve is silently ignored by the browser and lands at the
    top again, so a caller passing ``anchor`` must also ship the
    fallback script that catches a missing target. **All four roster
    pages** do since 19P.3 rung 1 — Reviewers at 19P.1, Observers at
    19P.2, Reviewees and Relationships together at 19P.3. Two of the
    four ship a two-case fallback rather than one: Reviewees,
    Relationships and Reviewers are sortable, so a row can move off the
    restored page under a cookie-held sort as well as drop out of a
    filtered view; Observers is not."""
    params: list[tuple[str, object]] = []
    if filter_params:
        params.extend((key, value) for key, value in filter_params if value)
    if extra_params:
        params.extend(extra_params)
    if offset:
        params.append(("offset", offset))
    params.extend(("selected", i) for i in selected_ids)
    url = base_url if not params else base_url + "?" + urlencode(params)
    if anchor:
        url += "#" + anchor
    return urls.redirect(request, url=url, status_code=status.HTTP_303_SEE_OTHER)


def _row_action_anchor(row_ids: list[int], *, noun: str) -> str:
    """Where a row action lands: the first row it acted on.

    ``noun`` is the singular entity name — ``"reviewer"`` yields
    ``reviewer-row-<id>``, falling back to ``reviewers-table-card``. The
    bare ``+ "s"`` plural holds for all four rosters (reviewer, reviewee,
    observer, relationship) and the table-card ids they already ship.

    A bare 303 lands at the top of the document — measured at 821px of
    jump from a mid-table action (19P.1). Anchoring the table card
    instead only helps when the row is near its top, which is the Add
    case and not the common one.

    With no row to land on, the table card. ``bulk-delete`` passes ``[]``
    by design, since the rows it acted on no longer exist.

    **Two** cases leave the fragment unresolvable, and neither is decided
    here: a row that survives but drops out of a filtered view
    (``Inactivate`` under ``status=active``), and a row that moves to
    another page under the operator's cookie sort — the bulk status
    routes write ``updated_at`` as well as ``status``, so a sort on
    either reorders the row out from under a held ``offset``. Both would
    need the filter and the sort re-run to predict, which is a multi-row
    computation and belongs outside a route handler; the page's fallback
    script catches them instead.

    The delete case is **not** one of them, though this docstring said
    "all three" until 19P.2 rung 1. The fallback script opens with
    ``hash.indexOf("#<noun>-row-") !== 0 -> return``, and a delete
    redirects to the table card, so the script returns on its first line
    and never sees it. The route handles that case; the script handles
    the other two.

    **Two is the generic count, not every page's.** A page whose table
    is not sortable has one — Observers, whose ``<table>`` carries no
    ``data-rrw-sortable``. Each page's own script comment states its
    own; this states the ceiling.

    The same miscount reached `spec/setup_pages.md` and was corrected
    there by 19P.1 rung 4a's cold read. **Two copies survive**, both
    outside this rung's reach: `spec/ui_elements.md` § *Landing
    targets* still reads "three cases", and is on Item 2's `Doc impact`
    for rung 7; `session_reviewers.html`'s own script comment is
    corrected alongside this one.
    """
    if row_ids:
        return f"{noun}-row-{row_ids[0]}"
    return f"{noun}s-table-card"


def _require_reviewer_in_session(
    db: Session, review_session: ReviewSession, reviewer_id: int
) -> Reviewer:
    """Resolve a reviewer by id scoped to the operator's session, or
    404. **Lifted here from ``_setup_reviewers.py`` at 19P.6 rung 1**,
    when the Invitations drill-in was re-keyed from the invitation to
    the reviewer and needed the same lookup: a slice may import from
    ``_shared.py`` and from outside the package, never from a sibling
    slice (``CLAUDE.md``; ``docs/unenforced_conventions.md`` §2.2).

    A plain helper, not a dependency, unlike
    ``_require_instrument_in_session`` below — both call sites already
    hold the session and the id, and converting them would be a change
    to the reviewers slice that this rung has no reason to make."""
    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.id == reviewer_id,
            Reviewer.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if reviewer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return reviewer


def _require_instrument_in_session(
    instrument_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    db: Session = Depends(get_db),
) -> tuple[Instrument, ReviewSession]:
    """Resolve an instrument by id scoped to the operator's session,
    or 404. Lifted to ``_shared.py`` in Segment 18N PR 3 so the
    Instruments-page slices (``_instruments.py``,
    ``_instruments_band2.py``, ``_instruments_pagination.py``) can
    all share the same dependency; ``_assignments.py``'s self-review
    toggle uses it too."""
    instrument = db.execute(
        select(Instrument).where(
            Instrument.id == instrument_id,
            Instrument.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return instrument, review_session


def _instruments_redirect(
    request: Request, session_id: str, fragment: str | None = None
) -> RedirectResponse:
    """Redirect to the Instruments index, optionally landing on an
    in-page anchor.

    Per-instrument actions (visibility / save / page break) should
    pass ``fragment="instrument-{id}"`` so the
    operator lands on the instrument they were just acting on
    instead of being yanked to the top of the page. Bulk actions
    (accepting / visibility all-on/off) pass no fragment — they
    affect the whole list, so landing at the top is appropriate.

    Lifted to ``_shared.py`` in Segment 18N PR 3 alongside
    ``_require_instrument_in_session``."""
    url = f"/operator/sessions/{session_id}/instruments"
    if fragment:
        url = f"{url}#{fragment}"
    return urls.redirect(request, url=url, status_code=status.HTTP_303_SEE_OTHER)


def dismiss_held_upload(
    request: Request, db: Session,
    *,
    held_token: str | None,
    user: User,
    review_session: ReviewSession,
    page: str,
) -> RedirectResponse:
    """A Setup upload card's Dismiss while its ask holds a file: end the
    hold, then back to the card with the panel open (segment 19W).
    ``page`` is the route segment (``reviewers``, ``reviewees``,
    ``relationships``, ``observers``), never a URL from the form."""
    release_hold(db, token=held_token, user=user, review_session=review_session)
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/{page}"
            "?unlocked=1#upload-csv"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def directory_or_none(request: Request) -> Directory | None:
    """The directory as the signed-in operator sees it (segment 21F), or
    ``None`` without a delegated token, which checks nothing."""
    try:
        return directory_for(request)
    except GraphError:
        return None


def directory_search_response(directory: Directory | None, q: str) -> JSONResponse:
    """A directory picker's answer (19Z, invite from the directory): up
    to ten people whose name, surname, mail or sign-in name starts with
    ``q``, each with the address a pick fills (the mail, else the UPN).
    ``available`` is false when the directory cannot be asked, and
    ``reason`` then says why. Never cached; not audited (author,
    2026-11-01)."""
    found = directory_accounts.search(directory, q)
    answer: dict[str, object] = {
        "available": found.people is not None,
        "people": [
            {"name": p.name, "mail": p.mail, "upn": p.upn, "address": p.address}
            for p in (found.people or [])
        ],
    }
    if found.reason:
        answer["reason"] = found.reason
    return JSONResponse(answer, headers={"Cache-Control": "no-store"})


def account_resolver(request: Request):
    """The single-row add and edit's lookup (segment 21F): one address
    resolved on demand, through the operator's directory if there is one."""
    return directory_accounts.resolver(directory_or_none(request))


def roster_address(row: object) -> str | None:
    """A parsed roster row's address: a reviewer's or observer's email,
    a reviewee's email or identifier."""
    return getattr(row, "email", None) or getattr(row, "email_or_identifier", None)


async def _handle_import(
    *,
    request: Request,
    file: UploadFile | None,
    held_token: str | None,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
    append: str | None = None,
    merge: str | None = None,
    acknowledge_group_clear: str | None = None,
) -> HTMLResponse | RedirectResponse:
    """Shared Reviewers / Reviewees CSV-import handler.

    ``kind`` is ``"reviewers"`` or ``"reviewees"``; the *_fn callables
    are the matching ``csv_imports`` entry points. On a parse / confirm
    / ack failure it re-renders the Setup page with the reason in the
    upload card's banner; on success it saves and 303s back to the
    page.

    An ask (no tick, both ticks, or the response-loss ack) holds the
    file, so the next submit answers it with no file chosen (segment
    19W); a save or a plain refusal ends the hold.

    ``append`` is the card's append tick (segment 19Z): the file's rows
    are added and nothing is replaced, so no response-loss ack applies.
    A row already on the roster, or on a directory account already
    there, refuses the file as its problems.

    ``merge`` is the merge tick (the upsert amendment): matched rows are
    updated, the rest added. A Reviewees merge whose tag changes would
    clear saved group answers asks first with the count, as the row
    editor does; its tick is ``acknowledge_group_clear``, a field of its
    own, since the card's hidden ``acknowledge_response_loss`` already
    carries ``true`` for a replace."""
    _require_editable(review_session)
    upload = await read_upload(
        db,
        file=file,
        held_token=held_token,
        user=user,
        review_session=review_session,
        slot=kind,
    )
    result = parse_fn(upload.content)
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

    # An append onto an empty roster is just the roster (plan,
    # Decision): only a direct POST can send one, as the card shows no
    # ticks there.
    appending = append == "true" and existing > 0
    merging = merge == "true" and existing > 0
    ticked = (confirm_replace == "true") + appending + merging

    def render(
        status_code: int = status.HTTP_200_OK,
        *,
        missing_confirm: bool = False,
        missing_response_ack: bool = False,
        both_ticks: bool = False,
        held_upload: dict[str, str] | None = None,
        group_clear: dict[str, object] | None = None,
    ) -> HTMLResponse:
        context: dict[str, object] = {
            # These two are the ids the page's own controls point at.
            # They were missing here, and Jinja's `Undefined` is falsy
            # rather than loud — so this re-render emitted `id=""` on
            # the table card and a bare `#` on every control that
            # targets it, which means "top of document". The landing
            # anchors silently did nothing on exactly the page where an
            # operator is reading hardest: a failed import.
            "pager_anchor": f"{kind}-table-card",
            "row_editor_anchor": f"{kind}-row-editor",
            # Same reason as the two above, and the same failure mode:
            # this path re-renders the page template, so it owes every
            # key that template reads. Without these, Reviewers rendered
            # `<input name="filter_offset" value="">` on a failed import
            # — harmless today only because an empty form value reads as
            # absent for an `int` field with a default, and because this
            # path renders unpaged so 0 is the right answer anyway.
            #
            # 19P.1 rung 3c moved the import card INTO the Unlock
            # panel, so this line flipped, as the rung-3 slicing said it
            # would have to. The panel ships `hidden` unless the server
            # says otherwise, and `?unlocked=1` cannot reach an in-place
            # re-render — this path returns 400 with the page, it does
            # not redirect. Left False, a failed import would answer
            # with a collapsed panel and the operator would see no
            # errors at all: `_upload_problems.html` renders the file's
            # problems inside that card.
            #
            # The suite cannot catch a regression here. With no JS
            # runtime `hidden` is an inert attribute, so the issues are
            # in the markup and every assertion on them passes either
            # way; Chromium is what proves it. Third time this shape has
            # bitten this segment (`.is-locked`, `.filter-actions`).
            #
            # 19P.3 rung 4 — BOTH kinds now, and the literal collapses
            # rather than gaining a branch. This handler serves exactly
            # `reviewers` and `reviewees`, and both render the panel
            # since Reviewees gained one, so there is no page left for
            # which the flag means nothing.
            "current_offset": 0,
            "panel_open": True,
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            list_key: list_items,
            "existing_count": existing,
            "directory_check": views.last_directory_check(db, review_session, kind),
            "assignment_count": assignment_count,
            "upload_problems": views.upload_problems(
                kind,
                result.issues,
                missing_confirm=missing_confirm,
                missing_response_ack=missing_response_ack,
                both_ticks=both_ticks,
            ),
            "filename": upload.filename,
            # Segment 19W: the file an ask holds, named in the card in
            # place of the empty input; a hold that had lapsed; and the
            # replace tick, ticked again when the operator had ticked it
            # (author, 2026-10-19).
            "held_upload": held_upload,
            "held_upload_lost": upload.lost,
            "confirm_replace_checked": (
                held_upload is not None and confirm_replace == "true" and not both_ticks
            ),
            # Segment 19Z: the append and merge ticks, likewise. None
            # comes back on the both-ticks ask, which asks the operator
            # to choose.
            "append_checked": held_upload is not None and appending and not both_ticks,
            "merge_checked": held_upload is not None and merging and not both_ticks,
            # A Reviewees merge refused for clearing group answers: the
            # count and line, offered back with a tick in the card.
            "group_clear": group_clear,
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
                # 19I Item 12 rung 2 — this path re-renders the same
                # template, so it owes it the same chip flags. Missing
                # them here would render every chip as "no data" on a
                # failed import, which is exactly when an operator is
                # looking hardest at which columns arrived.
                # 19P.1 — this path re-renders the same template, so it
                # owes it the same keys. The comment above says why that
                # matters; ``col_readouts`` is now one of them, and an
                # absent key would raise in the index row rather than
                # degrade quietly.
                column_state = views.reviewer_column_state(db, review_session)
                col_data = column_state.col_data
                col_readouts = column_state.readouts
                # participant info Item 1 — the same lesson again: the
                # Unlock panel's self-fields card and the readout row's
                # `Reviewers see:` pills read three keys this path owes.
                context.update(
                    views.reviewer_self_card_context(
                        review_session, col_readouts
                    )
                )
            else:
                status_options = views.REVIEWEES_STATUS_OPTIONS
                search_options = views.reviewees_search_options(list_items)
                # 19P.3 rung 4 — same as the branch above, and for the
                # same reason. This once set ``col_readouts = []`` with
                # a note that Reviewees had no index row yet; once it
                # had one, the empty list stopped being a placeholder
                # and started being a lie — a failed import rendered
                # an empty index ("Populated columns: none yet", as the
                # row then read) over a roster of three.
                # One helper answers both keys, so they cannot drift.
                column_state = views.reviewee_column_state(db, review_session)
                col_data = column_state.col_data
                col_readouts = column_state.readouts
                # participant info Item 4 — Item 1's lesson, kept: this
                # path owes the own-entry card and readout their keys.
                context.update(
                    views.reviewee_self_card_context(
                        review_session, col_readouts
                    )
                )
            context.update(
                {
                    "total_row_count": len(list_items),
                    "displayed_row_count": len(list_items),
                    # Segment 19I Item 10 — this path renders the
                    # whole roster unfiltered and uncapped, so the
                    # shared count line has nothing to report. Set
                    # explicitly rather than left undefined: an
                    # absent key would render the same today, but
                    # only by relying on Jinja's undefined being
                    # falsy.
                    "preview_count_line": None,
                    "filter_status": "all",
                    "filter_search": "",
                    "filter_status_options": status_options,
                    "filter_search_options": search_options,
                    "is_ready": lifecycle.is_ready(review_session),
                    # Segment 19I Item 3. This render path builds its
                    # own context, so every key the strip reads has to
                    # be repeated here. `delete_discards_responses`
                    # (Item 2) was missing and **nothing failed**:
                    # Jinja's `Undefined` is falsy in `{% if %}`, so
                    # the label silently took its no-loss branch on
                    # this page. Only `roster_response_count`, which is
                    # compared rather than tested, raised — which is
                    # how the older omission was found.
                    "is_editable": lifecycle.is_editable(review_session),
                    # No ``is_archived``: this path is behind
                    # ``_require_editable`` above, so it renders only
                    # when editable, and the lock card (19H.6) gates on
                    # ``not is_editable`` and never reads it here.
                    "delete_discards_responses": (
                        lifecycle.session_has_responses(db, review_session)
                    ),
                    "delete_discards_assignments": assignment_count > 0,
                    "roster_response_count": (
                        lifecycle.session_response_count(db, review_session)
                    ),
                    # 19O.5 rung 2 — this path builds its own context,
                    # so it owes the per-row counts the rows read. An
                    # absent key raises in the `<tr>` rather than
                    # degrading quietly; twelve tests caught it, which
                    # is the third time this handler has taught the
                    # lesson (19P.1, 19P.3, here).
                    "relationships_per_row": roster_bulk.relationships_per_row(
                        db,
                        model=Reviewer if kind == "reviewers" else Reviewee,
                        session_id=review_session.id,
                    ),
                    "col_data": col_data,
                    "col_readouts": col_readouts,
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

    def ask() -> dict[str, str] | None:
        return hold_for_ask(
            db, upload=upload, user=user, review_session=review_session,
            slot=kind,
        )

    if result.is_blocked:
        release_hold(
            db, token=upload.token, user=user, review_session=review_session
        )
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and ticked > 1:
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            both_ticks=True,
            held_upload=ask(),
        )

    if existing > 0 and ticked == 0:
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            missing_confirm=True,
            held_upload=ask(),
        )

    # The same gate as `_require_response_loss_ack`, answered in the
    # upload card's banner rather than as a full error page: that page
    # asked for an "acknowledge response loss" tick no page offers. The
    # card sends the field beside the tick whenever it names responses,
    # so this is a tab loaded before the session had any, or a direct
    # POST; the re-render names them and carries the field.
    if (
        existing > 0
        and not appending
        and not merging
        and acknowledge_response_loss != "true"
        and lifecycle.session_has_responses(db, review_session)
    ):
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            missing_response_ack=True,
            held_upload=ask(),
        )

    # Segment 21F: each address resolved through the directory on the
    # operator's token, at the save and not at an ask, so a held file is
    # looked up once. Off the event loop, as the lookups block.
    directory_check = await run_in_threadpool(
        csv_imports.directory_check,
        directory_or_none(request),
        [roster_address(row) for row in result.rows],
    )
    # Segment 19Z: an append refuses a row already on the roster, or on
    # a directory account already there, as the file's problems. The
    # save checks again under the session lock.
    if appending:
        result.issues.extend(
            csv_imports.append_conflicts(
                db,
                session_id=review_session.id,
                kind=kind,
                rows=result.rows,
                directory=directory_check,
            )
        )
        if result.is_blocked:
            release_hold(
                db, token=upload.token, user=user, review_session=review_session
            )
            return render(status_code=status.HTTP_400_BAD_REQUEST)
    # A merge refuses two file rows on one directory account.
    if merging:
        result.issues.extend(
            csv_imports.merge_conflicts(kind=kind, rows=result.rows, directory=directory_check)
        )
        if result.is_blocked:
            release_hold(
                db, token=upload.token, user=user, review_session=review_session
            )
            return render(status_code=status.HTTP_400_BAD_REQUEST)
    extra: dict[str, object] = {}
    if merging:
        extra["merge"] = True
        extra["columns"] = result.columns
        if kind == "reviewees":
            extra["acknowledged_loss"] = acknowledged_loss(acknowledge_group_clear)
    # The service locks the session row (findings Bc4): wait for it off
    # the event loop.
    try:
        await run_in_threadpool(
            save_fn,
            db,
            session=review_session,
            user=user,
            rows=result.rows,
            filename=upload.filename or "",
            correlation_id=request_correlation_id(),
            field_labels_captured=result.field_labels,
            directory=directory_check,
            append=appending,
            **extra,
        )
    except csv_imports.AppendConflict as refused:
        db.rollback()
        result.issues.extend(refused.issues)
        release_hold(db, token=upload.token, user=user, review_session=review_session)
        return render(status_code=status.HTTP_400_BAD_REQUEST)
    except GroupAnswersWouldClear as exc:
        # Rolled back in the save's own unit; roll back again before the
        # hold commits, so nothing of the refused merge rides with it.
        db.rollback()
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            held_upload=ask(),
            group_clear={"count": exc.count, "message": str(exc), "surface": "import"},
        )
    release_hold(db, token=upload.token, user=user, review_session=review_session)
    # 19P.1 rung 3c — a successful import lands back with the panel still
    # open, matching the two controls that moved before it (the labels
    # save and delete-all). The author's rule from the UI pass: a Save
    # does not close the roster card, the Lock button does.
    # `#roster-card` lands on the card instead of the top of the
    # document.
    #
    # 19P.3 rung 4 — unconditional now. This was
    # `if kind == "reviewers" else ""` while Reviewees had no panel to
    # keep open; it has one, and this handler serves no other kind.
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/{kind}"
            "?unlocked=1#roster-card"
        ),
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

    Rejected with 409 whenever the session is not editable — labels
    are locked alongside the rest of the page's data once it stops
    being a draft; operators revert to draft to rename.

    Segment 19H Item 7. This was ``is_ready`` from Segment 15A until
    then, so ``expired`` and ``archived`` sessions accepted the save
    (303) while the page's lock card said the roster could not be
    modified — 19H.6 put that card on those two states and turned a
    quiet inconsistency into a page contradicting itself. The gate is
    now ``_require_editable``'s predicate, so the editor, the Upload
    and Danger Zone cards, the selection surface and the lock card
    all answer one question.
    """
    if not lifecycle.is_editable(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to "
                "draft to rename labels."
            ),
        )
    # Every slot is checked before any is written, so an over-long label
    # refuses the save whole rather than landing the slots before it, or
    # reaching Postgres as a 500 (findings Cc3).
    for form_param, _ in slots:
        too_long = field_labels_service.label_length_error(
            submitted.get(form_param) or ""
        )
        if too_long is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=too_long,
            )
    # One commit for the form, so each slot's gate decides under the lock
    # the first one took, and a refusal part-way lands none of them
    # (findings Bc4; Codex on #2882).
    with unit_of_work.atomic(db):
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


# ------------------------------------------------------------------ #
# Session Home render — shared by its GET and the Quick Setup routes'
# refusals (findings O7).
# ------------------------------------------------------------------ #


def render_session_home(
    request: Request,
    db: Session,
    *,
    user: User,
    review_session: ReviewSession,
    quick_setup: views.QuickSetupContext | None = None,
    super_failure: dict[str, str] | None = None,
    prepare_confirm: str | None = None,
    editing: bool = False,
    owners_error: str | None = None,
    symmetric_preview_variant: str | None = None,
    http_status: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Render Session Home.

    Its GET calls this after the scheduled-event observer; the Quick
    Setup routes call it on an existing session to answer a refused
    upload in place, at 422, with ``quick_setup`` carrying the banner
    and the file's own lines, which therefore never ride a URL
    (findings O7). ``quick_setup`` defaults to the card with no banner."""
    setup_rows = views.build_setup_rows(db, review_session)
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="home",
        super_failure=super_failure,
        prepare_confirm=prepare_confirm,
    )
    if quick_setup is None:
        quick_setup = views.build_quick_setup_context(
            db, review_session, user=user
        )
    # 18R Item 4 Slice 2 (mock-up) — the same schedule input-value
    # prefills the Edit route builds, so the inert Session config card
    # can render filled edit boxes. Reused verbatim; the edit-mode
    # wiring in a later slice consumes them for real.
    session_tz = sessions_service.resolve_session_timezone(review_session)
    return _templates.TemplateResponse(
        request,
        "operator/session_detail.html",
        {
            "user": user,
            "session": review_session,
            "symmetric_preview": symmetric_preview_variant,
            "setup_rows": setup_rows,
            "status_pills": views.session_status_pills(db, review_session),
            "has_responses": lifecycle.session_has_responses(db, review_session),
            "quick_setup": quick_setup,
            "session_timezone_label": date_formatting.gmt_offset_zone_label(
                session_tz
            ),
            # Schedule input-value prefills for the Session config card
            # mock-up (18R Item 4 Slice 2) — mirror the Edit route.
            "scheduled_activate_at_input_value": (
                date_formatting.format_datetime_box(
                    review_session.scheduled_activate_at, session_tz
                )
            ),
            "deadline_input_value": date_formatting.format_datetime_box(
                review_session.deadline, session_tz
            ),
            "responses_release_at_input_value": (
                date_formatting.format_datetime_box(
                    review_session.responses_release_at, session_tz
                )
            ),
            "responses_release_until_input_value": (
                date_formatting.format_datetime_box(
                    review_session.responses_release_until, session_tz
                )
            ),
            "invite_offsets_input_value": ", ".join(
                review_session.invite_offsets or []
            ),
            "reminder_offsets_input_value": ", ".join(
                review_session.reminder_offsets or []
            ),
            # 18R Item 4 — display mode shows each offset + its resolved
            # send datetime (invites off Start, reminders off End).
            "invite_offset_rows": views.build_offset_display_rows(
                review_session.scheduled_activate_at,
                review_session.invite_offsets,
                session_tz,
            ),
            "reminder_offset_rows": views.build_offset_display_rows(
                review_session.deadline,
                review_session.reminder_offsets,
                session_tz,
            ),
            # The Owners card: the current owners, and the Add-owner
            # picker's candidates — operators not already owners.
            "config_owners": session_owners.list_owners(db, review_session),
            "config_owner_candidates": (
                session_owners.session_owner_candidates(db, review_session)
            ),
            # 19S Item 9 Part B — the details card's Tags field, shown as a
            # ``.config-value`` when locked and prefilled when editing.
            "session_tag_list": session_tags.tags_for_sessions(
                db, [review_session.id]
            )[review_session.id],
            # 19S Item 7 — the Tags field's typeahead.
            "tag_vocabulary": session_tags.vocabulary_for_user(db, user),
            # Owner add/remove errors, the Owners card's banner
            # (redirected here from the routes; 19S Item 10).
            "owners_error": owners_error,
            # 18R Item 4 Slice 3 — edit-mode wiring for the Session details
            # card. ``config_editing`` is the canonical server state (from
            # ``?editing=1``), gated on the session actually being editable so a
            # stale link on an activated session degrades to display mode. The
            # timezone options + current zone feed the edit-mode timezone
            # datalist; the has-* signals lock the UI-settings checkboxes when a
            # roster has rows (mirrors the Edit page + service-layer guard).
            "config_editing": (
                editing
                and (
                    lifecycle.is_draft(review_session)
                    or lifecycle.is_validated(review_session)
                )
            ),
            "timezone_options": operator_settings.timezone_options(),
            "current_session_timezone": session_tz,
            "has_relationships": sessions_service._has_relationships(
                db, review_session.id
            ),
            "has_observers": sessions_service._has_observers(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session(review_session),
            **workflow_ctx,
        },
        status_code=http_status,
    )
