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
    instruments as instruments_service,
    invitations,
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
    validated: bool = Query(default=False),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # ``?validated=1`` mirrors the Session Home Validate Setup entry
    # path: run validation live, promote ``draft → validated`` when
    # the readiness report is clean, and surface the inline summary
    # pills in the Next Action card render below.
    if validated:
        issues = validation.validate_session_setup(db, review_session)
        report = lifecycle.build_readiness_report(issues)
        if report.can_activate and lifecycle.is_draft(review_session):
            lifecycle.mark_validated(
                db,
                review_session=review_session,
                user=user,
                report=report,
                correlation_id=request_correlation_id(),
            )
    return _render_assignments_hub(
        request,
        db,
        review_session,
        user,
        missing_confirm=needs_confirm == 1,
        validated_just_ran=validated,
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

    # Next Action card context — same shape Session Home builds so
    # the duplicated card on the Assignments page surfaces the same
    # state-aware copy + button row. ``validation_summary`` runs on
    # the ``?validated=1`` entry path AND whenever the session is
    # already in ``validated`` (matching Session Home's gate); other
    # states fall back to the generic copy.
    validation_summary: dict[str, object] | None = None
    validation_issues_by_severity: dict[str, list] = {
        "errors": [],
        "warnings": [],
        "info": [],
    }
    if validated_just_ran or lifecycle.is_validated(review_session):
        issues_for_summary = validation.validate_session_setup(db, review_session)
        report = lifecycle.build_readiness_report(issues_for_summary)
        validation_summary = {
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
            "can_activate": report.can_activate
            and lifecycle.is_validated(review_session),
            "needs_acknowledge": report.has_non_blocking_findings,
        }
        validation_issues_by_severity = {
            "errors": report.errors,
            "warnings": report.warnings,
            "info": report.info,
        }
    reviewer_count = csv_imports.existing_reviewer_count(db, review_session.id)
    reviewee_count = csv_imports.existing_reviewee_count(db, review_session.id)
    has_unpinned_instruments = instruments_service.has_unpinned(
        db, review_session.id
    )
    is_setup_empty = lifecycle.is_draft(review_session) and (
        reviewer_count == 0
        or reviewee_count == 0
        or has_unpinned_instruments
    )
    setup_checklist = {
        "reviewers_ok": reviewer_count > 0,
        "reviewees_ok": reviewee_count > 0,
        "instruments_pinned_ok": not has_unpinned_instruments,
    }
    is_pre_generate = (
        lifecycle.is_draft(review_session)
        and not is_setup_empty
        and (
            assignments.existing_count(db, review_session.id) == 0
            or lifecycle.needs_regeneration_after_revert(
                db, review_session.id
            )
        )
    )
    invitations_generated = invitations.has_invitations(
        db, review_session.id
    )
    invitations_sent = invitations.has_sent_invitations(
        db, review_session.id
    )

    return _templates.TemplateResponse(
        request,
        "operator/session_assignments.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "assignment_count": assignment_count,
            "reviewer_count": reviewer_count,
            "reviewee_count": reviewee_count,
            "setup_checklist": setup_checklist,
            "validation_issues_by_severity": validation_issues_by_severity,
            "pair_sample": pair_sample,
            "truncated_count": truncated_count,
            "pair_context_lookup": pair_context_lookup,
            "issues": issues,
            "missing_confirm": missing_confirm,
            "is_blocked": is_blocked,
            "is_draft": lifecycle.is_draft(review_session),
            "is_validated": lifecycle.is_validated(review_session),
            "is_ready": lifecycle.is_ready(review_session),
            "is_setup_empty": is_setup_empty,
            "is_pre_generate": is_pre_generate,
            "invitations_generated": invitations_generated,
            "invitations_sent": invitations_sent,
            "validation_summary": validation_summary,
            # Wire the Next Action card forms to redirect back here
            # rather than to Session Home after their POST. The
            # /activate and /revert routes honour ``return_to`` via
            # the ``_REVERT_RETURN_TO`` allowlist (which already
            # includes "assignments").
            "next_action_return_to": "assignments",
            "fields_with_data": assignments.assignment_fields_with_data(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Assignments"
            ),
            "page_ctx": views.build_assignments_page_context(
                db, review_session
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
