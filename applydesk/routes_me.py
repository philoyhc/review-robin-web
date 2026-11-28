"""The participant's pages, `/me/…` (segment AD1, item 2): an applicant's
exercises and applications, and the dossier an assessor
opens from Review Robin. Placeholders on sample data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import clock, extract, locks, participant, sample_data, stages, timeline, workflow
from applydesk.exercises import ordinaries, stored_all
from applydesk.gate import placeholders_only
from applydesk.lookups import application_or_404, dossier_or_404, exercise_or_404
from applydesk.web import USER_LOBBY, render
from cordware.identity import current_identity

router = APIRouter(prefix="/me", dependencies=[Depends(placeholders_only)])

#: What an applicant sees on /me (ruling 41): a Closed exercise stays,
#: read-only, with its released results; Draft and Archived do not.
ON_ME = ("Published", "Completed", "Closed")


def _on_me(e: sample_data.Exercise, archived: frozenset[str] | None = None) -> bool:
    """Whether the exercise shows on /me: never archived (Codex on #4273:
    an ordinary exercise's state reads Draft whatever is stored); a sample
    by its own state; an exercise made with *New exercise*, whose state
    stays Draft, by its status as its stages give it
    (`locks.exercise_status`), so it shows once published (segment AD4A).
    ``archived`` is the archived IDs when the caller has read them."""
    if archived is None:
        archived = participant.archived_ids([e.public_id])
    if e.public_id in archived:
        return False
    if sample_data.is_sample(e.public_id):
        return e.state in ON_ME
    return locks.exercise_status(e) in ON_ME


@router.get("", name="applydesk_me")
def me(request: Request) -> Response:
    """The User Lobby, the signed-in person's (segment AD4A): their own
    applications, and the exercises whose Form admits them."""
    person_id = participant.signed_in(current_identity(request))
    # As the database has them; a deleted one is gone (segment AD2B), and
    # ordinary exercises with the samples.
    live = ordinaries() + stored_all(sample_data.EXERCISES)
    archived = participant.archived_ids(e.public_id for e in live)
    shown = {e.public_id: e for e in live if e.public_id not in archived}
    return render(
        request,
        "applydesk/me/home.html",
        area=USER_LOBBY,
        exercises=participant.open_to(person_id, [e for e in live if _on_me(e, archived)]),
        # Not an application in a deleted exercise (Codex on #4140).
        mine=[a for a in participant.my_applications(person_id) if a.exercise_id in shown],
        # Open as the form is stored, not the placeholder's flag (Codex).
        form_state=workflow.form_state,
        # Who evaluates which dossier is AD5's pairing: none until then.
        dossiers=[],
    )


@router.get("/exercises/{exercise_id}", name="applydesk_me_exercise")
def exercise(request: Request, exercise_id: str) -> Response:
    found = exercise_or_404(exercise_id)
    if not _on_me(found):
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
            for a in participant.my_applications(participant.signed_in(current_identity(request)))
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
    return render(
        request,
        "applydesk/me/application.html",
        area=USER_LOBBY,
        exercise=found,
        application=app,
        answered=extract.form_answers(found, app),
        form_state=workflow.form_state(found),
        withdrawal_closed_by=workflow.withdrawal_closed_by(found.public_id, app.public_id),
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
