"""The timeline checked as a whole (segment AD2K, ruling 83): what keeps
an exercise's first stage from being published, and what is worth a
second look but publishes anyway.

Errors block publishing the first stage (`locks.publish_problems`, so Home
lists them under *Blocking publication* and Process's Publish waits on
them); errors and warnings both show on Process's Outline, as saved.

- **Errors.** The first stage holds neither a Form nor *Populate
  Dossiers*: nothing says whose dossiers the exercise holds. *Populate
  Dossiers* after a Form: it populates only as the first item. A Form
  after *Populate Dossiers*: it needs an entry rule naming whom it
  invites, which AD4 builds.
- **Warnings.** *Populate Dossiers* has no entries; no outcome follows
  the last gate, so its results decide nothing.

The item is *Candidates* in code (`Stage.candidates`, `applydesk/candidates.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from applydesk import db, stages
from applydesk.models import Candidate, Exercise

NO_FIRST_ITEM = (
    "The first stage holds no Form and no Populate Dossiers: add one, so the exercise has dossiers."
)
POPULATE_AFTER_FORM = (
    "Populate Dossiers comes after the Form: it populates dossiers only as the first item."
)
FORM_AFTER_POPULATE = (
    "A Form after Populate Dossiers needs an entry rule, not built yet: move "
    "the Form to the first stage or remove it."
)
NO_ENTRIES = "Populate Dossiers has no one on it yet."
NO_LAST_OUTCOME = "No outcome follows the last gate: its results decide nothing."


@dataclass(frozen=True)
class Checked:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def check(plan: stages.Plan, entries: int) -> Checked:
    """``plan``'s timeline checked, ``entries`` the live entries on its
    Populate Dossiers item."""
    errors: list[str] = []
    warnings: list[str] = []
    if not plan.stages:
        return Checked((NO_FIRST_ITEM,), ())
    first = plan.stages[0]
    form_at = next((i for i, st in enumerate(plan.stages) if st.form), None)
    populate_at = next((i for i, st in enumerate(plan.stages) if st.candidates), None)
    if not (first.form or first.candidates):
        errors.append(NO_FIRST_ITEM)
    if form_at is not None and populate_at is not None:
        if populate_at > form_at:
            errors.append(POPULATE_AFTER_FORM)
        elif form_at > populate_at:
            errors.append(FORM_AFTER_POPULATE)
    if populate_at is not None and entries == 0:
        warnings.append(NO_ENTRIES)
    columns = [c for st in plan.stages for c in st.columns]
    last_gate = max((i for i, c in enumerate(columns) if isinstance(c, stages.Gate)), default=None)
    if last_gate is not None and not any(
        isinstance(c, stages.Outcome) for c in columns[last_gate + 1 :]
    ):
        warnings.append(NO_LAST_OUTCOME)
    return Checked(tuple(errors), tuple(warnings))


def entries_of(public_id: str) -> int:
    """The live entries on the exercise's Populate Dossiers, read in a
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


def of(public_id: str) -> Checked:
    """The exercise's timeline, as saved, checked."""
    return check(stages.plan_of(public_id), entries_of(public_id))
