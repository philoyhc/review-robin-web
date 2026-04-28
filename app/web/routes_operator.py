from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import permissions, sessions

router = APIRouter(prefix="/operator", tags=["operator"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def get_or_create_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated identity has no email claim",
        )

    user = db.execute(
        select(User).where(User.email == current_user.email)
    ).scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=current_user.email,
        display_name=current_user.name,
        external_principal_id=current_user.principal_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def request_correlation_id() -> str:
    return uuid.uuid4().hex


@router.get("/sessions", response_class=HTMLResponse)
def list_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    review_sessions = sessions.list_for_user(db, user)
    return _templates.TemplateResponse(
        request,
        "operator/sessions_list.html",
        {"user": user, "sessions": review_sessions},
    )


@router.get("/sessions/new", response_class=HTMLResponse)
def new_session_form(
    request: Request,
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_new.html",
        {"user": user},
    )


@router.post("/sessions")
def create_session(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    parsed_deadline: datetime | None = None
    if deadline:
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="deadline must be ISO-8601",
            ) from exc

    payload = SessionCreate(
        name=name,
        code=code,
        description=description or None,
        deadline=parsed_deadline,
    )
    review_session = sessions.create_session(
        db,
        user=user,
        payload=payload,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(
    request: Request,
    session_id: int,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if not permissions.user_can_view_session(db, user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )
    review_session = sessions.get_for_user(db, user, session_id)
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _templates.TemplateResponse(
        request,
        "operator/session_detail.html",
        {"user": user, "session": review_session},
    )
