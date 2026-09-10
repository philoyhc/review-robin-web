"""Assignments hub: index page + manual import + delete-all. Slice 4
of the major refactor.

Note: The Rule Builder routes (``/assignments/rule-based-editor/...``
and ``/assignments/rule-based/generate``) live with the Rule Builder
slice (PR 8), not here, even though they share the URL parent.

Source ranges in pre-refactor ``routes_operator.py``:
1261-1342, 2015-2120, 2350-2380.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import (
    assignments,
    csv_imports,
    relationships as relationships_service,
    session_lifecycle as lifecycle,
)
from app.services._queries import tag_slot_presence
from app.services.instruments import _instrument_label
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _require_editable,
    _require_response_loss_ack,
    _templates,
)


router = APIRouter()


@router.get("/sessions/{session_id}/assignments", response_class=HTMLResponse)
def assignments_hub(
    request: Request,
    needs_confirm: int | None = Query(default=None),
    validated: bool = Query(default=False),
    super_status: str | None = Query(default=None),
    super_button: str | None = Query(default=None),
    super_step: str | None = Query(default=None),
    super_error: str | None = Query(default=None),
    prepare_confirm: str | None = Query(default=None),
    q: str = Query(default=""),
    search_by: str = Query(default="all"),
    # `filter_status` rather than `status`: the module-level
    # `status` import (`status.HTTP_200_OK`) is in scope here, and a
    # parameter of that name shadows it. The alias keeps the URL
    # parameter `?status=`.
    filter_status: str = Query(default="all", alias="status"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # ``?validated=1`` is the workflow-card Validate Setup entry path.
    # ``build_workflow_card_context`` runs validation live and
    # promotes ``draft → validated`` inline when the report is
    # clean; the resulting validation_summary + per-issue list
    # flows through to the partial via the same builder.
    return _render_assignments_hub(
        request,
        db,
        review_session,
        user,
        missing_confirm=needs_confirm == 1,
        validated_just_ran=validated,
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
        search=q,
        search_by=search_by,
        filter_status=filter_status,
    )


_ASSIGNMENT_SORT_KEYS = {
    "reviewer",
    "reviewer_tag_1",
    "reviewer_tag_2",
    "reviewer_tag_3",
    "reviewee",
    "reviewee_tag_1",
    "reviewee_tag_2",
    "reviewee_tag_3",
    "pair_tag_1",
    "pair_tag_2",
    "pair_tag_3",
    "include",
    "instrument",
}


_SEARCH_BY_VALUES = {"all", "reviewer", "reviewee"}
# Segment 19I Item 9 — the `Assignment.include` filter. "all" and
# anything unrecognised fall through to everything, as the roster
# pages do.
_STATUS_VALUES = {key for key, _ in views.ASSIGNMENTS_STATUS_OPTIONS}


def _assignments_url(
    session_id: int,
    filter_q: str = "",
    search_by: str = "all",
    status: str = "all",
) -> str:
    """The Assignments-page URL, carrying the active search term /
    dimension / status so a bulk action redirects back to the same
    filtered view."""
    url = f"/operator/sessions/{session_id}/assignments"
    params: dict[str, str] = {}
    if filter_q:
        params["q"] = filter_q
    if search_by in _SEARCH_BY_VALUES and search_by != "all":
        params["search_by"] = search_by
    if status in _STATUS_VALUES:
        params["status"] = status
    if params:
        url += "?" + urlencode(params)
    return url


def _render_assignments_hub(
    request: Request,
    db: Session,
    review_session: ReviewSession,
    user: User,
    *,
    issues: list | None = None,
    missing_confirm: bool = False,
    is_blocked: bool = False,
    validated_just_ran: bool = False,
    super_failure: dict[str, str] | None = None,
    prepare_confirm: str | None = None,
    search: str = "",
    search_by: str = "all",
    # `filter_status`, not `status`: the module-level `status` import
    # (`status.HTTP_200_OK`, used below) is in scope here and a
    # parameter of that name shadows it — caught by an
    # `AttributeError: 'str' object has no attribute 'HTTP_200_OK'`
    # the first time this rendered.
    filter_status: str = "all",
) -> HTMLResponse:
    q = search.strip()
    if search_by not in _SEARCH_BY_VALUES:
        search_by = "all"
    if filter_status not in _STATUS_VALUES:
        filter_status = "all"
    # Segment 19I Item 9 — the typeahead's labels, and the handle a
    # picked one resolves to. Both sides' rosters are loaded here; the
    # page carried only counts before. Detection runs against the
    # **uncapped** label sets, the rendered list is capped.
    roster_reviewers = assignments.list_reviewers(db, review_session.id)
    roster_reviewees = assignments.list_reviewees(db, review_session.id)
    search_options = views.assignments_search_options(
        roster_reviewers, roster_reviewees
    )
    picked_reviewer, picked_reviewee = views.assignments_picked_handles(
        q, roster_reviewers, roster_reviewees
    )
    assignment_count = assignments.existing_count(db, review_session.id)
    if q or filter_status in _STATUS_VALUES:
        matching_count = assignments.count_pairs(
            db,
            review_session.id,
            search=q,
            search_by=search_by,
            status=filter_status,
            picked_reviewer_handle=picked_reviewer,
            picked_reviewee_handle=picked_reviewee,
        )
        pair_sample = (
            assignments.list_pairs(
                db,
                review_session.id,
                search=q,
                search_by=search_by,
                status=filter_status,
                picked_reviewer_handle=picked_reviewer,
                picked_reviewee_handle=picked_reviewee,
            )
            if matching_count
            else []
        )
    else:
        matching_count = assignment_count
        pair_sample = (
            assignments.list_pairs(db, review_session.id)
            if assignment_count
            else []
        )
    # Pair-context lookup is built up-front so the cookie-backed
    # sort (Segment 13B Part 2 PR 8) can resolve ``pair_tag_*``
    # keys without a second pass through the relationships table.
    pair_context_lookup = (
        relationships_service.pair_context_lookup(db, review_session.id)
        if assignment_count
        else {}
    )

    def _assignment_sort_value(assignment, key: str):
        if key == "reviewer":
            return assignment.reviewer.name if assignment.reviewer else None
        if key == "reviewee":
            return assignment.reviewee.name if assignment.reviewee else None
        if key.startswith("reviewer_tag_"):
            slot = key.rsplit("_", 1)[-1]
            return getattr(assignment.reviewer, f"tag_{slot}", None)
        if key.startswith("reviewee_tag_"):
            slot = key.rsplit("_", 1)[-1]
            return getattr(assignment.reviewee, f"tag_{slot}", None)
        if key.startswith("pair_tag_"):
            rel = pair_context_lookup.get(
                (assignment.reviewer_id, assignment.reviewee_id)
            )
            if rel is None or getattr(rel, "status", None) != "active":
                return None
            slot = key.rsplit("_", 1)[-1]
            return getattr(rel, f"tag_{slot}", None)
        if key == "include":
            # Render-text parity: assignment.include True → "yes",
            # False → "no". Sort lexically so "no" < "yes" (asc =
            # excluded first).
            return "yes" if assignment.include else "no"
        if key == "instrument":
            inst = assignment.instrument
            if inst is None:
                return None
            return _instrument_label(inst)
        return None

    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=f"rrw-sort-assignments-{review_session.id}",
        valid_keys=_ASSIGNMENT_SORT_KEYS,
    )
    pair_sample = views.apply_cookie_sort(
        pair_sample,
        sort_spec,
        value_resolver=_assignment_sort_value,
    )
    status_code = (
        status.HTTP_400_BAD_REQUEST if (missing_confirm or is_blocked) else status.HTTP_200_OK
    )

    # Workflow card context — shared builder owns the lifecycle
    # booleans, state predicates, validation summary + per-issue
    # list, setup checklist, invitation flags, super-button failure
    # banner state, and the ``return_to`` slug. Page-specific
    # context (reviewer / reviewee counts, pair sample, etc.) is
    # computed separately below and merged into the template dict.
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="assignments",
        validated_just_ran=validated_just_ran,
        super_failure=super_failure,
        prepare_confirm=prepare_confirm,
        user=user,
        correlation_id=request_correlation_id(),
    )

    return _templates.TemplateResponse(
        request,
        "operator/session_assignments.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "assignment_count": assignment_count,
            "reviewer_count": csv_imports.existing_reviewer_count(
                db, review_session.id
            ),
            "reviewee_count": csv_imports.existing_reviewee_count(
                db, review_session.id
            ),
            "pair_sample": pair_sample,
            # 19I Item 12 rung 2 — nine chip flags, answered over the
            # session's rosters rather than over a sample of assignment
            # rows. The sample this replaces was deliberately unfiltered
            # (Item 9) but still carried ``list_pairs``' default
            # ``limit=PAIR_PREVIEW_LIMIT``, so a tag populated only past
            # row 200 struck its own chip out. It also cost a second
            # 200-row fetch per filtered render, which these nine
            # indexed ``LIMIT 1``s replace.
            #
            # ``active_only`` on the pair-context group matches the rule
            # engine: only active relationships contribute predicate
            # values. The Relationships Setup page counts every row, and
            # the two answers differ on purpose.
            "col_data": (
                views.chip_slots(
                    tag_slot_presence(
                        db, session_id=review_session.id, model=Reviewer
                    ),
                    prefix="rt",
                )
                | views.chip_slots(
                    tag_slot_presence(
                        db, session_id=review_session.id, model=Reviewee
                    ),
                    prefix="et",
                )
                | views.chip_slots(
                    tag_slot_presence(
                        db,
                        session_id=review_session.id,
                        model=Relationship,
                        active_only=True,
                    ),
                    prefix="p",
                )
            ),
            # Segment 19I Item 10 — the page's three separate
            # notices (this filter count, a `Showing first N of M
            # unique pairs.` line, and a `…and X more not shown.`
            # line below the table) collapse into the one
            # sentence the seven table pages share.
            "preview_count_line": views.preview_count_line(
                shown=len(pair_sample),
                matching=matching_count,
                total=assignment_count,
                noun="assignments",
            ),
            "filter_q": q,
            "filter_search_by": search_by,
            "filter_status": filter_status,
            "filter_search_options": search_options,
            "filter_status_options": views.ASSIGNMENTS_STATUS_OPTIONS,
            "pair_context_lookup": pair_context_lookup,
            "issues": issues,
            "missing_confirm": missing_confirm,
            "is_blocked": is_blocked,
            "fields_with_data": assignments.assignment_fields_with_data(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Assignments"
            ),
            "page_ctx": views.build_assignments_page_context(
                db, review_session
            ),
            # Segment 19I Item 8 — the page's half of the gate the
            # five mutating routes already enforce. The template read
            # `is_ready` from the shared workflow context, which
            # disagreed with those routes on three of five states:
            # `expired` / `archived` offered live controls they
            # refuse, and `ready` hid the *search* along with them.
            # Composed here rather than added to
            # `build_workflow_card_context`, which eight pages share.
            "can_edit": lifecycle.is_editable(review_session),
            # The recovery path out of each locked state, for the
            # disabled self-review toggle's title.
            # `revert_session_to_draft` accepts `ready` and `expired`;
            # `archived` leaves through `unarchive_session` in the
            # archived-sessions lobby (Item 6 set this pattern).
            "lock_action": (
                ""
                if lifecycle.is_editable(review_session)
                else (
                    "Unarchive this session"
                    if lifecycle.is_archived(review_session)
                    else "Revert to draft"
                )
            ),
            **workflow_ctx,
        },
        status_code=status_code,
    )


# Manual-CSV assignment upload route retired 2026-05-11 (16A PR 5).
# The dev-only escape hatch kept on the bet that some real bypass
# need would surface; nine days of pilot prep later no such need
# appeared. The rule-based engine + Relationships table cover every
# realistic operator scenario. Tests previously seeding assignments
# via this route now use the rule-based generate endpoint with the
# Full Matrix seed RuleSet.


@router.post("/sessions/{session_id}/assignments/generate")
def assignments_generate(
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Page-level Generate (Segment 15B Slice 3a).

    Materialises ``Assignment`` rows for every instrument with a
    pinned ``rule_set_id``. Instruments with NULL ``rule_set_id``
    are skipped silently by ``replace_assignments(instrument_id=None)``.
    Any existing rows are replaced wholesale; the
    ``confirm_replace`` form field gates the destructive path
    when the session already has assignments — mirroring the
    pre-Slice-3a Rule Based card flow.
    """

    _require_editable(review_session)
    existing = assignments.existing_count(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                f"?needs_confirm=1"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if existing > 0:
        _require_response_loss_ack(
            db, review_session, acknowledge_response_loss
        )
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/assignments/delete-all")
def assignments_delete_all(
    confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
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
    assignments.delete_all_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/{instrument_id}/self-reviews/active",
    response_class=HTMLResponse,
    response_model=None,
)
def assignments_instrument_self_reviews_active(
    session_id: int,
    instrument_id: int,
    active: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Per-instrument self-review include toggle — owns the
    checkbox in the Self review column on the Assignments-page
    status blocks. Bulk-flips every self-review row on this
    instrument to the posted ``active`` boolean. Mixed states
    converge: ``active=false`` flips remaining active rows to
    false; ``active=true`` flips remaining deactivated rows to
    true. Audit event
    ``assignments.instrument_self_reviews_active_set`` records the
    flipped row count + ``refs.instrument_id``."""

    _require_editable(review_session)
    is_active = active == "true"
    assignments.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=instrument_id,
        user=user,
        active=is_active,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/bulk-inactivate",
    response_class=HTMLResponse,
    response_model=None,
)
def assignments_bulk_inactivate(
    session_id: int,
    assignment_ids: list[int] = Form(default=[]),
    filter_q: str = Form(default=""),
    filter_search_by: str = Form(default="all"),
    filter_status: str = Form(default="all"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-exclude the selected assignments — the Inactivate
    button on the Assignments-page operator-actions card."""
    _require_editable(review_session)
    assignments.bulk_set_assignment_include(
        db,
        review_session=review_session,
        assignment_ids=assignment_ids,
        include=False,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=_assignments_url(
            review_session.id, filter_q, filter_search_by, filter_status
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/bulk-activate",
    response_class=HTMLResponse,
    response_model=None,
)
def assignments_bulk_activate(
    session_id: int,
    assignment_ids: list[int] = Form(default=[]),
    filter_q: str = Form(default=""),
    filter_search_by: str = Form(default="all"),
    filter_status: str = Form(default="all"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-include the selected assignments — the Activate button
    on the Assignments-page operator-actions card."""
    _require_editable(review_session)
    assignments.bulk_set_assignment_include(
        db,
        review_session=review_session,
        assignment_ids=assignment_ids,
        include=True,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=_assignments_url(
            review_session.id, filter_q, filter_search_by, filter_status
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
