"""The participant's pages, `/me/…` (segment AD1, item 2): an applicant's
exercises and applications, and the dossier an assessor
opens from Review Robin. Placeholders on sample data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import clock, extract, participant, sample_data, stages, timeline, workflow
from applydesk.exercises import ordinaries, stored_all
from applydesk.gate import placeholders_only
from applydesk.lookups import application_or_404, dossier_or_404, exercise_or_404
from applydesk.web import USER_LOBBY, render
from cordware.identity import current_identity

router = APIRouter(prefix="/me", dependencies=[Depends(placeholders_only)])


def _person(request: Request) -> int | None:
    """The signed-in person's row ID, resolved once per request (as
    `gate.viewer` resolves the viewer once): the page may ask twice."""
    held = getattr(request.state, "applydesk_participant", ...)
    if held is ...:
        held = participant.signed_in(current_identity(request))
        request.state.applydesk_participant = held
    return held


def _on_me(found: sample_data.Exercise) -> bool:
    return participant.on_me(found, participant.archived_ids([found.public_id]))


@router.get("", name="applydesk_me")
def me(request: Request) -> Response:
    """The User Lobby, the signed-in person's (segment AD4A): their own
    applications, and the exercises whose Form admits them."""
    # As the database has them; a deleted one is gone (segment AD2B), and
    # ordinary exercises with the samples.
    admitted, mine = participant.lobby(
        _person(request), ordinaries() + stored_all(sample_data.EXERCISES)
    )
    return render(
        request,
        "applydesk/me/home.html",
        area=USER_LOBBY,
        exercises=admitted,
        form_state=workflow.form_state,
        mine=mine,
        # Who evaluates which dossier is AD5's pairing: none until then.
        dossiers=[],
    )


@router.get("/exercises/{exercise_id}", name="applydesk_me_exercise")
def exercise(request: Request, exercise_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    # Only to someone its Form admits, or who has applied (segment AD4A).
    if not participant.may_see(_person(request), found):
        raise HTTPException(status_code=404)
    # The same timeline as the operator's Home (segment AD1I, rung 5): it
    # holds nothing operator-only, and takes no Next step line.
    return render(
        request,
        "applydesk/me/exercise.html",
        area=USER_LOBBY,
        exercise=found,
        tl=timeline.of(found, applicant=True),
        short=clock.short,
        # The signed-in person's own here (segment AD4A).
        mine=tuple(
            a
            for a in participant.my_applications(_person(request))
            if a.exercise_id == found.public_id
        ),
        results=stages.released_results,
        form_state=workflow.form_state,
    )


@router.get(
    "/exercises/{exercise_id}/applications/{application_id}", name="applydesk_me_application"
)
def application(request: Request, exercise_id: str, application_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    if not _on_me(found):  # closed with its exercise (author, 2026-11-18)
        raise HTTPException(status_code=404)
    app = application_or_404(found, application_id)
    # Only its own applicant reaches an application (segment AD4A):
    # anyone else, the super-admin included, has a 404, as for none.
    if not participant.owns(_person(request), app.public_id):
        raise HTTPException(status_code=404)
    return render(
        request,
        "applydesk/me/application.html",
        area=USER_LOBBY,
        exercise=found,
        application=app,
        answered=extract.form_answers(found, app),
        form_state=workflow.form_state(found),
        withdrawal_closed_by=workflow.withdrawal_closed_by(found.public_id, app.public_id),
        results=stages.released_results(found.public_id, app.public_id),
    )


@router.get("/exercises/{exercise_id}/dossiers/{dossier_id}", name="applydesk_me_dossier")
def dossier(request: Request, exercise_id: str, dossier_id: str) -> Response:
    """The dossier (rulings 5, 6, 9, 13 and 25): the *Shown to
    reviewers* section only; in a blind exercise the applicant's name and
    identifiers redacted. Named by its own ID, never the application's."""
    found = exercise_or_404(exercise_id)
    if not _on_me(found):  # closed with its exercise (author, 2026-11-18)
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
