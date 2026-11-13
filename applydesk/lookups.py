"""Path lookups the route modules share (segment AD1, item 2): each
checks an ID's shape before looking it up, and answers 404 for a
malformed or unknown one. Route modules import this, never each other."""

from __future__ import annotations

from fastapi import HTTPException

from applydesk import sample_data
from applydesk.ids import is_public_id


def exercise_or_404(exercise_id: str) -> sample_data.Exercise:
    if not is_public_id(exercise_id):
        raise HTTPException(status_code=404)
    found = sample_data.exercise(exercise_id)
    if found is None:
        raise HTTPException(status_code=404)
    return found


def application_or_404(
    exercise: sample_data.Exercise, application_id: str
) -> sample_data.Application:
    if not is_public_id(application_id):
        raise HTTPException(status_code=404)
    found = sample_data.application(exercise.public_id, application_id)
    if found is None:
        raise HTTPException(status_code=404)
    return found


def file_or_404(exercise: sample_data.Exercise, file_id: str) -> sample_data.Application:
    """The application an application file shows, by the file's own ID."""
    if not is_public_id(file_id):
        raise HTTPException(status_code=404)
    found = sample_data.by_file(exercise.public_id, file_id)
    if found is None:
        raise HTTPException(status_code=404)
    return found
