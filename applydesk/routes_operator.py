"""The operator's pages, `/operator/exercises/…` (segment AD1, item 2):
placeholders on sample data, controls inert."""

from __future__ import annotations

import functools

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import sample_data, stages, workflow
from applydesk.gate import placeholders_only
from applydesk.lookups import exercise_or_404
from applydesk.web import OPERATIONS_PAGES, OPERATOR_LOBBY, SETUP_PAGES, exercise_nav, render

router = APIRouter(prefix="/operator", dependencies=[Depends(placeholders_only)])

#: An exercise's operator pages beyond Home, each a partial of
#: `operator/section.html`, headed by its tab's label (ruling 14).
SECTIONS: dict[str, str] = dict(SETUP_PAGES + OPERATIONS_PAGES)


@router.get("/exercises", name="applydesk_exercises")
def exercises(request: Request) -> Response:
    return render(
        request,
        "applydesk/operator/exercises.html",
        area=OPERATOR_LOBBY,
        exercises=sample_data.EXERCISES,
        applications=sample_data.applications_of,
        current_stage=workflow.current_stage,
    )


@router.get("/exercises/{exercise_id}", name="applydesk_exercise_home")
def exercise_home(request: Request, exercise_id: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    return render(
        request,
        "applydesk/operator/home.html",
        area=OPERATOR_LOBBY,
        nav=exercise_nav(exercise.public_id, ""),
        status=workflow.status_row(exercise),
        exercise=exercise,
        applications=sample_data.applications_of(exercise.public_id),
        assessors=sample_data.assessors_of(exercise.public_id),
        missing=sample_data.setup_missing(exercise),
        wf_steps=workflow.steps(exercise),
        wf_groups_of=workflow.groups,
        next_step=workflow.next_step,
    )


@router.get("/exercises/{exercise_id}/form/preview", name="applydesk_form_preview")
def form_preview(request: Request, exercise_id: str) -> Response:
    """The application form as an applicant sees it, in its own tab
    (segment AD1B, iteration): drawn from the Form page that opened it,
    else from the sample form."""
    exercise = exercise_or_404(exercise_id)
    return render(
        request,
        "applydesk/operator/form_preview.html",
        area=OPERATOR_LOBBY,
        exercise=exercise,
        snapshot=sample_data.form_snapshot(exercise.public_id),
        people=sample_data.people_pools(exercise.public_id),
    )


@router.get("/exercises/{exercise_id}/{section}", name="applydesk_exercise_section")
def exercise_section(request: Request, exercise_id: str, section: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    if section not in SECTIONS:
        raise HTTPException(status_code=404)
    return render(
        request,
        "applydesk/operator/section.html",
        area=OPERATOR_LOBBY,
        nav=exercise_nav(exercise.public_id, section),
        status=workflow.status_row(exercise),
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
        summary=functools.partial(
            sample_data.card_summary, pools=sample_data.people_pools(exercise.public_id)
        ),
        kept_size=sample_data.kept_size,
        people=sample_data.people_pools(exercise.public_id),
        panel_pools=sample_data.panel_pools(exercise.public_id),
        panels=sample_data.panels_of(exercise.public_id),
        roster=sample_data.roster(exercise.public_id),
        uses=stages.panel_uses(exercise.public_id),
        panels_sent=workflow.panels_sent(exercise.public_id),
        blank=sample_data.FormCard("field"),
        blank_section=sample_data.FormCard("section"),
        plan=stages.plan_of(exercise.public_id),
        counts=stages.counts,
        last_submitted=stages.last_submitted,
        scope=stages.scope,
        submitted_rank=stages.submitted_rank,
        rule_text=stages.rule_text,
        rule_json=stages.rule_json,
        stage_problems=stages.problems,
        blank_stage=stages.Stage(0, "", ""),
        blank_gate=stages.Gate("", 0, "", "RRW"),
        result_summary=stages.result_summary,
        result_type=stages.result_type,
        field_types=stages.FIELD_TYPES,
        derivations=stages.DERIVATIONS,
        allowed=stages.ALLOWED,
        blank_result=stages.GateResult("", "", stages.Field(), "mean"),
        field_text=stages.field_text,
        blank_outcome=stages.Outcome("", 0, "", (), "", ""),
        gate_state=workflow.gate_state,
        emails=workflow.emails(exercise.public_id),
        sends=functools.partial(workflow.sends, exercise.public_id),
        form_state=workflow.form_state(exercise),
        wf_steps=workflow.steps(exercise),
        wf_groups_of=workflow.groups,
        next_step=workflow.next_step,
    )
