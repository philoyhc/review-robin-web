"""A session's URL ID, for tests that hold its integer key (19V Item 1).

Session URLs carry ``sessions.public_id``, never ``sessions.id``. Most
tests build URLs from the row itself (``review_session.public_id``);
this is for the helpers that are handed only the integer and have no
``db`` of their own. It reads through the same ``get_db`` override the
test client uses, so it sees exactly what the routes see.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import ReviewSession
from app.db.session import get_db
from app.main import app


def public_id(session_id: int) -> str:
    """The public ID of the session whose primary key is ``session_id``."""
    rows = app.dependency_overrides[get_db]()
    db = next(rows)
    try:
        return db.execute(
            select(ReviewSession.public_id).where(ReviewSession.id == session_id)
        ).scalar_one()
    finally:
        rows.close()
