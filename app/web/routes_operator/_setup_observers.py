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

from dataclasses import dataclass
from typing import Any


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
from app.db.models import Observer, ReviewSession, User
from app.db.session import get_db
from app.schemas.observer_cohort_rule import VALUE_OPERATORS
from app.services import csv_imports, participant_info
from app.services import observers as observers_service
from app.services import session_lifecycle as lifecycle
from app.services.observers import ObserverOperationError
from app.services.text import parse_id
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
)
from app.web.routes_operator._shared import (
    account_resolver,
    _setup_row_window,
    _redirect_keeping_selection,
    _row_action_anchor,
    _require_delete_confirm,
    _require_selected_response_loss_ack,
    _require_not_archived,
    _templates,
    directory_or_none,
    dismiss_held_upload,
    hold_for_ask,
    read_upload,
    release_hold,
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


#: `_render_observers_page`'s default for the row editor's rule: the edited
#: observer's stored one (none on `Add`). A sentinel rather than ``None``,
#: because ``None`` is a rule a caller can mean: an emptied builder.
_STORED_RULE: Any = object()


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
    edit_cohort_rule: dict[str, Any] | None = _STORED_RULE,
    rule_edit_ids: list[int] | None = None,
    selected_ids: set[int] | None = None,
    focus_id: int | None = None,
    issues: list | None = None,
    missing_confirm: bool = False,
    filename: str | None = None,
    held_upload: dict[str, str] | None = None,
    held_upload_lost: bool = False,
    confirm_replace_checked: bool = False,
    append_checked: bool = False,
    both_ticks: bool = False,
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
        rule_edit_ids = None
    # operator pages Item 4 — `Edit` on several selected rows edits their
    # rule alone. A single id is the row editor's job, not this mode's.
    rule_edit_ids = list(dict.fromkeys(rule_edit_ids or []))
    if edit_id is not None or add_mode or len(rule_edit_ids) < 2:
        rule_edit_ids = []

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
        locate_id=focus_id if focus_id is not None else (
            rule_edit_ids[0] if rule_edit_ids else None
        ),
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
    # operator pages Item 4 — the row editor's builder loads the observer's
    # stored rule. Resolved apart from `edit_values`: a rejected save
    # (a taken email, say) re-renders with the operator's values, and the
    # builder must not come back empty while the rule is still stored.
    # operator pages Item 4 — the several-row editor's rows and what it
    # loads; the view adapter owns the comparison (Codex on #2990).
    rule_edit = views.rule_edit_state(observers, rule_edit_ids)
    if rule_edit.ids and edit_cohort_rule is _STORED_RULE:
        edit_cohort_rule = rule_edit.rule
    if edit_cohort_rule is _STORED_RULE:
        edited = (
            next((o for o in all_observers if o.id == edit_id), None)
            if edit_id is not None else None
        )
        edit_cohort_rule = edited.cohort_rule if edited is not None else None
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
    col_readouts = views.observer_column_state(db, review_session).readouts

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
                f"/operator/sessions/{review_session.public_id}/observers?"
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
            "col_readouts": col_readouts,
            # participant info Item 5 — the own-entry card and the
            # `Observers see:` readout. This helper renders the GET and the
            # failed import alike, so the two cannot disagree.
            **views.observer_self_card_context(review_session, col_readouts),
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
            "directory_check": views.last_directory_check(db, review_session, "observers"),
            "upload_problems": views.upload_problems(
                "observers",
                issues,
                missing_confirm=missing_confirm,
                offers_append=True,
                both_ticks=both_ticks,
            ),
            "filename": filename,
            # Segment 19W: the file an ask holds, and a hold that lapsed.
            "held_upload": held_upload,
            "held_upload_lost": held_upload_lost,
            "confirm_replace_checked": confirm_replace_checked,
            # Segment 19Z: the append tick, re-ticked on an ask's render.
            "append_checked": append_checked,
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
            # `_upload_problems`, `_pager_cluster`,
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
            "edit_cohort_rule": edit_cohort_rule,
            "rule_edit_ids": rule_edit.ids,
            "rule_edit_last": rule_edit.last_id,
            "rule_edit_mixed": rule_edit.mixed,
            # The page's half-filled check reads the same list the
            # server's does.
            "cohort_value_ops": sorted(VALUE_OPERATORS),
            "cohort_match_tags": cohort_match_tags,
            "cohort_rule_views": {
                obs.id: {
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
    rule_id: list[int] = Query(default=[]),
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
        rule_edit_ids=rule_id,
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
    cohort_rule_field: list[str] = Form(default=[]),
    cohort_rule_op: list[str] = Form(default=[]),
    cohort_rule_operand_tag: list[str] = Form(default=[]),
    cohort_rule_operand_value: list[str] = Form(default=[]),
    cohort_combinator: str = Form(default="AND"),
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
    rule = _row_editor_rule(
        fields=cohort_rule_field,
        ops=cohort_rule_op,
        operand_tags=cohort_rule_operand_tag,
        operand_values=cohort_rule_operand_value,
        combinator=cohort_combinator,
    )
    try:
        if rule.error:
            raise ObserverOperationError("half_filled_rule", rule.error)
        created = observers_service.create_observer(
            db,
            review_session=review_session,
            email=email,
            display_name=display_name,
            tag_1=tag_1,
            status=status_value,
            cohort_rule=rule.payload,
            user=user,
            correlation_id=request_correlation_id(),
            resolve_account=account_resolver(request),
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
            edit_cohort_rule=rule.shown,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    # 19P.2 rung 1 — a create is the one action whose row a fragment
    # alone cannot reach: rows list by id, so the new row appends past
    # the end and, on a roster over one page, is not on the page the
    # form was submitted from. `focus` relocates the window to it and
    # the fragment then resolves.
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/observers",
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
    cohort_rule_field: list[str] = Form(default=[]),
    cohort_rule_op: list[str] = Form(default=[]),
    cohort_rule_operand_tag: list[str] = Form(default=[]),
    cohort_rule_operand_value: list[str] = Form(default=[]),
    cohort_combinator: str = Form(default="AND"),
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
    rule = _row_editor_rule(
        fields=cohort_rule_field,
        ops=cohort_rule_op,
        operand_tags=cohort_rule_operand_tag,
        operand_values=cohort_rule_operand_value,
        combinator=cohort_combinator,
    )
    try:
        if rule.error:
            raise ObserverOperationError("half_filled_rule", rule.error)
        observers_service.update_observer(
            db,
            observer=observer,
            email=email,
            display_name=display_name,
            tag_1=tag_1,
            status=status_value,
            cohort_rule=rule.payload,
            user=user,
            correlation_id=request_correlation_id(),
            resolve_account=account_resolver(request),
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
            edit_cohort_rule=rule.shown,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/observers",
        [observer_id],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor([observer_id], noun="observer"),
    )


@router.post("/sessions/{session_id}/observers/bulk-inactivate")
def observers_bulk_inactivate(
    request: Request, observer_ids: list[int] = Form(default=[]),
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
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(observer_ids, noun="observer"),
    )


@router.post("/sessions/{session_id}/observers/bulk-reactivate")
def observers_bulk_reactivate(
    request: Request, observer_ids: list[int] = Form(default=[]),
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
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(observer_ids, noun="observer"),
    )


@dataclass(frozen=True)
class _RowEditorRule:
    """The row editor's builder, read from its form fields."""

    #: What the service stores: ``None`` when every cell is blank.
    payload: dict[str, Any] | None
    #: The cells as posted, blank ones dropped, for a re-render.
    shown: dict[str, Any]
    #: Set when a cell is half-filled.
    error: str | None


def _row_editor_rule(
    *,
    fields: list[str],
    ops: list[str],
    operand_tags: list[str],
    operand_values: list[str],
    combinator: str,
) -> _RowEditorRule:
    """Read the row editor's cohort builder (operator pages Item 4).

    A cell with no field and nothing typed is blank and dropped, so an
    untouched builder saves no rule. A cell with a field but a typed
    operator and no value, or a typed value but no field, is half-filled:
    the page disables Save on one, and this refuses it too.
    """
    n = len(ops)
    pad = lambda xs: list(xs) + [""] * (n - len(xs))  # noqa: E731
    fields, operand_tags, operand_values = (
        pad(fields), pad(operand_tags), pad(operand_values)
    )
    cells: list[dict[str, str]] = []
    half = False
    for field, op, tag, value in zip(
        fields, ops, operand_tags, operand_values, strict=False
    ):
        typed = op in VALUE_OPERATORS
        if not field and not (typed and value.strip()):
            continue
        if not field or (typed and not value.strip()):
            half = True
        cells.append(
            {"field": field, "op": op, "operand_tag": tag, "operand_value": value}
        )
    shown = {"combinator": (combinator or "AND").strip().upper(), "rules": cells}
    return _RowEditorRule(
        payload=shown if cells else None,
        shown=shown,
        error=(
            "Finish or clear each rule cell: every cell needs a field "
            "and an operand." if half else None
        ),
    )


@router.post(
    "/sessions/{session_id}/observers/cohort-rule",
    response_class=HTMLResponse,
    response_model=None,
)
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
) -> HTMLResponse | RedirectResponse:
    """POST handler for the Cohort match rule editor's Save
    button. Applies the editor's current rule to every observer
    in ``observer_ids`` (the hidden inputs the several-row editor
    carries, operator pages Item 4); rejects an empty selection with a
    400.

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
        parsed
        for parsed in (parse_id(v) for v in form.getlist("observer_ids"))
        if parsed is not None
    ]
    # operator pages Item 4 rung 4 — the builder now opens from `Edit` on
    # several rows (the selection expander lost it), and reads as the row
    # editor's does: blank cells dropped, all blank clears the rule, a
    # half-filled cell refused with the editor re-rendered.
    rule = _row_editor_rule(
        fields=[str(v) for v in form.getlist("cohort_rule_field")],
        ops=[str(v) for v in form.getlist("cohort_rule_op")],
        operand_tags=[str(v) for v in form.getlist("cohort_rule_operand_tag")],
        operand_values=[
            str(v) for v in form.getlist("cohort_rule_operand_value")
        ],
        combinator=str(form.get("cohort_combinator") or "AND"),
    )
    try:
        if rule.error:
            raise ObserverOperationError("half_filled_rule", rule.error)
        # Locks the session row (findings Bc4): off the event loop.
        await run_in_threadpool(
            observers_service.set_cohort_rule,
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            payload=rule.payload,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        if exc.code in {"empty_selection", "not_in_session"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
            ) from exc
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            status_filter=filter_status,
            search=filter_q,
            offset=filter_offset,
            # One row's rule is edited in its row editor; only several
            # open the rule alone.
            edit_id=observer_ids[0] if len(observer_ids) == 1 else None,
            rule_edit_ids=observer_ids,
            edit_error=exc.message,
            edit_cohort_rule=rule.shown,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_row_action_anchor(observer_ids, noun="observer"),
    )


@router.post(
    "/sessions/{session_id}/observers/self-fields",
    response_class=RedirectResponse,
)
async def observers_save_self_fields(
    request: Request,
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save what observers see of their own entry (participant info
    Item 5), as the Reviewers and Reviewees cards save theirs: the ticked
    chips plus ``keep``, the selected keys the card offered no chip for.
    Refused only when archived, the Observers roster's gate: checked
    here as every sibling route does, and again under the row lock in
    the service."""
    _require_not_archived(review_session)
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
            participant="observer",
            keys=keys,
            correlation_id=request_correlation_id(),
        )
    except participant_info.SelfFieldsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/observers"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/observers/delete-all")
def observers_delete_all(
    request: Request, confirm: str | None = Form(default=None),
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
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/observers"
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
    # Optional since segment 19W: with an ask's file held, the card
    # submits with no file chosen and ``held_token`` names the hold.
    file: UploadFile | None = File(default=None),
    held_token: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    # Segment 19Z: the card's append tick, beside the replace tick.
    append: str | None = Form(default=None),
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
    upload = await read_upload(
        db,
        file=file,
        held_token=held_token,
        user=user,
        review_session=review_session,
        slot="observers",
    )
    result = csv_imports.parse_observer_csv(upload.content)
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
    appending = append == "true"

    def render(
        status_code: int = status.HTTP_200_OK,
        *,
        missing_confirm: bool = False,
        both_ticks: bool = False,
        held_upload: dict[str, str] | None = None,
    ) -> HTMLResponse:
        # `panel_open=True`: this path re-renders the page in place and
        # returns 400 WITH it, so `?unlocked=1` cannot reach it. Left
        # False, a failed import would answer with a collapsed panel and
        # the operator would see no errors at all —
        # `_upload_problems.html` renders the file's problems inside the
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
            missing_confirm=missing_confirm,
            both_ticks=both_ticks,
            filename=upload.filename,
            held_upload=held_upload,
            held_upload_lost=upload.lost,
            # Neither tick comes back on the both-ticks ask (19Z).
            confirm_replace_checked=(
                held_upload is not None and confirm_replace == "true" and not both_ticks
            ),
            append_checked=held_upload is not None and appending and not both_ticks,
            http_status=status_code,
        )

    def ask() -> dict[str, str] | None:
        return hold_for_ask(
            db, upload=upload, user=user, review_session=review_session,
            slot="observers",
        )

    if result.is_blocked:
        release_hold(
            db, token=upload.token, user=user, review_session=review_session
        )
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and appending and confirm_replace == "true":
        return render(
            status_code=status.HTTP_400_BAD_REQUEST, both_ticks=True, held_upload=ask()
        )

    if existing > 0 and not appending and confirm_replace != "true":
        # An ask: hold the file so the tick is all the answer needs
        # (segment 19W).
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            missing_confirm=True,
            held_upload=ask(),
        )

    # No response-loss gate here (Segment 19I Item 5), for the same
    # reason `delete-all` lost its in Item 3: nothing references an
    # observer, so replacing the roster destroys no assignment and no
    # response. The requirement asked the operator to accept a loss
    # that cannot occur, and 400d when they could not — the `if
    # existing > 0:` block it guarded went with it.

    # Segment 21F: each address resolved through the directory first.
    directory_check = await run_in_threadpool(
        csv_imports.directory_check,
        directory_or_none(request),
        [row.email for row in result.rows],
    )
    # Segment 19Z: an append refuses a row already on the roster, or on
    # a directory account already there; the save checks again under
    # the session lock.
    if appending:
        result.issues.extend(
            csv_imports.append_conflicts(
                db,
                session_id=review_session.id,
                kind="observers",
                rows=result.rows,
                directory=directory_check,
            )
        )
        if result.is_blocked:
            release_hold(
                db, token=upload.token, user=user, review_session=review_session
            )
            return render(status_code=status.HTTP_400_BAD_REQUEST)
    # The service locks the session row (findings Bc4): wait for it off
    # the event loop.
    try:
        await run_in_threadpool(
            csv_imports.save_observers,
            db,
            session=review_session,
            user=user,
            rows=result.rows,
            filename=upload.filename or "",
            correlation_id=request_correlation_id(),
            directory=directory_check,
            append=appending,
        )
    except csv_imports.AppendConflict as refused:
        db.rollback()
        result.issues.extend(refused.issues)
        release_hold(db, token=upload.token, user=user, review_session=review_session)
        return render(status_code=status.HTTP_400_BAD_REQUEST)
    release_hold(db, token=upload.token, user=user, review_session=review_session)
    # Open, like the failure path above and like `delete-all`: one rule
    # about the panel rather than three about its controls. A Save does
    # not close this card; the Lock button does.
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/observers"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/observers/import/dismiss")
def observers_import_dismiss(
    request: Request, held_token: str | None = Form(default=None),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """The upload card's Dismiss while an ask holds its file: end the
    hold and return to the card (segment 19W)."""
    return dismiss_held_upload(request,
        db, held_token=held_token, user=user,
        review_session=review_session, page="observers",
    )


@router.post("/sessions/{session_id}/observers/bulk-delete")
def observers_bulk_delete(
    request: Request, observer_ids: list[int] = Form(default=[]),
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
    return _redirect_keeping_selection(request,
        f"/operator/sessions/{review_session.public_id}/observers",
        [],
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        # `[]` by design: the rows this acted on no longer exist, so the
        # helper answers with the table card. That is also why the page's
        # fallback script never sees a delete — it guards on a
        # `#observer-row-` hash, and this is not one.
        anchor=_row_action_anchor([], noun="observer"),
    )
