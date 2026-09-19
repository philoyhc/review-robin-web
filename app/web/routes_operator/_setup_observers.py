"""Observers Setup page — the list / edit / add view, its CSV
import, bulk status actions, and delete-all.

Lights up the third participant audience (the observer roster).
Mirrors the Reviewers / Reviewees Setup-page shape but trimmed
for the simpler observer model: a single ``tag_1`` column,
``email`` as the required identity, and an optional human-
facing ``display_name``.

Route-gated on ``session.observers_enabled``
(``require_observers_enabled_session``) — the page 404s until
the operator opts in via the User interface settings card on
Session Edit Details.
"""

from __future__ import annotations

from typing import Any

from starlette.datastructures import FormData

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
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession, User
from app.db.session import get_db
from app.services import csv_imports
from app.services import observers as observers_service
from app.services import session_lifecycle as lifecycle
from app.services.observers import ObserverOperationError
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
)
from app.web.routes_operator._shared import (
    _setup_row_window,
    _redirect_keeping_selection,
    _row_action_anchor,
    _require_delete_confirm,
    _require_selected_response_loss_ack,
    _require_not_archived,
    _templates,
    require_observers_enabled_session,
)

router = APIRouter()


def _list_observers(db: Session, session_id: int) -> list[Observer]:
    return list(
        db.execute(
            select(Observer)
            .where(Observer.session_id == session_id)
            .order_by(Observer.id)
        ).scalars()
    )


def _require_observer_in_session(
    db: Session, review_session: ReviewSession, observer_id: int
) -> Observer:
    observer = db.execute(
        select(Observer).where(
            Observer.id == observer_id,
            Observer.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if observer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return observer


def _render_observers_page(
    *,
    request: Request,
    db: Session,
    user: User,
    review_session: ReviewSession,
    status_filter: str = "all",
    search: str = "",
    offset: int = 0,
    edit_id: int | None = None,
    add_mode: bool = False,
    panel_open: bool = False,
    edit_values: dict[str, str] | None = None,
    edit_error: str | None = None,
    selected_ids: set[int] | None = None,
    focus_id: int | None = None,
    issues: list | None = None,
    filename: str | None = None,
    http_status: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Render the Observers Setup page.

    Shared by the GET route and the create / update error-render
    paths. ``edit_id`` / ``add_mode`` drive the server-rendered
    edit state; ``edit_values`` / ``edit_error`` carry an
    operator's rejected submission back into the edit row."""
    is_ready = lifecycle.is_ready(review_session)
    # The editor renders wherever `create` / `update` accept. Was
    # `if is_ready`, from 19I Item 3, when both routes took
    # `_require_editable` and `ready` could not save — suppressing the
    # editor there stopped the page offering a form the server would
    # refuse.
    #
    # 19P.2 rung 2 relaxed those routes and the buttons above them, and
    # left this behind: `Add` and `Edit` rendered on `ready` and
    # produced no editor, which is the dead control the rung exists to
    # remove, and a rejected save came back with the operator's typed
    # values dropped and the error banner — scoped to `edit_mode` —
    # unrendered. `archived` is the predicate now, the same one the
    # buttons read, so the two cannot disagree again.
    if lifecycle.is_archived(review_session):
        edit_id = None
        add_mode = False

    all_observers = _list_observers(db, review_session.id)
    filtered = views.filter_observers_rows(
        all_observers, status=status_filter, search=search
    )
    is_filtered = status_filter != "all" or bool(search.strip())
    # Segment 19J.5 rung 2 — the cap became a page size. The shared
    # helper cuts the window, clamps a stale ``offset`` onto a real
    # boundary, and lands the operator on the page that holds the row
    # they are editing instead of prepending it to whatever page they
    # happened to be on.
    window = _setup_row_window(
        filtered=filtered,
        all_rows=all_observers,
        is_filtered=is_filtered,
        offset=offset,
        edit_id=edit_id,
        # 19P.2 rung 1 — a create appends past the end of the list, so on
        # a roster over one page the new row is not on the page the form
        # was submitted from and the redirect's fragment would name a row
        # this response never renders. `locate_id` moves the window to it.
        locate_id=focus_id,
    )
    observers = window.rows
    offset = window.offset
    edit_id = window.edit_id
    displayed_row_count = len(observers)

    if edit_values is None and edit_id is not None:
        edited = next(
            (o for o in observers if o.id == edit_id), None
        )
        if edited is not None:
            edit_values = {
                "email": edited.email,
                "display_name": edited.display_name or "",
                "tag_1": edited.tag_1 or "",
                "status": edited.status,
            }
    if edit_values is None and add_mode:
        edit_values = {
            "email": "",
            "display_name": "",
            "tag_1": "",
            "status": "active",
        }

    existing_count = csv_imports.existing_observer_count(
        db, review_session.id
    )

    cohort_match_tags = views.new_model_usable_tags(db, review_session)

    return _templates.TemplateResponse(
        request,
        "operator/session_observers.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "observers": observers,
            "selected_ids": selected_ids or set(),
            "total_row_count": len(all_observers),
            # Always ``False`` (Segment 19I Item 2). Deleting a
            # observer destroys no response — nothing references
            # one, measured from the model graph at PR 2 — so the
            # strip must not offer an acknowledgement for a loss
            # that cannot happen. The route's gate reaches the
            # same answer on its own via ``cascade_counts``; this
            # keeps the page from saying otherwise.
            # Always ``False`` / ``0``: deleting a observer reaches
            # no assignment and no response (Segment 19I Item 2,
            # measured from the model graph).
            "delete_discards_assignments": False,
            "roster_response_count": 0,
            "delete_discards_responses": False,
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
                f"/operator/sessions/{review_session.id}/observers?"
            ),
            # The fragment the range links land on (19J.8): the
            # table's card, so a page turn arrives showing the card's
            # top edge, the column chips, the page links and the new
            # rows — in that order down the screen. Passed rather than
            # derived: a macro guessing the id would land silently at
            # the top of the document the first time someone renamed
            # it, which is a failure with no error.
            # 19P.2 rung 6 — the roster index row. Informational in
            # every lifecycle state, which is why the card carrying it
            # renders even where the Unlock panel cannot.
            "col_readouts": views.observer_column_state(
                db, review_session
            ).readouts,
            # 19P.2 rung 6 — whether the Unlock panel ships open.
            # Server state, not a second source of truth for the JS
            # toggle: the toggle still owns every click, this only
            # decides what the page ARRIVES as. Both the controls the
            # panel now holds answer with a redirect, and a panel that
            # always shipped collapsed would shut itself on every one —
            # the Lock control is what closes it, not a Save.
            "panel_open": panel_open,
            "pager_anchor": "observers-table-card",
            # The add row's own id. An `Add` from mid-page is a
            # navigation like any other and lands at the top of the
            # document without a fragment to name; the row IS the
            # editor's second home on this page, so it is what the
            # fragment names.
            "row_editor_anchor": "observers-row-editor",
            # The pager offset the row-action forms post back, so a
            # mid-table action returns to the page it was taken on.
            "current_offset": offset,
            # Segment 19J.5 rung 2 — the sentence is the filter's now,
            # not the table's: where the pager renders, the ranges
            # already say where the operator is.
            "preview_count_line": views.preview_count_line(
                shown=displayed_row_count,
                pool=len(filtered),
                noun="observers",
                is_filtered=is_filtered,
            ),
            "filter_status": status_filter,
            "filter_search": search,
            "filter_status_options": views.OBSERVERS_STATUS_OPTIONS,
            "filter_search_options": views.observers_search_options(
                all_observers
            ),
            "existing_count": existing_count,
            "issues": issues or [],
            "filename": filename,
            "is_ready": is_ready,
            # Segment 19I Item 3 — the gate on the selection surface.
            # ``is_ready`` is only ``status == "ready"``, so gating on it
            # left `expired` and `archived` sessions rendering checkboxes
            # and a live Delete while every mutation 409d. Page and route
            # agree by construction rather than by two lists kept in step.
            #
            # 19P.2 rung 2 — that pairing now runs through
            # ``is_archived`` on this page, not ``is_editable``: every
            # mutating route relaxed to ``_require_not_archived``, so
            # ``is_editable`` no longer describes any route's gate here.
            # It stays in the context as DEAD data, and is named as
            # such rather than quietly left: the lock card takes the
            # `lock_when` branch on this page, and `is_editable` is
            # absent from every partial this template includes
            # (`session_top_nav`, `session_setup_status_row`,
            # `validation_results`, `_pager_cluster`,
            # `_preview_count_line`). A cold read caught the first
            # version of this comment claiming two readers that do not
            # exist. Kept for now because rungs 3-6 still move this
            # page's surface around; it goes at the close if nothing
            # has picked it up.
            "is_editable": lifecycle.is_editable(review_session),
            "is_archived": lifecycle.is_archived(review_session),
            "edit_id": edit_id,
            "add_mode": add_mode,
            "edit_values": edit_values,
            "edit_error": edit_error,
            "cohort_match_tags": cohort_match_tags,
            "cohort_rule_views": {
                obs.id: {
                    "signature": views.cohort_rule_signature(obs.cohort_rule),
                    "summary": views.cohort_rule_summary(
                        obs.cohort_rule, tag_labels=cohort_match_tags
                    ),
                }
                for obs in observers
            },
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Observers"
            ),
        },
        status_code=http_status,
    )


@router.get(
    "/sessions/{session_id}/observers", response_class=HTMLResponse
)
def observers_page(
    request: Request,
    status_filter: str = Query(default="all", alias="status"),
    q: str = "",
    offset: int = 0,
    focus: int | None = None,
    edit_id: int | None = None,
    add: int = 0,
    unlocked: int = 0,
    selected: list[int] = Query(default=[]),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_observers_page(
        request=request,
        db=db,
        user=user,
        review_session=review_session,
        status_filter=status_filter,
        search=q,
        offset=offset,
        edit_id=edit_id,
        add_mode=bool(add),
        panel_open=bool(unlocked),
        selected_ids=set(selected),
        focus_id=focus,
    )


@router.post(
    "/sessions/{session_id}/observers/create",
    response_class=HTMLResponse,
    response_model=None,
)
def observers_create(
    request: Request,
    email: str = Form(default=""),
    display_name: str = Form(default=""),
    tag_1: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_not_archived(review_session)
    try:
        created = observers_service.create_observer(
            db,
            review_session=review_session,
            email=email,
            display_name=display_name,
            tag_1=tag_1,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            add_mode=True,
            edit_values={
                "email": email,
                "display_name": display_name,
                "tag_1": tag_1,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    # 19P.2 rung 1 — a create is the one action whose row a fragment
    # alone cannot reach: rows list by id, so the new row appends past
    # the end and, on a roster over one page, is not on the page the
    # form was submitted from. `focus` relocates the window to it and
    # the fragment then resolves.
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        [],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        extra_params=[("focus", created.id)],
        anchor=_row_action_anchor([created.id], noun="observer"),
    )


@router.post(
    "/sessions/{session_id}/observers/{observer_id}/update",
    response_class=HTMLResponse,
    response_model=None,
)
def observers_update(
    request: Request,
    observer_id: int,
    email: str = Form(default=""),
    display_name: str = Form(default=""),
    tag_1: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_not_archived(review_session)
    observer = _require_observer_in_session(db, review_session, observer_id)
    try:
        observers_service.update_observer(
            db,
            observer=observer,
            email=email,
            display_name=display_name,
            tag_1=tag_1,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            edit_id=observer_id,
            edit_values={
                "email": email,
                "display_name": display_name,
                "tag_1": tag_1,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        [observer_id],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor([observer_id], noun="observer"),
    )


@router.post("/sessions/{session_id}/observers/bulk-inactivate")
def observers_bulk_inactivate(
    observer_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_not_archived(review_session)
    try:
        observers_service.bulk_inactivate(
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(observer_ids, noun="observer"),
    )


@router.post("/sessions/{session_id}/observers/bulk-reactivate")
def observers_bulk_reactivate(
    observer_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_not_archived(review_session)
    try:
        observers_service.bulk_reactivate(
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(observer_ids, noun="observer"),
    )


def _parse_cohort_rule_form(form: FormData) -> dict[str, Any]:
    """Decode the Cohort match rule editor's submission into the
    ``CohortRuleSet`` dict shape. Mirrors Band 1's
    ``_form_rules`` (parallel arrays + blank-field guard) so a
    cell whose ``field`` came in empty (e.g. a default cell the
    operator never touched, or the browser-omits-empty-select
    edge case) drops silently rather than tripping the schema
    validator.

    All four sibling arrays are padded up to ``len(ops)`` with
    empty strings — never truncated — so a missing trailing
    operand never silently drops an otherwise valid rule cell.
    """
    fields = [str(v) for v in form.getlist("cohort_rule_field")]
    ops = [str(v) for v in form.getlist("cohort_rule_op")]
    operand_tags = [
        str(v) for v in form.getlist("cohort_rule_operand_tag")
    ]
    operand_values = [
        str(v) for v in form.getlist("cohort_rule_operand_value")
    ]

    n = len(ops)
    while len(fields) < n:
        fields.append("")
    while len(operand_tags) < n:
        operand_tags.append("")
    while len(operand_values) < n:
        operand_values.append("")

    rules: list[dict[str, str]] = []
    for i in range(n):
        if not fields[i]:
            continue
        rules.append(
            {
                "field": fields[i],
                "op": ops[i],
                "operand_tag": operand_tags[i],
                "operand_value": operand_values[i],
            }
        )

    combinator = str(form.get("cohort_combinator") or "AND").strip().upper()
    # Don't silently coerce unknown values to AND — let
    # ``CohortRuleSet.model_validate`` reject so a JS bug that
    # desyncs the hidden combinator mirror surfaces as a 400
    # rather than a silent AND save.

    return {"combinator": combinator, "rules": rules}


@router.post("/sessions/{session_id}/observers/cohort-rule")
async def observers_cohort_rule_save(
    request: Request,
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """POST handler for the Cohort match rule editor's Save
    button. Applies the editor's current rule to every observer
    in ``observer_ids`` (sourced from the bulk-form's row
    checkboxes); rejects an empty selection with a 400.

    Lifecycle gate is ``_require_not_archived``. This route has
    used it since it was written, on the ground that cohort rules
    govern which parts of response data observers see, not the
    response data or roster shape, so editing them mid-session
    (ready / expired) is legitimate.

    **19P.2 rung 2 extended that ground to the roster itself** and
    the other six mutators joined it, so this is no longer the
    looser of two gates on the page — it is the page's gate. An
    observer row is a view grant either way: observers never
    appear in assignments, never produce responses, and no
    readiness rule references them. Only archived is a hard stop.
    """
    _require_not_archived(review_session)
    form = await request.form()
    observer_ids = [
        int(v)
        for v in form.getlist("observer_ids")
        if str(v).isdigit()
    ]
    payload = _parse_cohort_rule_form(form)
    try:
        observers_service.set_cohort_rule(
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            payload=payload,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(observer_ids, noun="observer"),
    )


@router.post("/sessions/{session_id}/observers/delete-all")
def observers_delete_all(
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_not_archived(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    # No response-loss gate (Segment 19I Item 3). Nothing references an
    # observer, so deleting the roster destroys no assignment and no
    # response — measured from the model graph at Item 2. Requiring an
    # acknowledgement here asked the operator to accept a loss that
    # cannot occur, and returned 400 when they could not.
    csv_imports.delete_all_observers(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    # `?unlocked=1#roster-card` — 19P.2 rung 6. This control lives
    # INSIDE the Unlock panel now, and a bare redirect closes the panel
    # the operator was working in. The Danger Zone itself is gone from
    # the response (the roster is empty and the card is gated on rows),
    # but Upload is not, and uploading a replacement is the likely next
    # move.
    #
    # Called out in the plan's rung-6 entry because 19P.1 rung 3b
    # shipped exactly this omission on Reviewers and had to fix it
    # after the fact: a control inside the panel must not close the
    # panel it was used from. Matching the status code is not matching
    # the contract.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/observers"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/observers/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def observers_import_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Observers CSV import. Mirrors ``_handle_import`` for the
    reviewer / reviewee path, cross-table identity check included.

    **It skipped that check until 19Q Item 7**, and said why: *a person
    can be both an observer and a reviewer / reviewee by design*. True,
    and it never argued for the exclusion — the check has always allowed
    one person to hold two roles, and blocks only holding them under two
    different **names**. Exactly as much is true of reviewer↔reviewee,
    which it did cover. So the premise was sound and the conclusion did
    not follow from it (author's ruling, 2026-09-19).
    """
    _require_not_archived(review_session)
    content = await file.read()
    result = csv_imports.parse_observer_csv(content)
    if not result.is_blocked:
        result.issues.extend(
            csv_imports.check_cross_table_identity(
                db,
                session_id=review_session.id,
                rows=result.rows,
                kind="observers",
            )
        )
    existing = csv_imports.existing_observer_count(db, review_session.id)

    def render(status_code: int = status.HTTP_200_OK) -> HTMLResponse:
        # `panel_open=True`: this path re-renders the page in place and
        # returns 400 WITH it, so `?unlocked=1` cannot reach it. Left
        # False, a failed import would answer with a collapsed panel and
        # the operator would see no errors at all —
        # `validation_results.html` renders the issue list inside the
        # card the panel now holds.
        #
        # The suite cannot catch a regression here. With no JS runtime
        # `hidden` is an inert attribute, so the issues are in the
        # markup and every assertion on them passes either way; Chromium
        # is what proves it. Same shape that bit Reviewers at 19P.1
        # rung 3c.
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            panel_open=True,
            issues=result.issues,
            filename=file.filename,
            http_status=status_code,
        )

    if result.is_blocked:
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and confirm_replace != "true":
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    # No response-loss gate here (Segment 19I Item 5), for the same
    # reason `delete-all` lost its in Item 3: nothing references an
    # observer, so replacing the roster destroys no assignment and no
    # response. The requirement asked the operator to accept a loss
    # that cannot occur, and 400d when they could not — the `if
    # existing > 0:` block it guarded went with it.

    csv_imports.save_observers(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    # Open, like the failure path above and like `delete-all`: one rule
    # about the panel rather than three about its controls. A Save does
    # not close this card; the Lock button does.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/observers"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/observers/bulk-delete")
def observers_bulk_delete(
    observer_ids: list[int] = Form(default=[]),
    confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    filter_offset: int = Form(default=0),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
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
    _require_not_archived(review_session)
    _require_delete_confirm(confirm)
    _require_selected_response_loss_ack(
        db,
        model=Observer,
        ids=observer_ids,
        ack=acknowledge_response_loss,
    )
    try:
        observers_service.delete_selected(
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        [],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        # `[]` by design: the rows this acted on no longer exist, so the
        # helper answers with the table card. That is also why the page's
        # fallback script never sees a delete — it guards on a
        # `#observer-row-` hash, and this is not one.
        anchor=_row_action_anchor([], noun="observer"),
    )
