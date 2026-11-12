"""The operator's pages, `/operator/exercises/…` (segment AD1, item 2):
placeholders on sample data, controls inert."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import sample_data
from applydesk.gate import placeholders_only
from applydesk.lookups import exercise_or_404
from applydesk.web import exercise_tabs, render

router = APIRouter(prefix="/operator", dependencies=[Depends(placeholders_only)])

#: An exercise's operator pages beyond Home, each a partial of
#: `operator/section.html`, with its heading.
#: The tabs as the author set them (2026-11-12): Review kept, between
#: Panels and Reports, as a seventh.
SECTIONS: dict[str, str] = {
    "setup": "Setup",
    "form": "Application form",
    "applications": "Applications",
    "panels": "Panels",
    "review": "Assessment in Review Robin",
    "reports": "Reports",
}


@router.get("/exercises", name="applydesk_exercises")
def exercises(request: Request) -> Response:
    return render(
        request,
        "applydesk/operator/exercises.html",
        area="Exercises",
        exercises=sample_data.EXERCISES,
        applications=sample_data.applications_of,
    )


@router.get("/exercises/{exercise_id}", name="applydesk_exercise_home")
def exercise_home(request: Request, exercise_id: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    return render(
        request,
        "applydesk/operator/home.html",
        area="Exercises",
        tabs=exercise_tabs(exercise.public_id),
        exercise=exercise,
        applications=sample_data.applications_of(exercise.public_id),
        assessors=sample_data.assessors_of(exercise.public_id),
        missing=sample_data.setup_missing(exercise),
    )


@router.get("/exercises/{exercise_id}/{section}", name="applydesk_exercise_section")
def exercise_section(request: Request, exercise_id: str, section: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    if section not in SECTIONS:
        raise HTTPException(status_code=404)
    return render(
        request,
        "applydesk/operator/section.html",
        area="Exercises",
        tabs=exercise_tabs(exercise.public_id),
        exercise=exercise,
        section=section,
        heading=SECTIONS[section],
        applications=sample_data.applications_of(exercise.public_id),
        assessors=sample_data.assessors_of(exercise.public_id),
        pool=sample_data.pool_of(exercise.public_id),
        interviewers=sample_data.interviewers_of(exercise.public_id),
        responses=sample_data.RESPONSES,
        cards=sample_data.form_cards(exercise.public_id),
        form_heading=sample_data.form_heading(exercise.public_id),
        card_types=sample_data.CARD_TYPES,
        summary=sample_data.card_summary,
        kept_size=sample_data.kept_size,
        blank=sample_data.FormCard("field"),
        blank_section=sample_data.FormCard("section"),
    )
