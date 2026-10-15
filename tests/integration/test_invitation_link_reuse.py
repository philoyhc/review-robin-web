"""A reminder reuses the invitation's link even when the operator's own
invitation text never named ``$invite_url`` (participant audit L5).

``invitations.most_recent_invitation_url`` finds the link by searching
the latest invitation's body. An override without the tag left nothing
to find, so every later reminder fell back to a fresh invitation that
rotated the token and killed the links already sent. The renderer now
appends the link to such an override.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Invitation, Reviewer, ReviewSession, User
from app.services import invitations


def _invite_url(token: str) -> str:
    return f"https://example.edu/me/invite/{token}"


def _setup(db: Session, overrides: dict) -> tuple:
    user = User(email="op-reuse@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Reuse",
        code="link-reuse",
        created_by_user_id=user.id,
        status="ready",
        email_template_overrides=overrides,
    )
    db.add(review_session)
    db.flush()
    reviewer = Reviewer(
        session_id=review_session.id, name="Rae", email="rae@example.edu"
    )
    db.add(reviewer)
    db.flush()
    invitation = Invitation(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        token_hash=invitations.hash_token("raw-reuse"),
    )
    db.add(invitation)
    db.commit()
    return user, review_session, reviewer, invitation


def test_a_reminder_reuses_the_link_after_an_override_without_the_tag(
    db: Session,
) -> None:
    user, review_session, reviewer, invitation = _setup(
        db, {"invitation_body": "Please complete your review soon."}
    )
    invitations.send_invitation(
        db,
        invitation=invitation,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        build_invite_url=_invite_url,
    )
    db.refresh(invitation)
    token_hash = invitation.token_hash
    sent_url = invitations.most_recent_invitation_url(
        db, invitation_id=invitation.id
    )
    assert sent_url is not None

    result = invitations.send_reminder(
        db,
        invitation=invitation,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        build_invite_url=_invite_url,
    )

    db.refresh(invitation)
    assert result.fell_back_to_invitation is False
    assert invitation.token_hash == token_hash
    assert (
        invitations.most_recent_invitation_url(db, invitation_id=invitation.id)
        == sent_url
    )
