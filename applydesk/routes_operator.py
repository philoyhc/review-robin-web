"""The operator's pages, `/operator/exercises/…` (segment AD1, item 2):
built on sample data, working on screen; nothing saved until AD2."""

from __future__ import annotations

import functools
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from applydesk import (
    extract,
    handoff,
    home_ops,
    locks,
    paging,
    sample_data,
    stages,
    timeline,
    workflow,
)
from applydesk.gate import placeholders_only
from applydesk.lookups import exercise_or_404
from applydesk.web import (
    OPERATIONS_PAGES,
    OPERATOR_LOBBY,
    SETUP_PAGES,
    exercise_nav,
    render,
    url_path,
)

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
        exercise_status=locks.exercise_status,
        counts=workflow.counts_of,
        current_stage=workflow.current_stage,
    )


@router.get("/exercises/{exercise_id}", name="applydesk_exercise_home")
def exercise_home(request: Request, exercise_id: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    tl = timeline.of(exercise)
    return render(
        request,
        "applydesk/operator/home.html",
        area=OPERATOR_LOBBY,
        nav=exercise_nav(exercise.public_id, ""),
        status=workflow.status_row(exercise),
        exercise=exercise,
        tl=tl,
        short=timeline.short,
        next_line=timeline.next_step(exercise, tl),
        running_gate=timeline.running_gate(exercise, tl),
        ops=home_ops.of(exercise),
        missing=sample_data.setup_missing(exercise),
        timezones=sample_data.TIMEZONES,
        default_contact=sample_data.DEFAULT_HELP_CONTACT,
        blind_lock=locks.blind_lock(exercise),
        stage_rows=locks.stage_rows(exercise),
        STATUS_CHIP=locks.STATUS_CHIP,
        # Every other exercise's code and name, so Details refuses a
        # clashing code on the page (segment AD1I Semantics).
        other_codes=[
            [e.code, e.name]
            for e in sample_data.EXERCISES
            if e.code and e.public_id != exercise.public_id
        ],
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


def _gate_or_404(exercise: sample_data.Exercise, gate: str) -> stages.Gate:
    """The gate a ``gate_<n>`` path names, 404 for one the exercise lacks
    or a draft exercise."""
    number = re.fullmatch(r"gate_([1-9][0-9]*)", gate)
    plan = stages.plan_of(exercise.public_id)
    found = stages.gate_numbered(plan, int(number.group(1))) if number else None
    if found is None or exercise.state == "Draft":
        raise HTTPException(status_code=404)
    return found


def _bundle(request: Request, exercise: sample_data.Exercise, gate: stages.Gate) -> handoff.Bundle:
    """The gate's bundle, each ``ProfileLink`` the dossier's page as an
    absolute URL under the mount (segment AD1M)."""
    origin = f"{request.url.scheme}://{request.url.netloc}"
    return handoff.bundle(
        exercise,
        gate,
        lambda app: (
            origin
            + url_path(request, f"/me/exercises/{exercise.public_id}/dossiers/{app.dossier_id}")
        ),
    )


@router.get(
    "/exercises/{exercise_id}/evaluations/{gate}/{kind}.csv", name="applydesk_gate_bundle_file"
)
def gate_bundle_file(request: Request, exercise_id: str, gate: str, kind: str) -> Response:
    """One of the four files a gate would be sent with (segment AD1M),
    named as Review Robin names its own: ``<code>_<kind>.csv``."""
    exercise = exercise_or_404(exercise_id)
    found = _gate_or_404(exercise, gate)
    if kind not in handoff.KINDS:
        raise HTTPException(status_code=404)
    sent = _bundle(request, exercise, found)
    return _download(
        f"{sent.code}_{kind}.csv", sent.files[kind].encode(), "text/csv; charset=utf-8"
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
    found = _gate_or_404(exercise, gate)
    rows, spread = stages.assignments(exercise.public_id, found)
    pairs = stages.pairs_of(rows)
    state = workflow.gate_state(exercise.public_id, found.key)
    sent = workflow.gate_opened(*state)
    # Blind review, or a confidential gate (ruling 42): its page shows
    # Dossier IDs, never names, as its files do.
    ids_only = exercise.blind or found.confidential
    # Sorted on the server, across every page (author, 2026-11-17: as
    # Review Robin's tables; a page shows 200 of up to 2,980).
    order = paging.parse_sort(sort)
    shown = stages.sorted_pairs(stages.matching(pairs, q, ids_only), order, found, sent, ids_only)
    # An offset that is not a whole number reads as the first page.
    start = int(offset) if re.fullmatch(r"-?[0-9]+", offset) else 0
    where = paging.page(len(shown), start, paging.PAGE_SIZE)
    return render(
        request,
        "applydesk/operator/gate_evaluations.html",
        area=OPERATOR_LOBBY,
        crumb_child=f"Gate {found.number} · {found.label or 'Untitled gate'}",
        nav=exercise_nav(exercise.public_id, "evaluations"),
        status=workflow.status_row(exercise),
        exercise=exercise,
        gate=found,
        ids_only=ids_only,
        state=state,
        sent=sent,
        order=order,
        sort_text=paging.sort_text,
        plain_click=paging.plain_click,
        shift_click=paging.shift_click,
        sort_badge=paging.sort_badge,
        # Its operations' data (AD1G rung 6b), for a gate still the
        # operator's to change.
        ev_data=None
        if sent
        else stages.page_data(exercise.public_id, found, rows, ids_only, q, where.offset == 0),
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
        bundle=_bundle(request, exercise, found),
    )


def _download(name: str, body: bytes, media_type: str) -> Response:
    return Response(
        body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _csv(name: str, table: extract.Table) -> Response:
    return _download(name, extract.csv_bytes(table), "text/csv; charset=utf-8")


def _zip(name: str, body: bytes) -> Response:
    return _download(name, body, "application/zip")


def _pick(value: str, allowed: tuple[str, ...]) -> str:
    """A chip's value from the query, else its default (the first)."""
    return value if value in allowed else allowed[0]


@router.get("/exercises/{exercise_id}/extract/{file}", name="applydesk_extract_file")
def extract_file(
    exercise_id: str,
    file: str,
    rows: str = "",
    drafts: str = "",
    shape: str = "",
    applicants: str = "",
    carries: str = "",
    orows: str = "",
    sparts: str = "",
) -> Response:
    """Extract data's downloads (segment AD1J, rung 3), shaped by the
    cards' chips: ``rows`` last|all, ``drafts`` 1, ``shape`` pair|application,
    ``applicants`` names|ids (else the file's default,
    ``extract.names_by_default``), ``carries`` a ZIP's files (Extract all data's,
    or Extract setup's pages), ``orows`` the
    ZIP's outcomes rows (the Outcomes card's), ``sparts`` its setup pages
    (Extract setup's). Sample data;
    logged from AD2."""
    exercise = exercise_or_404(exercise_id)
    rows = _pick(rows, ("last", "all"))
    shape = _pick(shape, ("pair", "application"))
    names = (
        applicants == "names"
        if applicants in ("names", "ids")
        else extract.names_by_default(exercise, file)
    )
    if file == "applications.csv":
        return _csv(file, extract.applications(exercise, rows, drafts == "1"))
    if file == "outcomes.csv":
        return _csv(file, extract.outcomes(exercise, rows, names))
    if file == "alias_key.csv":
        return _csv(file, extract.alias_key(exercise))
    gate = re.fullmatch(r"gate_([1-9][0-9]*)\.csv", file)
    if gate:
        found = extract.gate_file(exercise, int(gate.group(1)), shape, names)
        if found is None:
            raise HTTPException(status_code=404)  # no such gate, or not sent
        return _csv(*found)
    if file == "gates.zip":
        body = extract.gates_zip(exercise, shape, names)
        return _zip(extract.zip_name(exercise, "gates"), body)
    if file == "all.zip":
        wanted = frozenset(carries.split(",")) if carries else extract.DEFAULT_CARRIES
        body = extract.all_zip(
            exercise,
            wanted & extract.CARRIES,
            names,
            rows,
            drafts == "1",
            shape,
            _pick(orows, ("last", "all")),
            (frozenset(sparts.split(",")) if sparts else extract.SETUP_PARTS) & extract.SETUP_PARTS,
        )
        return _zip(extract.zip_name(exercise, "extract"), body)
    if file == "setup.zip":
        parts = frozenset(carries.split(",")) if carries else extract.SETUP_PARTS
        body = extract.setup_zip(exercise, parts & extract.SETUP_PARTS)
        return _zip(extract.zip_name(exercise, "setup"), body)
    raise HTTPException(status_code=404)


def _email_sample(
    request: Request, exercise: sample_data.Exercise, email: workflow.Email
) -> dict[str, str]:
    """Preview's sample for an email (segment AD1L), its link under the
    mount (a view's shaping, kept out of the template)."""
    values = workflow.sample_values(exercise, email)
    if "exercise_url" in values:
        values["exercise_url"] = url_path(request, values["exercise_url"])
    return values


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
        extract=extract.of(exercise) if section == "extract" else None,
        dossiers_csv=extract.zip_name(exercise, "dossiers", ext="csv"),
        redraft_closed=workflow.closed_by(exercise.public_id) if section == "dossiers" else {},
        today=timeline.short(timeline.TODAY),
        all_names=extract.names_by_default(exercise, "all.zip"),
        alias_columns=extract.ALIAS_KEYS,
        setup_files=extract.SETUP_FILES,
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
        local_value=stages.local_value,
        stage_status=functools.partial(locks.stage_status, exercise),
        publish_problems=functools.partial(locks.publish_problems, exercise),
        stage_lock=functools.partial(locks.stage_lock, exercise),
        item_lock=functools.partial(locks.item_lock, exercise),
        form_lock=locks.form_lock(exercise),
        revert_warnings=functools.partial(locks.revert_warnings, exercise),
        outstanding=functools.partial(locks.outstanding, exercise),
        STATUS_CHIP=locks.STATUS_CHIP,
        now_value=stages.local_value(locks.NOW),
        cells_lock=functools.partial(locks.cells_lock, exercise),
        release_lock=functools.partial(locks.release_lock, exercise),
        blind_lock=locks.blind_lock(exercise),
        window=stages.window,
        window_text=stages.window_text,
        blank_stage=stages.Stage(0, "", None),
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
        blank_outcome=stages.Outcome("", 0, "", (), None, ""),
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
        email_defaults=workflow.DEFAULT_TEMPLATES,
        email_fields=workflow.EMAIL_FIELDS,
        tag_help=workflow.TAG_HELP,
        email_sample=functools.partial(_email_sample, request, exercise),
        sends=functools.partial(workflow.sends, exercise.public_id),
        form_state=workflow.form_state(exercise),
    )
