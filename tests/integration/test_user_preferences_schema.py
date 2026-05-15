"""Schema-level coverage for the Segment 13F PR 7
``users.preferences`` column.

Round-trips the new JSON column. The column is inert today — no
service module reads ``preferences``.

The column sits inert until Segment 18B PR 2 lights it up
(per-operator default timezone + ``/operator/settings`` card).
``NULL`` (or an absent key) means "no preference set".
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def test_preferences_defaults_to_null(db: Session) -> None:
    user = User(email="default@example.edu", display_name="Default")
    db.add(user)
    db.flush()

    reread = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert reread.preferences is None


def test_preferences_round_trips_dict(db: Session) -> None:
    """The container round-trips a JSON object — the first key is
    ``display_timezone`` (18B PR 2's consumer)."""

    user = User(
        email="prefs@example.edu",
        display_name="Prefs",
        preferences={"display_timezone": "Asia/Singapore"},
    )
    db.add(user)
    db.flush()

    reread = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert reread.preferences == {"display_timezone": "Asia/Singapore"}


def test_preferences_mutation_persists(db: Session) -> None:
    """Replacing the JSON object persists across a flush + expire."""

    user = User(email="flip@example.edu", display_name="Flip")
    db.add(user)
    db.flush()
    assert user.preferences is None

    user.preferences = {"display_timezone": "America/New_York"}
    db.flush()
    db.expire(user)
    assert user.preferences == {"display_timezone": "America/New_York"}

    user.preferences = None
    db.flush()
    db.expire(user)
    assert user.preferences is None
