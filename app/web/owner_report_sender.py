"""Mail the owner reports a request's actions committed (14C Item 4).

An app-wide dependency: it yields, the route runs, and on the way out
anything ``app.services.owner_reports`` promoted at a commit is mailed
from the signed-in operator's mailbox (``cordware.graph.mailer_for``),
each outcome audited. A request whose actions owe no report costs a lazy
database session (no connection) and a dict lookup. Never raises: a
report is never worth the action's response.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.logging_config import get_logger
from app.services import operator_settings, owner_reports
from app.web import urls
from app.web.deps import request_correlation_id
from cordware import graph

log = get_logger(__name__)


def send_owner_reports(request: Request, db: Session = Depends(get_db)) -> Iterator[None]:
    try:
        yield
    finally:
        _send_ready(request, db)


def _send_ready(request: Request, db: Session) -> None:
    """Mail what committed, even when the route raised after committing."""
    reports = owner_reports.take_ready(db)
    if not reports:
        return
    try:
        _send(request, db, reports)
    except Exception:  # the action has answered; a report never fails it
        log.exception("owner reports failed", extra={"event": "report.sender_failed"})


def _send(request: Request, db: Session, reports: list[owner_reports.Report]) -> None:
    mailer: graph.Mailer | None = None
    refusal: graph.GraphError | None = None
    try:
        mailer = graph.mailer_for(request)
    except graph.GraphError as exc:
        refusal = exc
    origin = f"{request.url.scheme}://{request.url.netloc}"

    def send(report: owner_reports.Report) -> None:
        if mailer is None:
            assert refusal is not None
            raise refusal
        link = (
            origin + urls.url_path(request, f"/operator/sessions/{report.session_public_id}")
            if report.session_public_id
            else None
        )
        subject, body = owner_reports.compose(report, session_link=link)
        actor = db.get(User, report.actor_user_id)
        keep = (
            actor is not None and operator_settings.get_email_preferences(actor).save_to_sent_items
        )
        mailer.send_mail(
            graph.MailMessage(to=report.to, subject=subject, body=body, save_to_sent_items=keep)
        )

    owner_reports.send_ready(db, reports, send=send, correlation_id=request_correlation_id())
