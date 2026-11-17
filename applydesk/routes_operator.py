"""The operator's pages, `/operator/exercises/…` (segment AD1, item 2):
placeholders on sample data, controls inert."""

from __future__ import annotations

import functools
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import paging, sample_data, stages, workflow
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


@router.get("/exercises/{exercise_id}/evaluations/{gate}", name="applydesk_gate_evaluations")
def gate_evaluations(
    request: Request,
    exercise_id: str,
    gate: str,
    offset: str = "0",
    q: str = "",
    sort: str = "",
) -> Response:
    """A gate's assignments on a page of their own (segment AD1H): one
    gate may pair 30 evaluators with 100 dossiers, so its pairs show a
    row each (author, 2026-11-17), 200 at a time, filtered by candidate
    or evaluator."""
    exercise = exercise_or_404(exercise_id)
    number = re.fullmatch(r"gate_([1-9][0-9]*)", gate)
    plan = stages.plan_of(exercise.public_id)
    found = stages.gate_numbered(plan, int(number.group(1))) if number else None
    if found is None or exercise.state == "Draft":
        raise HTTPException(status_code=404)
    rows, spread = stages.assignments(exercise.public_id, found)
    pairs = stages.pairs_of(rows)
    state = workflow.gate_state(exercise.public_id, found.key)
    sent = workflow.gate_opened(*state)
    # Sorted on the server, across every page (author, 2026-11-17: as
    # Review Robin's tables; a page shows 200 of up to 2,980).
    order = paging.parse_sort(sort)
    shown = stages.sorted_pairs(
        stages.matching(pairs, q, exercise.blind), order, found, sent, exercise.blind
    )
    # An offset that is not a whole number reads as the first page.
    start = int(offset) if re.fullmatch(r"-?[0-9]+", offset) else 0
    where = paging.page(len(shown), start, paging.PAGE_SIZE)
    return render(
        request,
        "applydesk/operator/gate_evaluations.html",
        area=OPERATOR_LOBBY,
        nav=exercise_nav(exercise.public_id, "evaluations"),
        status=workflow.status_row(exercise),
        exercise=exercise,
        gate=found,
        state=state,
        sent=sent,
        order=order,
        sort_text=paging.sort_text,
        plain_click=paging.plain_click,
        shift_click=paging.shift_click,
        sort_badge=paging.sort_badge,
        # Its operations' data (AD1G rung 6b), for a gate still the
        # operator's to change.
        ev_data=None if sent else stages.page_data(exercise.public_id, found, rows, exercise.blind),
        all_rows=rows,
        all_pairs=pairs,
        rows=shown[where.offset : where.end],
        matched=len(shown),
        spread=spread,
        where=where,
        q=q.strip(),
        mode_label=dict(stages.MODES).get(found.mode, found.mode),
        assignment_state=stages.assignment_state,
        assignment_counts=stages.assignment_counts,
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
        going_on=stages.going_on,
        last_submitted=stages.last_submitted,
        scope=stages.scope,
        submitted_rank=stages.submitted_rank,
        answers=functools.partial(sample_data.answers, exercise.public_id),
        form_lists=sample_data.list_questions(exercise.public_id),
        rule_text=stages.rule_text,
        rule_json=stages.rule_json,
        weight_rows=stages.weight_rows,
        result_label=functools.partial(stages.result_label, stages.plan_of(exercise.public_id)),
        stage_problems=stages.problems,
        blank_stage=stages.Stage(0, "", ""),
        # A new gate starts with one blank result, as a new form a String card.
        blank_gate=stages.Gate(
            "", 0, "", "RRW", (stages.GateResult("r1", "", stages.Field(), "mean"),)
        ),
        result_summary=stages.result_summary,
        result_type=stages.result_type,
        field_types=stages.FIELD_TYPES,
        derivations=stages.DERIVATIONS,
        allowed=stages.ALLOWED,
        blank_result=stages.GateResult("", "", stages.Field(), "mean"),
        field_text=stages.field_text,
        blank_outcome=stages.Outcome("", 0, "", (), "", ""),
        gate_state=workflow.gate_state,
        gate_opened=workflow.gate_opened,
        sources_of=functools.partial(stages.sources_of, exercise.public_id),
        total_bounds=stages.total_bounds,
        sources_warn=stages.sources_warn,
        gate_summary=stages.gate_summary,
        evaluators_summary=stages.evaluators_summary,
        gate_types=stages.GATE_TYPES,
        fields_of=stages.fields_of,
        field_summary=stages.field_summary,
        source_field=stages.source_field,
        collated=stages.collated,
        derivation_text=stages.derivation_text,
        blank_field=stages.ResponseField("", "", stages.Field()),
        assignments=functools.partial(stages.assignments, exercise.public_id),
        assignment_state=stages.assignment_state,
        assignment_counts=stages.assignment_counts,
        pairs_of=stages.pairs_of,
        sources_summary=stages.sources_summary,
        nominee_questions=stages.nominee_questions(exercise.public_id),
        blank_source=stages.Source("panel", "", 1, 1),
        source_kinds=stages.SOURCE_KINDS,
        modes=stages.MODES,
        emails=workflow.emails(exercise.public_id),
        sends=functools.partial(workflow.sends, exercise.public_id),
        form_state=workflow.form_state(exercise),
    )
