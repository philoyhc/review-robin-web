"""The timeline checked as a whole (segment AD2K, ruling 83): what keeps
an exercise's first stage from being published, and what is worth a
second look but publishes anyway.

Errors block publishing the first stage (`locks.publish_problems`, so Home
lists them under *Blocking publication* and Process's Publish waits on
them); errors and warnings both show on Process's Outline, as saved.

- **Errors.** The first stage holds neither a Form nor *Create
  dossiers*: nothing says whose dossiers the exercise holds. *Create
  dossiers* after a Form: a Form creates the dossiers itself, so the item
  is not offered after one (ruling 83 as amended, author 2026-11-27); a
  timeline saved before says so. A Form after *Create dossiers* is
  allowed: it writes to the dossiers already made.
- **Warnings.** *Create dossiers* has no entries; the Form's *Who may
  apply* is *Invitees* with no one invited (ruling 84, segment AD2I); no
  outcome follows the last gate, so its results decide nothing.

The item is *Candidates* in code (`Stage.candidates`, `applydesk/candidates.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from applydesk import db, stages
from applydesk.models import Candidate, Exercise, Invitee

NO_FIRST_ITEM = (
    "The first stage holds no Form and no Create dossiers: add one, so the exercise has dossiers."
)
POPULATE_AFTER_FORM = (
    "Create dossiers comes after the Form, which creates the dossiers itself: remove one."
)
NO_ENTRIES = "Create dossiers has no one on it yet."
NO_INVITEES = "The Form is for invitees, and no one is invited yet."
NO_LAST_OUTCOME = "No outcome follows the last gate: its results decide nothing."


@dataclass(frozen=True)
class Checked:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def check(plan: stages.Plan, entries: int, invited: int | None = None) -> Checked:
    """``plan``'s timeline checked, ``entries`` the live entries on its
    Create dossiers item, ``invited`` its live invitees when the Form's
    *Who may apply* is *Invitees* (None otherwise)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not plan.stages:
        return Checked((NO_FIRST_ITEM,), ())
    first = plan.stages[0]
    form_at = next((i for i, st in enumerate(plan.stages) if st.form), None)
    populate_at = next((i for i, st in enumerate(plan.stages) if st.candidates), None)
    if not (first.form or first.candidates):
        errors.append(NO_FIRST_ITEM)
    if form_at is not None and populate_at is not None and populate_at > form_at:
        errors.append(POPULATE_AFTER_FORM)
    if populate_at is not None and entries == 0:
        warnings.append(NO_ENTRIES)
    # Invitees chosen counts only where the Form does not invite from the
    # dossiers made before it.
    from_dossiers = populate_at is not None and form_at is not None and populate_at <= form_at
    if form_at is not None and not from_dossiers and invited == 0:
        warnings.append(NO_INVITEES)
    columns = [c for st in plan.stages for c in st.columns]
    last_gate = max((i for i, c in enumerate(columns) if isinstance(c, stages.Gate)), default=None)
    if last_gate is not None and not any(
        isinstance(c, stages.Outcome) for c in columns[last_gate + 1 :]
    ):
        warnings.append(NO_LAST_OUTCOME)
    return Checked(tuple(errors), tuple(warnings))


def entries_of(public_id: str) -> int:
    """The live entries on the exercise's Create dossiers, read in a
    session of its own, as `stages.plan_of` is."""
    session = db.new_session()
    try:
        found = session.scalar(
            select(func.count())
            .select_from(Candidate)
            .join(Exercise, Exercise.id == Candidate.exercise_id)
            .where(Exercise.public_id == public_id, Candidate.removed_at.is_(None))
        )
    finally:
        session.close()
    return found or 0


def invited_of(public_id: str) -> int | None:
    """The exercise's live invitees when its Form is for invitees
    (``eligibility`` ``invitation``), None otherwise."""
    session = db.new_session()
    try:
        eligibility = session.scalar(
            select(Exercise.eligibility).where(Exercise.public_id == public_id)
        )
        if eligibility != "invitation":
            return None
        found = session.scalar(
            select(func.count())
            .select_from(Invitee)
            .join(Exercise, Exercise.id == Invitee.exercise_id)
            .where(Exercise.public_id == public_id, Invitee.removed_at.is_(None))
        )
    finally:
        session.close()
    return found or 0


def of(public_id: str) -> Checked:
    """The exercise's timeline, as saved, checked."""
    return check(stages.plan_of(public_id), entries_of(public_id), invited_of(public_id))
