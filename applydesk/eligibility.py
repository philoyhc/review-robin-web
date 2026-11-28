"""Who may apply to an exercise (segment AD4A; ruling 84): one answer for
the User Lobby's *Open to me* and, from AD4C, for *Submit*.

The Form's *Who may apply* decides, as Process and the Form store it:

- **Dossiers**: Create dossiers is on the timeline, so the Form writes to
  the dossiers it made (ruling 83). A person holding a live entry may apply.
- **Invitees** (`exercise.eligibility` ``invitation``): a person on the
  invite list, not removed.
- **Anyone signed in** (``open``, or not set): everyone signed in.

Only the reason is answered here: whether the form is open, and the most
per person, are the form's (AD4C, AD4D). An archived or deleted exercise
admits no one. Reads only; never commits.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk.models import Candidate, Exercise, Invitee, Person, Stage

#: Why a person may apply: anyone may, they are invited, or a dossier is
#: held for them.
Reason = Literal["open", "invited", "dossier"]


def from_dossiers(session: Session, exercise: Exercise) -> bool:
    """Whether Create dossiers is on the exercise's timeline, so its
    dossiers' people are the ones who may apply."""
    held = session.scalar(
        select(Stage.id).where(
            Stage.exercise_id == exercise.id,
            Stage.retired_at.is_(None),
            Stage.holds_candidates.is_(True),
        )
    )
    return held is not None


def may_apply(session: Session, exercise: Exercise, person: Person | None) -> Reason | None:
    """Why ``person`` may apply to ``exercise``, or None if they may not.
    No one signed in (None) may not."""
    if person is None or exercise.archived_at is not None or exercise.deleted_at is not None:
        return None
    if from_dossiers(session, exercise):
        entry = session.scalar(
            select(Candidate.id).where(
                Candidate.exercise_id == exercise.id,
                Candidate.person_id == person.id,
                Candidate.removed_at.is_(None),
            )
        )
        return "dossier" if entry is not None else None
    if exercise.eligibility == "invitation":
        invited = session.scalar(
            select(Invitee.id).where(
                Invitee.exercise_id == exercise.id,
                Invitee.person_id == person.id,
                Invitee.removed_at.is_(None),
            )
        )
        return "invited" if invited is not None else None
    return "open"
