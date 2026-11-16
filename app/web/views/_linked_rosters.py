"""The roster pages' view of a linked application's rosters (segment 23F
rung 6): whether the page is editable, and the application its lock card
names. The refusals that back them are route dependencies in
``app/web/routes_operator/_shared.py``."""

from __future__ import annotations

from app.db.models import ReviewSession
from app.services import linked_apps
from app.services import session_lifecycle as lifecycle


def rosters_editable(review_session: ReviewSession) -> bool:
    """A roster page's ``is_editable``: the lifecycle's, and not a linked
    application's rosters. Its editor modes (``?add=1``, ``?edit_id=``)
    clear on the same test (Codex on #3924)."""
    return lifecycle.is_editable(review_session) and not linked_apps.locks(
        review_session, linked_apps.Lock.ROSTERS
    )


def rosters_linked_to(review_session: ReviewSession) -> str:
    """The application whose rosters these are, or "": the roster pages'
    lock card names it."""
    if linked_apps.locks(review_session, linked_apps.Lock.ROSTERS):
        return linked_apps.linked_name(review_session)
    return ""


def self_fields_open(review_session: ReviewSession) -> bool:
    """Whether a linked draft's roster page shows its *What … see of their
    own entry* card on the page itself: the rosters are the application's,
    so the Unlock panel that holds the card is not offered, but the card's
    settings stay Review Robin's (Codex on #3924)."""
    return lifecycle.is_editable(review_session) and linked_apps.locks(
        review_session, linked_apps.Lock.ROSTERS
    )
