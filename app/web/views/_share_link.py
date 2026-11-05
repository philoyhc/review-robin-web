"""The Share the session link card on Invitations (14F rungs 3b–3c).

Until bulk email is paced (14G), the operator delivers the session's
stable link through their own channels. The card shows that link and the
session's invitation and reminder templates written for everyone
(``email_templates.render_for_everyone``), to copy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import ReviewSession
from app.services import email_templates


@dataclass(frozen=True)
class SharedMessage:
    key: str
    """``invite`` or ``reminder``: the card's element ids."""
    title: str
    subject: str
    body: str


@dataclass(frozen=True)
class ShareLinkCard:
    session_link: str
    messages: tuple[SharedMessage, ...]


def build_share_link_card(review_session: ReviewSession, session_link: str) -> ShareLinkCard:
    """The card's link and its two messages; ``session_link`` is the
    absolute URL of ``/me/sessions/{public_id}``, built by the route."""
    messages: list[SharedMessage] = []
    for key, kind, title in (
        ("invite", "invitation", "Invitation message"),
        ("reminder", "reminder", "Reminder message"),
    ):
        subject, body = email_templates.render_for_everyone(review_session, kind, session_link)
        messages.append(SharedMessage(key=key, title=title, subject=subject, body=body))
    return ShareLinkCard(session_link=session_link, messages=tuple(messages))
