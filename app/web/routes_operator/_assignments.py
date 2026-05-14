"""Assignments hub: index page + manual import + delete-all. Slice 4
of the major refactor.

Note: The Rule Builder routes (``/assignments/rule-based-editor/...``
and ``/assignments/rule-based/generate``) live with the Rule Builder
slice (PR 8), not here, even though they share the URL parent.

Source ranges in pre-refactor ``routes_operator.py``:
1261-1342, 2015-2120, 2350-2380.
"""

from __future__ import annotations

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

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import (
    assignments,
    csv_imports,
    relationships as relationships_service,
)
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
    super_step: str | None = Query(default=None),
    super_error: str | None = Query(default=None),
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
            super_status, super_step, super_error
        ),
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
) -> HTMLResponse:
    assignment_count = assignments.existing_count(db, review_session.id)
    pair_sample = (
        assignments.list_pairs(db, review_session.id) if assignment_count else []
    )
    truncated_count = max(0, assignment_count - len(pair_sample))
    # Pair-context lookup is built up-front so the cookie-backed
    # sort (Segment 13B Part 2 PR 8) can resolve ``pair_tag_*``
    # keys without a second pass through the relationships table.
    pair_context_lookup = (
        relationships_service.pair_context_lookup(db, review_session.id)
        if pair_sample
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
            return inst.short_label or inst.name
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
            "truncated_count": truncated_count,
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
