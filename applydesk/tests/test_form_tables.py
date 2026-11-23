"""The form's tables (segment AD2D rung 2): a card's key is unique per
exercise and kept apart from another exercise's; an exercise's form
revision starts at 0, so the pages keep the sample's form until Form is
first saved."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from applydesk import db
from applydesk.models import Exercise, FormCard


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.rollback()
    s.close()


def _exercise(session: Session, public_id: str) -> Exercise:
    exercise = Exercise(public_id=public_id)
    session.add(exercise)
    session.flush()
    return exercise


def test_a_new_exercise_has_no_form_recorded(session: Session) -> None:
    exercise = _exercise(session, "zz-form-1")
    assert (exercise.form_revision, exercise.form_title, exercise.form_description) == (
        0,
        None,
        None,
    )


def test_a_card_takes_the_defaults_form_gives_a_new_field(session: Session) -> None:
    exercise = _exercise(session, "zz-form-2")
    session.add(FormCard(exercise_id=exercise.id, key="q1", position=0, kind="field"))
    session.flush()
    card = session.scalars(select(FormCard).where(FormCard.exercise_id == exercise.id)).one()
    assert (card.type, card.pool, card.ratio_w, card.ratio_h) == ("string", "institution", "4", "5")
    assert (card.exclusive, card.required, card.shown, card.retired_at) == (
        True,
        False,
        False,
        None,
    )


def test_a_key_is_unique_per_exercise(session: Session) -> None:
    one, two = _exercise(session, "zz-form-3"), _exercise(session, "zz-form-4")
    session.add(FormCard(exercise_id=one.id, key="q1", position=0, kind="field"))
    session.add(FormCard(exercise_id=two.id, key="q1", position=0, kind="field"))
    session.flush()  # the same key on another exercise is its own
    session.add(FormCard(exercise_id=one.id, key="q1", position=1, kind="section"))
    with pytest.raises(IntegrityError):
        session.flush()
