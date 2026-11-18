"""The participant's pages, `/me/…` (segment AD1, item 2): an applicant's
exercises and applications, and the dossier an assessor
opens from Review Robin. Placeholders on sample data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import extract, sample_data, stages, timeline, workflow
from applydesk.gate import placeholders_only
from applydesk.lookups import application_or_404, dossier_or_404, exercise_or_404
from applydesk.web import USER_LOBBY, render

router = APIRouter(prefix="/me", dependencies=[Depends(placeholders_only)])

#: What an applicant sees on /me (ruling 41): a Closed exercise stays,
#: read-only, with its released results; Draft and Archived do not.
ON_ME = ("Published", "Closed")


@router.get("", name="applydesk_me")
def me(request: Request) -> Response:
    exercises = [e for e in sample_data.EXERCISES if e.state in ON_ME]
    return render(
        request,
        "applydesk/me/home.html",
        area=USER_LOBBY,
        exercises=exercises,
        mine=sample_data.my_applications(),
        dossiers=[
            (sample_data.exercise(a.exercise_id), a) for a in sample_data.APPLICATIONS[1:5:2]
        ],
    )


@router.get("/exercises/{exercise_id}", name="applydesk_me_exercise")
def exercise(request: Request, exercise_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    if found.state not in ON_ME:
        raise HTTPException(status_code=404)
    # The same timeline as the operator's Home (segment AD1I, rung 5): it
    # holds nothing operator-only, and takes no Next step line.
    return render(
        request,
        "applydesk/me/exercise.html",
        area=USER_LOBBY,
        exercise=found,
        tl=timeline.of(found, applicant=True),
        short=timeline.short,
        mine=sample_data.my_applications(found.public_id),
        results=stages.released_results,
    )


@router.get(
    "/exercises/{exercise_id}/applications/{application_id}", name="applydesk_me_application"
)
def application(request: Request, exercise_id: str, application_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    if found.state not in ON_ME:  # closed with its exercise (author, 2026-11-18)
        raise HTTPException(status_code=404)
    app = application_or_404(found, application_id)
    return render(
        request,
        "applydesk/me/application.html",
        area=USER_LOBBY,
        exercise=found,
        application=app,
        answered=extract.form_answers(found, app),
        form_state=workflow.form_state(found),
        # Only the applicant's own (cold read): another's page names none.
        results=stages.released_results(found.public_id, app.public_id)
        if app.public_id in sample_data.MINE
        else (),
    )


@router.get("/exercises/{exercise_id}/dossiers/{dossier_id}", name="applydesk_me_dossier")
def dossier(request: Request, exercise_id: str, dossier_id: str) -> Response:
    """The dossier (rulings 5, 6, 9, 13 and 25): the *Shown to
    reviewers* section only; in a blind exercise the applicant's name and
    identifiers redacted. Named by its own ID, never the application's."""
    found = exercise_or_404(exercise_id)
    if found.state not in ON_ME:  # closed with its exercise (author, 2026-11-18)
        raise HTTPException(status_code=404)
    app = dossier_or_404(found, dossier_id)
    return render(
        request,
        "applydesk/me/dossier.html",
        area=USER_LOBBY,
        exercise=found,
        application=app,
        shown=extract.form_answers(found, app)[0],
    )
