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
    validation,
)
from app.services import session_lifecycle as lifecycle
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
    wf: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_assignments_hub(
        request,
        db,
        review_session,
        user,
        missing_confirm=needs_confirm == 1,
        workflow_banner_kind=wf,
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
    workflow_banner_kind: str | None = None,
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
    return _templates.TemplateResponse(
        request,
        "operator/session_assignments.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "assignment_count": assignment_count,
            "reviewer_count": csv_imports.existing_reviewer_count(db, review_session.id),
            "reviewee_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "pair_sample": pair_sample,
            "truncated_count": truncated_count,
            "pair_context_lookup": pair_context_lookup,
            "issues": issues,
            "missing_confirm": missing_confirm,
            "is_blocked": is_blocked,
            "is_ready": lifecycle.is_ready(review_session),
            "fields_with_data": assignments.assignment_fields_with_data(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Assignments"
            ),
            "page_ctx": views.build_assignments_page_context(
                db, review_session
            ),
            "workflow_card": views.build_workflow_card_context(
                db, review_session, banner_kind=workflow_banner_kind
            ),
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
    """Page-level Generate (Segment 15B Slice 3a + 15E PR 3 wrap).

    Segment 15E PR 3 wraps the existing Generate with two validation
    passes:

    1. Pre-flight **setup-gate** check (rules grouped under the
       Setup gate via ``app.web.views._validate.gate_for_rule_key``).
       If any setup-gate errors, hard-stop with ``?wf=setup_errors``
       — no assignment rows written. The workflow card banner
       points the operator at the Validate page for detail.
    2. Run ``replace_assignments`` (existing behaviour).
    3. Post-flight full validation. When the readiness report is
       clean (no errors), auto-call ``mark_validated`` to flip
       ``draft → validated`` so the operator's next click is
       Activate without an intermediate "Validate Setup" step.

    The ``?wf=`` redirect param carries the outcome
    (``clean | warnings | errors | setup_errors``); the workflow
    card view-shape adapter renders the matching banner.

    Materialises ``Assignment`` rows for every instrument with a
    pinned ``rule_set_id``. Instruments with NULL ``rule_set_id``
    are skipped silently by ``replace_assignments(instrument_id=None)``.
    Any existing rows are replaced wholesale; the
    ``confirm_replace`` form field gates the destructive path
    when the session already has assignments — mirroring the
    pre-Slice-3a Rule Based card flow.
    """
    from app.web.views._validate import gate_for_rule_key

    _require_editable(review_session)

    # Pre-flight setup-gate validation. Setup-gate errors hard-stop
    # the wrap; the operator fixes upstream on the Setup tabs.
    pre_issues = validation.validate_session_setup(db, review_session)
    setup_gate_errors = [
        i
        for i in pre_issues
        if i.severity.value == "error"
        and gate_for_rule_key(i.rule_key or "") == "setup"
    ]
    if setup_gate_errors:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                f"?wf=setup_errors"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

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
    correlation_id = request_correlation_id()
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=correlation_id,
    )

    # Post-flight full validation. Surfaces clean / warnings /
    # errors as the workflow-card banner via ``?wf=`` redirect.
    # Auto-promoting draft → validated here would conflict with the
    # lifecycle invariant ``replace_assignments`` enforces (it calls
    # ``invalidate_if_validated`` deliberately so the operator
    # re-acknowledges any validation findings after a mutation).
    # The operator still clicks "Validate Setup" on Session Home to
    # reach validated state in PR 3; PR 5 (Session Home Next Action
    # retirement) will revisit how the validate step surfaces on the
    # workflow card.
    post_issues = validation.validate_session_setup(db, review_session)
    post_report = lifecycle.build_readiness_report(post_issues)
    if not post_report.can_activate:
        wf_kind = "errors"
    elif post_report.has_non_blocking_findings:
        wf_kind = "warnings"
    else:
        wf_kind = "clean"

    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/assignments"
            f"?wf={wf_kind}"
        ),
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
