"""Operator workflow super-button — collapses Generate + Validate +
Activate into a single ``POST /workflow/activate`` route.

Per ``spec/workflow_card.md`` appendix A (PR 3 of the rollout). Lives
in its own slice so the super-button perimeter is easy to retire /
move once PR 4 cleans up the orphaned per-step routes.

Sequential best-effort run with structured per-step error capture:
Generate → Validate → Activate. The four failure paths and the
audit-event story per case are spelled out in appendix A.2 / A.5 /
A.6. The route never raises to the framework — every failure is
caught, optionally rolled back (Activate-failure case), audited
via ``session.workflow_run_failed``, and surfaced as a
``super_status=failed`` 303 redirect.

The Validate-page warnings detour
(``/validate?activate=1&return_to=...``) is preserved: when the
readiness report has non-blocking findings, the super-button 303s
to that URL before calling ``activate_session`` so the operator
acknowledges warnings inline. The detour writes no
``workflow_run_failed`` event — the run is paused at the
acknowledgement step, not failed.

A second detour guards saved responses. The Generate step
reconciles assignments (see ``spec/reconciling_regeneration.md``),
which deletes the responses on any pair the current setup no longer
produces. Before running, the route dry-runs the reconcile via
``assignments.reconcile_impact``; when that impact would delete one
or more responses and the operator hasn't acknowledged it, the
route 303s back to the host page with ``?activate_confirm=responses``
so the workflow card can render the confirmation. The operator
proceeds by re-POSTing with ``acknowledge_response_loss=true``. A
reconcile that deletes no responses never detours. Like the
warnings detour this writes no ``workflow_run_failed`` event.
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


# Slugs the super-button accepts as ``return_to``. Mirrors the
# ``_REVERT_RETURN_TO`` allowlist for Operations-row pages, plus
# ``home`` for the Session Home / no-card-present case so the
# warnings-detour URL builder can reuse the same plumbing.
_SUPER_RETURN_TO = _REVERT_RETURN_TO | {"home"}


class _StepFailed(Exception):
    """Internal sentinel for a pre-condition failure inside the
    super-button chain (e.g. session not editable). Carries the
    operator-facing message in ``args[0]``."""


def _redirect_url(
    session_id: int,
    return_to: str | None,
    *,
    super_status: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    activate_confirm: bool = False,
) -> str:
    """Resolve the post-action redirect target. ``return_to`` honours
    the allowlist; anything else falls through to Session Home. Failure
    diagnostics ride along as query params per the
    ``quick_setup_error`` / ``quick_setup_reason`` pattern."""
    if return_to in _REVERT_RETURN_TO:
        base = f"/operator/sessions/{session_id}/{return_to}"
    else:
        base = f"/operator/sessions/{session_id}"
    if activate_confirm:
        return f"{base}?{urlencode({'activate_confirm': 'responses'})}"
    if super_status is None:
        return base
    params = {"super_status": super_status}
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
    if return_to in _SUPER_RETURN_TO:
        return f"{base}&return_to={return_to}"
    return base


@router.post("/sessions/{session_id}/workflow/activate")
def workflow_activate(
    return_to: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Run Generate + Validate + Activate as one click.

    ``acknowledge_response_loss="true"`` confirms the saved-response
    detour: the operator has seen the workflow card's confirmation
    and accepts that the reconcile will delete responses on pairs the
    current setup no longer produces. Absent it, the route dry-runs
    the reconcile and detours to the confirmation when a run would
    delete responses.
    """
    correlation_id = request_correlation_id()

    # Pre-flight gates — defensive; the workflow-card stepper renders
    # the super-button inert in States 1 / 5 / 6 / 7 / 8.
    if lifecycle.is_ready(review_session):
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_step="precondition",
                super_error="Session is already activated.",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Saved-response confirmation detour. The Generate step reconciles
    # assignments, which deletes responses on pairs the current setup
    # no longer produces. Dry-run the reconcile; if it would delete
    # responses and the operator hasn't acknowledged that, bounce to
    # the workflow card's confirmation. ``session_has_responses`` is a
    # cheap pre-check so first activations skip the dry-run entirely.
    if (
        acknowledge_response_loss != "true"
        and lifecycle.is_editable(review_session)
        and lifecycle.session_has_responses(db, review_session)
    ):
        impact = assignments.reconcile_impact(db, review_session)
        if impact.responses_deleted > 0:
            return RedirectResponse(
                url=_redirect_url(
                    review_session.id, return_to, activate_confirm=True
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

    step: str | None = None
    try:
        step = "generate"
        if not lifecycle.is_editable(review_session):
            raise _StepFailed(
                "Session can't be edited from its current state."
            )
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
            # State 3: stays in draft. The right-column issue list
            # already in PR 2 surfaces the diagnostic; no banner
            # text needed beyond "Validate setup failed". The audit
            # event records the failure for observability.
            audit.write_event(
                db,
                event_type="session.workflow_run_failed",
                summary=(
                    f"Activate-session run failed for {review_session.code} "
                    f"at validate"
                ),
                actor_user_id=user.id,
                session=review_session,
                context={
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
                    super_step="validate",
                    super_error=(
                        f"Validation reported "
                        f"{len(report.errors)} error"
                        f"{'' if len(report.errors) == 1 else 's'}."
                    ),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        lifecycle.mark_validated(
            db,
            review_session=review_session,
            user=user,
            report=report,
            correlation_id=correlation_id,
        )

        step = "activate"
        if report.has_non_blocking_findings:
            # State 4B: detour to /validate?activate=1 so the operator
            # acknowledges warnings inline. No audit emission — the
            # run is paused at the acknowledgement step, not failed.
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
        # If we got past Validate, the session is now ``validated`` —
        # roll it back so the card resolves to State 1A on the next
        # render via the existing
        # ``needs_regeneration_after_revert`` predicate.
        if step == "activate" and lifecycle.is_validated(review_session):
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
                f"at {step}"
            ),
            actor_user_id=user.id,
            session=review_session,
            context={"step": step or "unknown", "error_message": message},
            correlation_id=correlation_id,
        )
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_step=step,
                super_error=message,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=_redirect_url(review_session.id, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )
