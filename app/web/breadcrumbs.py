"""Breadcrumb factories for operator and reviewer pages.

Each factory returns a list of ``(label, url)`` tuples. The last tuple
always has ``url=None`` and is rendered as a non-link label marking the
current page. Earlier tuples render as ``<a>`` links.
"""

from __future__ import annotations

from app.db.models import ReviewSession

Crumb = tuple[str, str | None]


def operator_root() -> list[Crumb]:
    return [("Sessions", None)]


def operator_session(session: ReviewSession) -> list[Crumb]:
    return [
        ("Sessions", "/operator/sessions"),
        (session.name, None),
    ]


def operator_session_child(session: ReviewSession, label: str) -> list[Crumb]:
    return [
        ("Sessions", "/operator/sessions"),
        (session.name, f"/operator/sessions/{session.id}"),
        (label, None),
    ]


def operator_session_invitations_reviewer(
    session: ReviewSession, reviewer_label: str
) -> list[Crumb]:
    """Breadcrumb for the reviewer-detail drill-in from Manage
    Invitations (Segment 11C Part 1)."""
    return [
        ("Sessions", "/operator/sessions"),
        (session.name, f"/operator/sessions/{session.id}"),
        ("Invitations", f"/operator/sessions/{session.id}/invitations"),
        (reviewer_label, None),
    ]


def operator_session_responses_reviewee(
    session: ReviewSession, reviewee_label: str
) -> list[Crumb]:
    """Breadcrumb for the reviewee-detail drill-in from the Responses
    page (Segment 11C Part 1 PR 3)."""
    return [
        ("Sessions", "/operator/sessions"),
        (session.name, f"/operator/sessions/{session.id}"),
        ("Responses", f"/operator/sessions/{session.id}/responses"),
        (reviewee_label, None),
    ]


def operator_new_session() -> list[Crumb]:
    return [
        ("Sessions", "/operator/sessions"),
        ("New session", None),
    ]


def reviewer_root() -> list[Crumb]:
    return [("Reviewer", None)]


def reviewer_session(session: ReviewSession) -> list[Crumb]:
    return [
        ("Reviewer", "/reviewer"),
        (session.name, None),
    ]


def reviewer_invite_mismatch() -> list[Crumb]:
    return [
        ("Reviewer", "/reviewer"),
        ("Access denied", None),
    ]
