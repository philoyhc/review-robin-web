"""The participant's pages, `/me/…` (segment AD1, item 2): an applicant's
exercises and applications, and the application profile page an assessor
opens from Review Robin. Placeholders on sample data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import sample_data
from applydesk.gate import placeholders_only
from applydesk.ids import is_public_id
from applydesk.routes_operator import exercise_or_404
from applydesk.web import render

router = APIRouter(prefix="/me", dependencies=[Depends(placeholders_only)])


@router.get("", name="applydesk_me")
def me(request: Request) -> Response:
    exercises = [e for e in sample_data.EXERCISES if e.state == "Published"]
    return render(
        request,
        "applydesk/me/home.html",
        area="My ApplyDesk",
        exercises=exercises,
        mine=sample_data.APPLICATIONS[:1],
        profiles=[
            (sample_data.exercise(a.exercise_id), a) for a in sample_data.APPLICATIONS[1:5:2]
        ],
    )


@router.get("/exercises/{exercise_id}", name="applydesk_me_exercise")
def exercise(request: Request, exercise_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    if found.state != "Published":
        raise HTTPException(status_code=404)
    return render(request, "applydesk/me/exercise.html", area="My ApplyDesk", exercise=found)


@router.get(
    "/exercises/{exercise_id}/applications/{application_id}", name="applydesk_me_application"
)
def application(request: Request, exercise_id: str, application_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    app = sample_data.application(found.public_id, application_id)
    if not is_public_id(application_id) or app is None:
        raise HTTPException(status_code=404)
    return render(
        request,
        "applydesk/me/application.html",
        area="My ApplyDesk",
        exercise=found,
        application=app,
        shown=sample_data.SHOWN_TO_REVIEWERS,
        not_shown=sample_data.NOT_SHOWN_TO_REVIEWERS,
    )


@router.get("/exercises/{exercise_id}/profiles/{profile_id}", name="applydesk_me_profile")
def profile(request: Request, exercise_id: str, profile_id: str) -> Response:
    """The application profile page (rulings 5, 6 and 9): the *Shown to
    reviewers* section only; in a blind exercise the applicant's name and
    identifiers redacted. Named by its own ID, never the application's."""
    found = exercise_or_404(exercise_id)
    app = sample_data.by_profile(found.public_id, profile_id)
    if not is_public_id(profile_id) or app is None:
        raise HTTPException(status_code=404)
    return render(
        request,
        "applydesk/me/profile.html",
        area="My ApplyDesk",
        exercise=found,
        application=app,
        shown=sample_data.SHOWN_TO_REVIEWERS,
    )
