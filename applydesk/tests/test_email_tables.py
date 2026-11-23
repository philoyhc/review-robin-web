"""The email tables (segment AD2L rung 2): a tick and a template are each
unique per exercise, item and audience; a new exercise has recorded no
ticks, so a sample keeps its own until Process saves them."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from applydesk import db
from applydesk.models import EmailSend, EmailTemplate, Exercise


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


def test_a_new_exercise_has_recorded_no_ticks(session: Session) -> None:
    assert _exercise(session, "zz-mail-1").sends_saved is False


def test_a_template_starts_empty_at_version_0(session: Session) -> None:
    e = _exercise(session, "zz-mail-2")
    row = EmailTemplate(exercise_id=e.id, item="receipt", audience="Applicants")
    session.add(row)
    session.flush()
    assert (row.subject, row.body, row.version, row.saved_at) == ("", "", 0, None)


@pytest.mark.parametrize("model", [EmailSend, EmailTemplate])
def test_one_row_per_item_and_audience(session: Session, model: type) -> None:
    one, two = _exercise(session, "zz-mail-3"), _exercise(session, "zz-mail-4")
    session.add(model(exercise_id=one.id, item="o1", audience="Applicants"))
    session.add(model(exercise_id=one.id, item="o1", audience="Evaluators"))
    session.add(model(exercise_id=two.id, item="o1", audience="Applicants"))
    session.flush()  # another audience, or another exercise, is its own
    session.add(model(exercise_id=one.id, item="o1", audience="Applicants"))
    with pytest.raises(IntegrityError):
        session.flush()
