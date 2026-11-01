"""Reviewees Setup page — the list / edit / add view, its CSV
import, bulk status actions, delete-all, and friendly-label editor.

Split out of ``_setup_rosters.py`` in Segment 17A PR 3; the shared
import / redirect / field-label plumbing now lives in ``_shared.py``.
The reviewee surface mirrors ``_setup_reviewers.py`` with the
identity field ``email_or_identifier`` and an extra ``profile_link``.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.web import urls
from app.db.models import Reviewee, ReviewSession, User
from app.db.session import get_db
from app.services import assignments, csv_imports, participant_info
from app.services import responses as responses_service
from app.services import reviewees as reviewees_service
from app.services import roster_bulk
from app.services import session_lifecycle as lifecycle
from app.services.reviewees import RevieweeOperationError
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    require_reviewees_editable_session,
    account_resolver,
    _setup_row_window,
    _handle_import,
    dismiss_held_upload,
    acknowledged_loss,
    _redirect_keeping_selection,
    _row_action_anchor,
    _require_delete_confirm,
    _require_editable,
    _require_selected_response_loss_ack,
    _require_response_loss_ack,
    _save_field_labels,
    _templates,
)

router = APIRouter()


_REVIEWEE_SORT_KEYS = {
    "name",
    "email_or_identifier",
    "tag_1",
    "tag_2",
    "tag_3",
    "status",
    "updated_at",
}


def _reviewee_sort_value(reviewee, key: str):
    """Sort-key resolver for the Reviewees Setup table (Segment 13B
    Part 2 PR 6)."""
    return getattr(reviewee, key, None)


@router.post(
    "/sessions/{session_id}/reviewees/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewees_import_submit(
    request: Request,
    # Optional since segment 19W: with an ask's file held, the card
    # submits with no file chosen and ``held_token`` names the hold.
    file: UploadFile | None = File(default=None),
    held_token: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    # Segment 19Z: the card's append and merge ticks, beside the replace
    # tick, and a merge's group-clear answer (Reviewees).
    append: str | None = Form(default=None),
    merge: str | None = Form(default=None),
    acknowledge_group_clear: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await _handle_import(
        request=request,
        file=file,
        held_token=held_token,
        confirm_replace=confirm_replace,
        append=append,
        merge=merge,
        acknowledge_group_clear=acknowledge_group_clear,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewees",
        existing_count_fn=csv_imports.existing_reviewee_count,
        parse_fn=csv_imports.parse_reviewee_csv,
        save_fn=csv_imports.save_reviewees,
    )


@router.post("/sessions/{session_id}/reviewees/import/dismiss")
def reviewees_import_dismiss(
    request: Request, held_token: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """The upload card's Dismiss while an ask holds its file: end the
    hold and return to the card (segment 19W)."""
    return dismiss_held_upload(request,
        db, held_token=held_token, user=user,
        review_session=review_session, page="reviewees",
    )


def _render_reviewees_page(
    *,
    request: Request,
    db: Session,
    user: User,
    review_session: ReviewSession,
    status_filter: str = "all",
    search: str = "",
    offset: int = 0,
    edit_id: int | None = None,
    # 19P.3 rung 1 — the created row, so the pager window can be
    # relocated onto the page holding it. See the create route.
    focus_id: int | None = None,
    add_mode: bool = False,
    edit_values: dict[str, str] | None = None,
    edit_error: str | None = None,
    # The count a refused tag edit would clear, which the row editor
    # offers back with a ``Yes, clear them`` tick (warnings_updates.md).
    edit_confirm_group_clear: int | None = None,
    selected_ids: set[int] | None = None,
    # 19P.3 rung 4 — whether the page ARRIVES with the Unlock panel
    # open. Server state, not a second source of truth for the JS
    # toggle: the toggle still owns every click, this only decides the
    # starting state. Saving a label POSTs and 303s, and a panel that
    # always shipped collapsed would shut itself on every save — the
    # Lock control is what closes it.
    panel_open: bool = False,
    http_status: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Render the Reviewees Setup page — the reviewee-side mirror of
    ``_render_reviewers_page`` (Segment 15F PR 4)."""
    is_ready = lifecycle.is_ready(review_session)
    column_state = views.reviewee_column_state(db, review_session)
    # Segment 19H Item 6 — the lock-card partial branches on
    # ``archived`` (no revert form: ``/revert`` 409s from there).
    # Observers already passed this for its checkbox exception.
    is_archived = lifecycle.is_archived(review_session)
    if not lifecycle.is_editable(review_session) or review_session.symmetric_review:
        # The editor renders only where `create` / `update` accept
        # (`_require_editable`). Was `is_ready` (findings C3). Under
        # symmetric review they answer 409 (20B), so it renders nowhere.
        edit_id = None
        add_mode = False

    all_reviewees = assignments.list_reviewees(db, review_session.id)
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=f"rrw-sort-reviewees-{review_session.public_id}",
        valid_keys=_REVIEWEE_SORT_KEYS,
    )
    all_reviewees = views.apply_cookie_sort(
        all_reviewees,
        sort_spec,
        value_resolver=_reviewee_sort_value,
    )

    filtered = views.filter_reviewees_rows(
        all_reviewees, status=status_filter, search=search
    )
    is_filtered = status_filter != "all" or bool(search.strip())
    # Segment 19J.5 rung 2 — the cap became a page size. The shared
    # helper cuts the window, clamps a stale ``offset`` onto a real
    # boundary, and lands the operator on the page that holds the row
    # they are editing instead of prepending it to whatever page they
    # happened to be on.
    window = _setup_row_window(
        filtered=filtered,
        all_rows=all_reviewees,
        is_filtered=is_filtered,
        offset=offset,
        locate_id=focus_id,
        edit_id=edit_id,
    )
    reviewees = window.rows
    offset = window.offset
    edit_id = window.edit_id
    displayed_row_count = len(reviewees)

    if edit_values is None and edit_id is not None:
        edited = next(
            (r for r in reviewees if r.id == edit_id), None
        )
        if edited is not None:
            edit_values = {
                "name": edited.name,
                "email_or_identifier": edited.email_or_identifier,
                "profile_link": edited.profile_link or "",
                "tag_1": edited.tag_1 or "",
                "tag_2": edited.tag_2 or "",
                "tag_3": edited.tag_3 or "",
                "status": edited.status,
            }
    if edit_values is None and add_mode:
        edit_values = {
            "name": "",
            "email_or_identifier": "",
            "profile_link": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        }

    return _templates.TemplateResponse(
        request,
        "operator/session_reviewees.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewees": reviewees,
            "selected_ids": selected_ids or set(),
            "total_row_count": len(all_reviewees),
            # Segment 19I Item 2 — decides whether the strip renders
            # the response-loss acknowledgement beside its confirm
            # checkbox. Session-wide, because at render time the
            # page cannot know which rows will be selected; the
            # route then gates on the *selected* rows' exact
            # count, so a tick on a selection that carries no
            # responses costs nothing.
            # Segment 19I Item 3 — the confirmation names what the
            # delete destroys, modelled on the Instruments page. A
            # roster whose rows carry assignments loses them even
            # when no response has been saved, so the two clauses
            # are separate flags rather than one.
            "delete_discards_assignments": (
                csv_imports.existing_assignment_count(db, review_session.id) > 0
            ),
            "roster_response_count": lifecycle.session_response_count(
                db, review_session
            ),
            # 19O.5 rung 2 — per row, because the expander's
            # confirmation names what THIS SELECTION costs and the
            # selection lives in the browser. `data-status` is the
            # precedent: a server fact carried on the `<tr>` and summed
            # client-side.
            "relationships_per_row": roster_bulk.relationships_per_row(
                db, model=Reviewee, session_id=review_session.id
            ),
            "delete_discards_responses": (
                lifecycle.session_has_responses(db, review_session)
            ),
            "displayed_row_count": displayed_row_count,
            # Segment 19I Item 10 — the one preview-count
            # sentence the seven table pages share. The
            # branching lives in the view helper; the
            # template renders whatever string it returns.
            # Segment 19J.5 rung 1 — the scaffold. The ranges are real,
            # computed from the real count; the links are inert until a
            # later rung supplies ``pager_url_base``. ``None`` while a
            # filter is active is the suppression rule: the operator's
            # own partition of the roster wins, and the count line
            # speaks for that view instead. Both read the same
            # ``is_filtered``, so the two affordances can never
            # disagree about which mode the page is in.
            "pager": window.pager,
            # Only ever rendered on an unfiltered view, so the link
            # carries no filter state to preserve — and deliberately
            # not ``selected``: selection is page-local, and carrying
            # a hidden one across a page boundary is how an operator
            # deletes something they cannot see.
            "pager_url_base": (
                f"/operator/sessions/{review_session.public_id}/reviewees?"
            ),
            # The fragment the range links land on (19J.8): the
            # table's card, so a page turn arrives showing the card's
            # top edge, the column chips, the page links and the new
            # rows — in that order down the screen. Passed rather than
            # derived: a macro guessing the id would land silently at
            # the top of the document the first time someone renamed
            # it, which is a failure with no error.
            "pager_anchor": "reviewees-table-card",
            # 19P.3 rung 3 — the add row's own id, and what `Add new`
            # lands on. There is no editor card to name any more: the
            # editor IS the row. `Edit` does not use it — it builds
            # `#reviewee-row-<id>` from the id it already has.
            "row_editor_anchor": "reviewees-row-editor",
            # 19P.3 rung 1 — the pager offset the row-action forms
            # post back, so a mid-table action returns to the page
            # it was taken on rather than to page 1.
            "current_offset": offset,
            # Segment 19J.5 rung 2 — the sentence is the filter's now,
            # not the table's: where the pager renders, the ranges
            # already say where the operator is.
            "preview_count_line": views.preview_count_line(
                shown=displayed_row_count,
                pool=len(filtered),
                noun="reviewees",
                is_filtered=is_filtered,
            ),
            "filter_status": status_filter,
            "filter_search": search,
            "filter_status_options": views.REVIEWEES_STATUS_OPTIONS,
            "filter_search_options": views.reviewees_search_options(
                all_reviewees
            ),
            "existing_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "directory_check": views.last_directory_check(db, review_session, "reviewees"),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "upload_problems": None,
            "is_ready": is_ready,
            "is_archived": is_archived,
            # Segment 19I Item 3 — the gate on the selection surface.
            # ``is_ready`` is only ``status == "ready"``, so gating on it
            # left `expired` and `archived` sessions rendering checkboxes
            # and a live Delete while every mutation 409d. This is what
            # ``_require_editable`` enforces, so page and route agree by
            # construction rather than by two lists kept in step.
            "is_editable": lifecycle.is_editable(review_session),
            "panel_open": panel_open,
            # 19I Item 12 rung 2 — the chips' has-data flags, answered
            # over the whole roster by query rather than by scanning
            # whichever rows this render produced. Keyed by the page's
            # own chip slot names, so the template reads a flag instead
            # of computing one.
            # 19P.3 rung 4 — the readouts and the visibility flags come
            # from ONE query set (`RosterColumnState`). They answer the
            # same predicate — `col_data["tag-n"]` is exactly
            # `counts["tag_n"] > 0` — so asking twice would be two round
            # trips for one fact, and would leave a window where a
            # concurrent delete renders a chip reading `Tag 1 (0)`.
            "col_data": column_state.col_data,
            "col_readouts": column_state.readouts,
            # participant info Item 4 — what reviewees see of their own
            # entry on `/results`: the Unlock panel's chips and the
            # readout row's pills (rung 2, the scaffold: the default).
            **views.reviewee_self_card_context(
                review_session, column_state.readouts
            ),
            "edit_id": edit_id,
            "add_mode": add_mode,
            "edit_values": edit_values,
            "edit_error": edit_error,
            "edit_confirm_group_clear": edit_confirm_group_clear,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Reviewees"
            ),
        },
        status_code=http_status,
    )


@router.get("/sessions/{session_id}/reviewees", response_class=HTMLResponse)
def reviewees_list(
    request: Request,
    status_filter: str = Query(default="all", alias="status"),
    q: str = "",
    offset: int = 0,
    edit_id: int | None = None,
    add: int = 0,
    focus: int | None = None,
    selected: list[int] = Query(default=[]),
    # 19P.3 rung 4 — `?unlocked=1` renders the Unlock panel open. It
    # exists for the redirects the panel's own controls answer with, and
    # doubles as the no-JS way in (the `<noscript>` link beside the
    # toggle).
    unlocked: int = 0,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_reviewees_page(
        request=request,
        db=db,
        user=user,
        review_session=review_session,
        status_filter=status_filter,
        search=q,
        offset=offset,
        edit_id=edit_id,
        add_mode=bool(add),
        focus_id=focus,
        selected_ids=set(selected),
        panel_open=bool(unlocked),
    )


def _require_reviewee_in_session(
    db: Session, review_session: ReviewSession, reviewee_id: int
) -> Reviewee:
    reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.id == reviewee_id,
            Reviewee.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if reviewee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return reviewee


@router.post(
    "/sessions/{session_id}/reviewees/create",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewees_create(
    request: Request,
    name: str = Form(default=""),
    email_or_identifier: str = Form(default=""),
    profile_link: str = Form(default=""),
    tag_1: str = Form(default=""),
    tag_2: str = Form(default=""),
    tag_3: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    # 19P.3 rung 1 — the filter round-trip the other four row
    # actions already had. Create never carried it, so a create
    # from a filtered view answered unfiltered.
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    try:
        created = reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name=name,
            email_or_identifier=email_or_identifier,
            profile_link=profile_link,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
            resolve_account=account_resolver(request),
        )
    except RevieweeOperationError as exc:
        return _render_reviewees_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            add_mode=True,
            edit_values={
                "name": name,
                "email_or_identifier": email_or_identifier,
                "profile_link": profile_link,
                "tag_1": tag_1,
                "tag_2": tag_2,
                "tag_3": tag_3,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    # 19P.3 rung 1 — this route answered with a BARE redirect: no
    # selection, no filter, no offset, no fragment. So a create from a
    # filtered, paged view threw the operator back to an unfiltered
    # page 1 at the top of the document, losing more than the other
    # four row actions did. The ladder called this "five POSTs gain
    # offset and a fragment"; on this page it is also the filter
    # round-trip the other four already had.
    #
    # `focus` is the create-only half: rows list by id, so a new row
    # appends past the end and on a roster over one page is not on the
    # page the form was submitted from — the fragment would name a row
    # the response never rendered. It relocates the pager window; the
    # fragment then resolves onto the row.
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/reviewees",
        [],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        extra_params=[("focus", created.id)],
        anchor=_row_action_anchor([created.id], noun="reviewee"),
    )


@router.post(
    "/sessions/{session_id}/reviewees/{reviewee_id}/update",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewees_update(
    request: Request,
    reviewee_id: int,
    name: str = Form(default=""),
    email_or_identifier: str = Form(default=""),
    profile_link: str = Form(default=""),
    tag_1: str = Form(default=""),
    tag_2: str = Form(default=""),
    tag_3: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    acknowledge_response_loss: str = Form(default=""),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    reviewee = _require_reviewee_in_session(db, review_session, reviewee_id)
    edit_values = {
        "name": name,
        "email_or_identifier": email_or_identifier,
        "profile_link": profile_link,
        "tag_1": tag_1,
        "tag_2": tag_2,
        "tag_3": tag_3,
        "status": status_value,
    }
    try:
        reviewees_service.update_reviewee(
            db,
            reviewee=reviewee,
            name=name,
            email_or_identifier=email_or_identifier,
            profile_link=profile_link,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
            acknowledged_loss=acknowledged_loss(acknowledge_response_loss),
            resolve_account=account_resolver(request),
        )
    except RevieweeOperationError as exc:
        return _render_reviewees_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            edit_id=reviewee_id,
            edit_values=edit_values,
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    except responses_service.GroupAnswersWouldClear as exc:
        # Refuse, then re-offer (author's ruling 2026-10-17): the edit
        # was flushed, so roll it back and re-render the row editor with
        # the operator's values, the count and a ``Yes, clear them`` tick.
        db.rollback()
        return _render_reviewees_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            edit_id=reviewee_id,
            # The view the operator was on, so the re-offered Save
            # carries it too (Codex on #3103).
            status_filter=filter_status,
            search=filter_q,
            offset=filter_offset,
            edit_values=edit_values,
            edit_error=str(exc),
            edit_confirm_group_clear=exc.count,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/reviewees",
        [reviewee_id],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor([reviewee_id], noun="reviewee"),
    )


@router.post(
    "/sessions/{session_id}/reviewees/self-fields",
    response_class=RedirectResponse,
)
async def reviewees_save_self_fields(
    request: Request,
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save what reviewees see of their own entry (participant info
    Item 4), as the Reviewers card saves Item 1's: the ticked chips plus
    ``keep``, the selected keys the card offered no chip for."""
    form = await request.form()
    keys = [str(v) for v in form.getlist("fields")]
    keys += [str(v) for v in form.getlist("keep")]
    try:
        # The service locks the session row: wait for it off the loop.
        await run_in_threadpool(
            participant_info.set_self_fields,
            db,
            review_session=review_session,
            user=user,
            participant="reviewee",
            keys=keys,
            correlation_id=request_correlation_id(),
        )
    except participant_info.SelfFieldsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/reviewees"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/reviewees/bulk-inactivate")
def reviewees_bulk_inactivate(
    request: Request, reviewee_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        reviewees_service.bulk_inactivate(
            db,
            review_session=review_session,
            reviewee_ids=reviewee_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/reviewees",
        reviewee_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(reviewee_ids, noun="reviewee"),
    )


@router.post("/sessions/{session_id}/reviewees/bulk-reactivate")
def reviewees_bulk_reactivate(
    request: Request, reviewee_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        reviewees_service.bulk_reactivate(
            db,
            review_session=review_session,
            reviewee_ids=reviewee_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/reviewees",
        reviewee_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(reviewee_ids, noun="reviewee"),
    )


@router.post("/sessions/{session_id}/reviewees/delete-all")
def reviewees_delete_all(
    request: Request, confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    _require_response_loss_ack(db, review_session, acknowledge_response_loss)
    csv_imports.delete_all_reviewees(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    # 19P.3 rung 4 — `?unlocked=1#roster-card`. This control lives INSIDE
    # the Unlock panel now, and a bare redirect closes the panel the
    # operator was working in: a Save does not close the card, the Lock
    # control does. The fragment lands on the card rather than the top of
    # the document.
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/reviewees"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Allowlist of (form_param, source_field) the reviewee label editor
# accepts, mirroring ``app.services.field_labels._VALID_SOURCE_FIELDS``
# (Segment 15A Slice 3). Identity columns retired 2026-05-31 per
# ``guide/archive/participant_model_upgrade.md`` §3.7 — only the three tag
# slots remain.
_REVIEWEE_SLOTS: tuple[tuple[str, str], ...] = (
    ("tag_1", "tag_1"),
    ("tag_2", "tag_2"),
    ("tag_3", "tag_3"),
)


@router.post(
    "/sessions/{session_id}/reviewees/field-labels",
    response_class=RedirectResponse,
)
async def reviewees_save_field_labels(
    request: Request,
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save the three reviewee tag labels for this session.

    Identity columns (Name / Email_Identifier / Profile) retired
    2026-05-31 per upgrade-doc §3.7; form fields for those names
    are silently ignored if submitted.
    """
    form = await request.form()
    submitted = {
        param: str(form.get(param, "")) for param, _ in _REVIEWEE_SLOTS
    }
    # The labels service locks the session row (findings Bc4): wait for
    # it off the event loop.
    await run_in_threadpool(
        _save_field_labels,
        db,
        review_session=review_session,
        user=user,
        source_type="reviewee",
        slots=_REVIEWEE_SLOTS,
        submitted=submitted,
        correlation_id=request_correlation_id(),
    )
    # 19P.3 rung 4 — `?unlocked=1#roster-card`. This control lives INSIDE
    # the Unlock panel now, and a bare redirect closes the panel the
    # operator was working in: a Save does not close the card, the Lock
    # control does. The fragment lands on the card rather than the top of
    # the document.
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/reviewees"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/reviewees/bulk-delete")
def reviewees_bulk_delete(
    request: Request, reviewee_ids: list[int] = Form(default=[]),
    confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(require_reviewees_editable_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Delete the checkbox-selected rows (Segment 19I Item 2).

    Sibling of ``bulk-inactivate`` — same id list, same filter
    round-trip — with the Danger Zone's two gates in front of it,
    narrowed to the selection. The redirect carries the filters but
    **not** the ids: the rows are gone, so re-checking them is not a
    thing the page can do.
    """
    _require_editable(review_session)
    _require_delete_confirm(confirm)
    _require_selected_response_loss_ack(
        db,
        model=Reviewee,
        ids=reviewee_ids,
        ack=acknowledge_response_loss,
    )
    try:
        reviewees_service.delete_selected(
            db,
            review_session=review_session,
            reviewee_ids=reviewee_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/reviewees",
        [],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor([], noun="reviewee"),
    )
