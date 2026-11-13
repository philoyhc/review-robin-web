"""The participant's pages, `/me/…` (segment AD1, item 2): an applicant's
exercises and applications, and the application file an assessor
opens from Review Robin. Placeholders on sample data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import sample_data
from applydesk.gate import placeholders_only
from applydesk.lookups import application_or_404, exercise_or_404, file_or_404
from applydesk.web import render

router = APIRouter(prefix="/me", dependencies=[Depends(placeholders_only)])


@router.get("", name="applydesk_me")
def me(request: Request) -> Response:
    exercises = [e for e in sample_data.EXERCISES if e.state == "Published"]
    return render(
        request,
        "applydesk/me/home.html",
        area="My Apply Desk",
        exercises=exercises,
        mine=sample_data.APPLICATIONS[:1],
        files=[(sample_data.exercise(a.exercise_id), a) for a in sample_data.APPLICATIONS[1:5:2]],
    )


@router.get("/exercises/{exercise_id}", name="applydesk_me_exercise")
def exercise(request: Request, exercise_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    if found.state != "Published":
        raise HTTPException(status_code=404)
    return render(request, "applydesk/me/exercise.html", area="My Apply Desk", exercise=found)


@router.get(
    "/exercises/{exercise_id}/applications/{application_id}", name="applydesk_me_application"
)
def application(request: Request, exercise_id: str, application_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    app = application_or_404(found, application_id)
    return render(
        request,
        "applydesk/me/application.html",
        area="My Apply Desk",
        exercise=found,
        application=app,
        shown=sample_data.SHOWN_TO_REVIEWERS,
        not_shown=sample_data.NOT_SHOWN_TO_REVIEWERS,
    )


@router.get("/exercises/{exercise_id}/files/{file_id}", name="applydesk_me_file")
def application_file(request: Request, exercise_id: str, file_id: str) -> Response:
    """The application file (rulings 5, 6, 9 and 13): the *Shown to
    reviewers* section only; in a blind exercise the applicant's name and
    identifiers redacted. Named by its own ID, never the application's."""
    found = exercise_or_404(exercise_id)
    app = file_or_404(found, file_id)
    return render(
        request,
        "applydesk/me/file.html",
        area="My Apply Desk",
        exercise=found,
        application=app,
        shown=sample_data.SHOWN_TO_REVIEWERS,
    )
