"""Operator workflow routes — Prepare + Activate (Segment 18F Part 1).

Splits the previous super-button (Generate + Validate + Activate as
one click) into two deliberate steps:

- ``POST /workflow/prepare`` — runs Generate + Validate. Lands the
  session in ``validated`` on a clean report, stays in ``draft`` on
  validation errors (the assignment pairs survive — the reconcile
  has run). Owns the saved-response confirmation detour that fires
  when Generate's reconcile would delete responses.
- ``POST /workflow/activate`` — runs Activate only. The Validate-page
  warnings-acknowledgement detour
  (``/validate?activate=1&return_to=...``) is preserved here: when
  the readiness report (recomputed on activation) has non-blocking
  findings, the route 303s to that URL before calling
  ``activate_session``. Activate failures roll back the
  ``validated → ready`` promotion via ``invalidate_session``.

Per ``guide/segment_18F_workflow_optimization.md`` and the revised
``spec/workflow_card.md``.

Sequential best-effort runs with structured per-step error capture
in both routes. Neither route raises to the framework — every
failure is caught, optionally rolled back, audited via
``session.workflow_run_failed`` (with ``context.button`` carrying
``"prepare_session"`` or ``"activate_session"``), and surfaced as a
``super_status=failed`` 303 redirect.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette import status

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import assignments, audit, validation
from app.services import session_lifecycle as lifecycle
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import _REVERT_RETURN_TO

router = APIRouter()


# Slugs the workflow routes accept as ``return_to``. Mirrors the
# operator revert allowlist plus ``home`` for the Session Home /
# no-card-present case so the warnings-detour URL builder can reuse
# the same plumbing.
_WORKFLOW_RETURN_TO = _REVERT_RETURN_TO | {"home"}


class _StepFailed(Exception):
    """Internal sentinel for a pre-condition failure inside a workflow
    chain (e.g. session not editable). Carries the operator-facing
    message in ``args[0]``."""


def _redirect_url(
    session_id: int,
    return_to: str | None,
    *,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: bool = False,
) -> str:
    """Resolve the post-action redirect target. ``return_to`` honours
    the allowlist; anything else falls through to Session Home.
    Failure diagnostics ride along as query params, and the reconcile
    detour bounces with ``prepare_confirm=responses``. ``super_button``
    is ``"prepare"`` or ``"activate"`` so the workflow card's failure
    banner can vary its copy."""
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


def _warnings_detour_url(session_id: int, return_to: str | None) -> str:
    """The Validate-page warnings-acknowledgement detour. Carries
    ``return_to`` through so the eventual ``/activate`` POST from
    that page lands the operator back on the workflow-card page."""
    base = f"/operator/sessions/{session_id}/validate?activate=1"
    if return_to in _WORKFLOW_RETURN_TO:
        return f"{base}&return_to={return_to}"
    return base


@router.post("/sessions/{session_id}/workflow/prepare")
def workflow_prepare(
    return_to: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Run Generate + Validate as one click — the new "Prepare" button.

    On a clean validation report the session flips ``draft →
    validated``; on validation errors the route stays in ``draft``
    with the per-issue right-column populated on the next render.

    ``acknowledge_response_loss="true"`` confirms the saved-response
    detour: the operator has seen the workflow card's confirmation
    and accepts that the reconcile will delete responses on pairs
    the current setup no longer produces. Absent it, the route
    dry-runs the reconcile and detours to the confirmation when a
    run would delete responses.
    """
    correlation_id = request_correlation_id()

    # Pre-flight gate — Prepare runs only while the session is editable
    # (draft / validated). Ready sessions need to be reverted first.
    if not lifecycle.is_editable(review_session):
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="prepare",
                super_step="precondition",
                super_error="Session can't be edited from its current state.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Saved-response confirmation detour. The Generate step reconciles
    # assignments, which deletes responses on pairs the current setup
    # no longer produces. Dry-run; if it would delete responses and
    # the operator hasn't acknowledged that, bounce to the workflow
    # card's confirmation banner. ``session_has_responses`` is a
    # cheap pre-check so a first preparation skips the dry-run.
    if (
        acknowledge_response_loss != "true"
        and lifecycle.session_has_responses(db, review_session)
    ):
        impact = assignments.reconcile_impact(db, review_session)
        if impact.responses_deleted > 0:
            return RedirectResponse(
                url=_redirect_url(
                    review_session.id, return_to, prepare_confirm=True
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )

    audit.write_event(
        db,
        event_type="session.workflow_run_started",
        summary=f"Prepare-session run started for {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        context={"button": "prepare_session"},
        correlation_id=correlation_id,
    )

    step: str | None = None
    try:
        step = "generate"
        assignments.replace_assignments(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )

        step = "validate"
        issues = validation.validate_session_setup(db, review_session)
        report = lifecycle.build_readiness_report(issues)
        if not report.can_activate:
            # Validation errors — session stays in ``draft``; the
            # per-issue right column surfaces the diagnostic on next
            # render. The audit event records the failure for
            # observability.
            audit.write_event(
                db,
                event_type="session.workflow_run_failed",
                summary=(
                    f"Prepare-session run failed for {review_session.code} "
                    f"at validate"
                ),
                actor_user_id=user.id,
                session=review_session,
                context={
                    "button": "prepare_session",
                    "step": "validate",
                    "error_message": (
                        f"Validation reported "
                        f"{len(report.errors)} error"
                        f"{'' if len(report.errors) == 1 else 's'}."
                    ),
                },
                correlation_id=correlation_id,
            )
            return RedirectResponse(
                url=_redirect_url(
                    review_session.id,
                    return_to,
                    super_status="failed",
                    super_button="prepare",
                    super_step="validate",
                    super_error=(
                        f"Validation reported "
                        f"{len(report.errors)} error"
                        f"{'' if len(report.errors) == 1 else 's'}."
                    ),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if lifecycle.is_draft(review_session):
            lifecycle.mark_validated(
                db,
                review_session=review_session,
                user=user,
                report=report,
                correlation_id=correlation_id,
            )
    except (_StepFailed, lifecycle.LifecycleError, ValueError) as exc:
        message = str(exc)
        audit.write_event(
            db,
            event_type="session.workflow_run_failed",
            summary=(
                f"Prepare-session run failed for {review_session.code} "
                f"at {step}"
            ),
            actor_user_id=user.id,
            session=review_session,
            context={
                "button": "prepare_session",
                "step": step or "unknown",
                "error_message": message,
            },
            correlation_id=correlation_id,
        )
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="prepare",
                super_step=step,
                super_error=message,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=_redirect_url(review_session.id, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/workflow/activate")
def workflow_activate(
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Activate the session — the solo "Activate" button.

    Pre-flight requires ``validated``; Prepare must have run first.
    When the readiness report (recomputed here) has non-blocking
    findings, the route 303s to the Validate-page warnings detour
    instead of activating directly. An Activate failure rolls back
    the ``validated → draft`` flip via ``invalidate_session``.
    """
    correlation_id = request_correlation_id()

    # Pre-flight gates.
    if lifecycle.is_ready(review_session):
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="activate",
                super_step="precondition",
                super_error="Session is already activated.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not lifecycle.is_validated(review_session):
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="activate",
                super_step="precondition",
                super_error="Run Prepare session before activating.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    audit.write_event(
        db,
        event_type="session.workflow_run_started",
        summary=f"Activate-session run started for {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        context={"button": "activate_session"},
        correlation_id=correlation_id,
    )

    try:
        # Recompute the readiness report so a setup edit that
        # happened between Prepare and Activate (e.g. an instrument
        # going inactive) is caught before the live flip.
        issues = validation.validate_session_setup(db, review_session)
        report = lifecycle.build_readiness_report(issues)
        if not report.can_activate:
            raise _StepFailed(
                f"Validation reported "
                f"{len(report.errors)} error"
                f"{'' if len(report.errors) == 1 else 's'}."
            )
        if report.has_non_blocking_findings:
            # Warnings detour. Operator acknowledges inline on the
            # Validate page; no audit emission here — the run is
            # paused at the acknowledgement step, not failed.
            return RedirectResponse(
                url=_warnings_detour_url(review_session.id, return_to),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        lifecycle.activate_session(
            db,
            review_session=review_session,
            user=user,
            report=report,
            acknowledge_warnings=False,
            correlation_id=correlation_id,
        )
    except (_StepFailed, lifecycle.LifecycleError, ValueError) as exc:
        # If we got as far as ``validated → ready``, roll the
        # promotion back so the card resolves to a draft state.
        if lifecycle.is_validated(review_session):
            lifecycle.invalidate_session(
                db,
                review_session=review_session,
                user=user,
                reason="workflow_run_rollback",
                correlation_id=correlation_id,
            )
        message = str(exc)
        audit.write_event(
            db,
            event_type="session.workflow_run_failed",
            summary=(
                f"Activate-session run failed for {review_session.code} "
                f"at activate"
            ),
            actor_user_id=user.id,
            session=review_session,
            context={
                "button": "activate_session",
                "step": "activate",
                "error_message": message,
            },
            correlation_id=correlation_id,
        )
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="activate",
                super_step="activate",
                super_error=message,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=_redirect_url(review_session.id, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/workflow/close")
def workflow_close(
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Close the session — Row 2's "Close session" button.

    Flips ``ready → expired`` and closes every instrument
    (``accepting_responses=False``). Responses (drafts +
    submitted) are preserved; reviewers with
    ``responses_visible_when_closed=True`` instruments can still
    read what they submitted post-close. The session can be
    reopened by clicking Revert to draft, which goes through the
    shared ``/sessions/{id}/revert`` route — that path accepts
    ``expired`` as a valid starting state alongside ``ready``.
    """
    correlation_id = request_correlation_id()
    if not lifecycle.is_ready(review_session):
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="close",
                super_step="precondition",
                super_error="Session must be activated before it can be closed.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        lifecycle.expire_session(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )
    except lifecycle.LifecycleError as exc:
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="close",
                super_step="close",
                super_error=str(exc),
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=_redirect_url(review_session.id, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )
