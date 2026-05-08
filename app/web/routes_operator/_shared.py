from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession
from app.services import instruments as instruments_service
from app.services import lifecycle_display, session_lifecycle as lifecycle

_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "templates")
)
_templates.env.globals["app_version"] = settings.app_version
_templates.env.globals["display_field_label"] = (
    instruments_service.display_field_label
)
_templates.env.globals["is_locked_display_source"] = (
    instruments_service.is_locked_display_source
)
_templates.env.filters["lifecycle_label"] = (
    lifecycle_display.lifecycle_display_label
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


def _lifecycle_error_response(exc: lifecycle.LifecycleError) -> HTTPException:
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


_QUICK_SETUP_COOKIE_PREFIX = "qsu"


def _quick_setup_cookie_name(session_id: int) -> str:
    return f"{_QUICK_SETUP_COOKIE_PREFIX}_{session_id}"


def _quick_setup_unlocked(request: Request, review_session: ReviewSession) -> bool:
    """``True`` when the operator's last lock-toggle action was Unlock.

    Read from the per-session cookie set by
    ``POST /sessions/{id}/quick-setup/lock``. Absent ⇒ default locked.
    """

    return request.cookies.get(_quick_setup_cookie_name(review_session.id)) == "1"
