"""The operator's pages, `/operator/exercises/…` (segment AD1, item 2):
built on sample data, working on screen; nothing saved until AD2."""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse, Response

from applydesk import (
    db,
    directory,
    extract,
    gate,
    handoff,
    home_ops,
    locks,
    operators,
    paging,
    people,
    process_save,
    sample_data,
    scratch,
    scratch_panels,
    stages,
    team,
    timeline,
    workflow,
)
from applydesk import exercises as exercise_store
from applydesk.ids import RowId, row_id
from applydesk.lookups import dossier_or_404, exercise_or_404
from applydesk.web import (
    OPERATIONS_PAGES,
    OPERATOR_LOBBY,
    SETUP_PAGES,
    exercise_nav,
    render,
    root_path,
    url_path,
)
from cordware.identity import Identity, current_identity

router = APIRouter(prefix="/operator", dependencies=[Depends(gate.require_exercise_operator)])

#: An exercise's operator pages beyond Home, each a partial of
#: `operator/section.html`, headed by its tab's label (ruling 14).
SECTIONS: dict[str, str] = dict(SETUP_PAGES + OPERATIONS_PAGES)


@router.get("/exercises", name="applydesk_exercises")
def exercises(request: Request, session: Session = Depends(db.get_session)) -> Response:
    shown = sample_data.newest_first(
        e
        for e in exercise_store.stored_all(sample_data.exercises())
        if gate.operates(request, e.public_id)
    )
    return render(
        request,
        "applydesk/operator/exercises.html",
        area=OPERATOR_LOBBY,
        exercises=shown,
        is_scratch=scratch.is_scratch,
        scratch_limit=scratch.LIMIT,
        scratch_said=SAID.get(request.query_params.get("said", ""), ""),
        exercise_status=locks.exercise_status,
        status_counts=locks.status_counts(shown),
        stage_position=workflow.stage_position,
        timezone=sample_data.timezone,
        utc_offset=sample_data.utc_offset,
        created_label=sample_data.created_label,
        lobby_tags=sample_data.all_tags(shown),
        # Created by is the Owner on record until AD2B records who
        # created each exercise (the author, 2026-11-22).
        owners=operators.owner_labels(session, [e.public_id for e in shown]),
    )


def _same_site(request: Request) -> None:
    """A scratch exercise's posts come from Apply Desk's own pages: a
    browser naming another site is refused (as Review Robin's handoffs)."""
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        raise HTTPException(status_code=403)


#: The Lobby's status line, by the key its redirect carries: the page
#: shows only these, so a link cannot put words on it (findings
#: 2026-11-20 S11, ruled: a message key, not the text).
SAID: dict[str, str] = {
    **scratch.CREATE_REFUSALS,
    "not_made": "The scratch exercise could not be made.",
    "discarded": "The scratch exercise was discarded.",
}


def _to_lobby(request: Request, said: str = "") -> RedirectResponse:
    """The Lobby, with ``said`` a key of :data:`SAID`."""
    path = "/operator/exercises" + (("?" + urlencode({"said": said})) if said else "")
    return RedirectResponse(url_path(request, path), status_code=303)


@router.post("/exercises/new", name="applydesk_exercise_new")
async def exercise_new(request: Request) -> Response:
    """*New exercise* (segment AD1N, ruling 59): a blank draft named by the
    operator, held in memory for this browser, its Home next."""
    _same_site(request)
    body = await request.body()
    if len(body) > scratch.MAX_BODY:
        raise HTTPException(status_code=413)
    name = parse_qs(body.decode("utf-8", "replace")).get("name", [""])[0]
    browser = scratch.token() or scratch.new_token()
    try:
        made = scratch.create(browser, name)
    except scratch.Refused as why:
        return _to_lobby(request, why.key if why.key in SAID else "not_made")
    # Its row and Owner off the event loop (bug sweep at the AD2A close);
    # the scratch exercise is discarded however that fails.
    try:
        owned = await run_in_threadpool(gate.own_new_exercise, request, made.exercise.public_id)
    except OperationalError as error:  # SQLite: another change holds the file
        scratch.discard(browser, made.exercise.public_id)
        if not db.is_busy(error):
            raise
        return _to_lobby(request, "not_made")
    except Exception:
        scratch.discard(browser, made.exercise.public_id)
        raise
    if not owned:
        scratch.discard(browser, made.exercise.public_id)
        return _to_lobby(request, "not_made")
    reply = RedirectResponse(
        url_path(request, f"/operator/exercises/{made.exercise.public_id}"), status_code=303
    )
    reply.raw_headers.append(
        scratch.cookie_header(browser, root_path(request), request.url.scheme == "https")
    )
    return reply


@router.post("/exercises/{exercise_id}/discard", name="applydesk_exercise_discard")
def exercise_discard(request: Request, exercise_id: str) -> Response:
    """*Discard* on the Lobby: a scratch exercise forgotten."""
    _same_site(request)
    exercise = exercise_or_404(exercise_id)
    if not scratch.discard(scratch.token(), exercise.public_id):
        raise HTTPException(status_code=404)
    return _to_lobby(request, "discarded")


_ELIGIBILITY = ("Open to all signed in", "Invitation only", "Not set")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class _Refusal(scratch.Refused):
    """A Details refusal naming the field it is about, so the card points
    there rather than at Name (cold read)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _details(exercise: sample_data.Exercise, v: dict[str, Any]) -> dict[str, Any]:
    """Details as Lock sends them, checked as the card checks them; the
    reason for the first fault, else the fields for ``scratch.update``."""
    text = {
        k: v.get(k) for k in ("name", "code", "description", "contact", "timezone", "eligibility")
    }
    if not all(isinstance(x, str) for x in text.values()) or not isinstance(v.get("blind"), bool):
        raise scratch.Refused("The details are malformed.")
    name, code = str(text["name"]).strip(), str(text["code"]).strip()
    if not name or len(name) > 200:
        raise _Refusal("name", "A name of 1 to 200 characters is needed.")
    if len(code) > 40:
        raise _Refusal("code", "An exercise code is at most 40 characters.")
    clash = next(
        (
            e
            for e in sample_data.exercises()
            if code and e.public_id != exercise.public_id and e.code.lower() == code.lower()
        ),
        None,
    )
    if clash:
        raise _Refusal("code", f"{code} is already {clash.name}'s code.")
    contact = str(text["contact"]).strip()
    if len(str(text["description"]).strip()) > 2000:
        raise _Refusal("description", "A description is at most 2,000 characters.")
    if contact and not _EMAIL.fullmatch(contact):
        raise _Refusal("contact", "A help contact is an email address.")
    zone = str(text["timezone"])
    if zone not in sample_data.TIMEZONES:
        raise _Refusal("timezone", "That timezone is not offered.")
    if text["eligibility"] not in _ELIGIBILITY:
        raise _Refusal("eligibility", "Who may apply is not one of the choices.")
    return {
        "name": name,
        "code": code,
        "summary": str(text["description"]).strip(),
        "help_contact": contact,
        "timezone": "" if zone == sample_data.DEFAULT_TIMEZONE else zone,
        "eligibility": text["eligibility"],
        "blind": v["blind"],
    }


#: What a scratch post past ``scratch.MAX_BODY`` is told (cold read: the
#: plan's "past a limit the page says so").
_TOO_LARGE = "Not saved: a page posts at most 256 KiB to a scratch exercise."


async def _scratch_json(request: Request, exercise_id: str) -> tuple[sample_data.Exercise, Any]:
    """A Setup page's post into a scratch exercise (segment AD1N): from
    Apply Desk's own page, JSON, at most ``scratch.MAX_BODY``; 404 for an
    exercise that is not this browser's scratch one."""
    _same_site(request)
    exercise = exercise_or_404(exercise_id)
    if not scratch.is_scratch(exercise.public_id):
        raise HTTPException(status_code=404)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="Not saved: the page sent no JSON.")
    body = await request.body()
    if len(body) > scratch.MAX_BODY:
        raise HTTPException(status_code=413, detail=_TOO_LARGE)
    try:
        return exercise, json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400) from None


_CARD_KINDS = ("field", "section", "pagebreak")
_CARD_TEXT = {
    "label": 500,
    "help": 2000,
    "min": 40,
    "max": 40,
    "step": 40,
    "options": 2000,
    "ratio_w": 6,
    "ratio_h": 6,
    "pool": 80,
}


def _made_pools(cards: Any, known: dict[str, Any]) -> set[str]:
    """The panels a Form snapshot's questions name that the page made
    with *+ New panel…* (``new-1``), not yet the exercise's."""
    if not isinstance(cards, list):
        return set()
    return {
        pool
        for c in cast(list[Any], cards)
        if isinstance(c, dict)
        and isinstance(pool := cast(dict[str, Any], c).get("pool"), str)
        and pool.startswith("new-")
        and pool not in known
    }


def _form(sent: Any, exercise_id: str, renamed: dict[str, str]) -> dict[str, Any]:
    """The form as Form's *Save* sends it (``applydeskFormSnapshot``),
    checked card by card and kept in ``FormCard``'s shape; a panel the
    page made is named by the key ``renamed`` gives it."""
    if not isinstance(sent, dict):
        raise scratch.Refused("The form is malformed.")
    got = cast(dict[str, Any], sent)
    title, description, cards = got.get("title", ""), got.get("description", ""), got.get("cards")
    if (
        not isinstance(title, str)
        or not isinstance(description, str)
        or not isinstance(cards, list)
    ):
        raise scratch.Refused("The form is malformed.")
    if len(title.strip()) > 200:
        raise scratch.Refused("The form's title is at most 200 characters.")
    if len(description.strip()) > 4000:
        raise scratch.Refused("The form's description is at most 4,000 characters.")
    if len(cast(list[Any], cards)) > 200:
        raise scratch.Refused("A form holds at most 200 cards.")
    types = {k for k, _ in sample_data.CARD_TYPES}
    kept: list[dict[str, Any]] = []
    for n, raw in enumerate(cast(list[Any], cards), start=1):
        if not isinstance(raw, dict):
            raise scratch.Refused(f"Card {n} is malformed.")
        card = cast(dict[str, Any], raw)
        kind = card.get("kind")
        # A string first: a list or object would fail ``in`` on a set
        # unhashable, a 500 (findings 2026-11-20 S9).
        if not isinstance(kind, str) or kind not in _CARD_KINDS:
            raise scratch.Refused(f"Card {n} is of no known kind.")
        if kind != "field":
            label = card.get("label", "")
            if not isinstance(label, str):
                raise scratch.Refused(f"Card {n} is malformed.")
            if len(label) > _CARD_TEXT["label"]:
                raise scratch.Refused(f"Card {n}'s label is too long.")
            kept.append({"kind": kind, "label": label})
            continue
        if not isinstance(card.get("type"), str) or card.get("type") not in types:
            raise scratch.Refused(f"Card {n}'s type is not one of the choices.")
        out: dict[str, Any] = {"kind": "field", "type": card["type"]}
        for key, cap in _CARD_TEXT.items():
            value = card.get(key, "")
            if not isinstance(value, str) or len(value) > cap:
                raise scratch.Refused(f"Card {n}'s {key} is malformed or too long.")
            out[key] = value
        for key in ("exclusive", "required", "shown"):
            if not isinstance(card.get(key), bool):
                raise scratch.Refused(f"Card {n} is malformed.")
            out[key] = card[key]
        out["pool"] = out["pool"] or "institution"
        out["pool"] = renamed.get(out["pool"], out["pool"])
        if out["pool"] not in sample_data.people_pools(exercise_id) and out["pool"] not in set(
            renamed.values()
        ):
            raise scratch.Refused(f"Card {n} chooses from no panel this exercise has.")
        out["ratio_w"] = out["ratio_w"] or "4"
        out["ratio_h"] = out["ratio_h"] or "5"
        kept.append(out)
    return {"title": title.strip(), "description": description.strip(), "cards": kept}


@router.post("/exercises/{exercise_id}/form", name="applydesk_exercise_form_save")
async def exercise_form_save(request: Request, exercise_id: str) -> Response:
    """Form's *Save* on a scratch exercise (segment AD1N rung 3): the cards
    kept in memory for this browser, so Process, Preview and the applicant
    pages read them."""
    exercise, sent = await _scratch_json(request, exercise_id)
    try:
        got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
        wanted = _made_pools(got.get("cards"), sample_data.people_pools(exercise.public_id))
        # A panel made with *+ New panel…* joins the exercise's panels
        # (rung 5), kept with the form or not at all.
        renamed, panels = scratch_panels.adopt(exercise.public_id, got.get("pools"), wanted)
        form = _form(sent, exercise.public_id, renamed)
        scratch_panels.keep(exercise.public_id, panels)
        scratch.save_page(exercise.public_id, "form", form)
    except (scratch.Refused, scratch_panels.Refused) as why:
        return JSONResponse({"error": str(why)}, status_code=400)
    # A panel it adopted has a key of its own now: the page reloads to
    # name it so, or its next Save would offer it again (cold read).
    return JSONResponse({"saved": True, "reload": bool(renamed)})


@router.post("/exercises/{exercise_id}/process", name="applydesk_exercise_process_save")
async def exercise_process_save(request: Request, exercise_id: str) -> Response:
    """Process's *Save* on a scratch exercise (segment AD1N rung 4): its
    stages, gates and outcomes, their rules, the emails each item ticks,
    and each stage's Draft or Published, kept for this browser."""
    exercise, sent = await _scratch_json(request, exercise_id)
    # A page opened before Process last saved holds keys that may now name
    # other columns, and the templates follow keys: refused before anything
    # changes (Codex on #4028).
    opened = cast(dict[str, Any], sent).get("revision") if isinstance(sent, dict) else None
    if opened != workflow.process_revision(exercise.public_id):
        return JSONResponse(
            {"error": "Process was saved since this page opened: reload it to save."},
            status_code=400,
        )
    try:
        # A panel made with *+ New panel…* joins the exercise's panels
        # (rung 5), kept with the process or not at all.
        wanted = process_save.made_panels(sent, exercise.public_id)
        made = cast(dict[str, Any], sent).get("pools") if isinstance(sent, dict) else None
        renamed, panels = scratch_panels.adopt(exercise.public_id, made, wanted)
        kept = process_save.build(sent, exercise.public_id, renamed)
        scratch_panels.keep(exercise.public_id, panels)
        scratch.save_page(exercise.public_id, "process", kept)
        # Emails keeps templates by outcome key: they follow the renumbering.
        workflow.rekey_templates(exercise.public_id, process_save.keys_of(sent))
        scratch.save_page(
            exercise.public_id,
            workflow.REVISION_PAGE,
            workflow.process_revision(exercise.public_id) + 1,
        )
    except (process_save.Refused, scratch.Refused, scratch_panels.Refused) as why:
        return JSONResponse({"error": str(why)}, status_code=400)
    # Gates and outcomes are renumbered on every save, and a panel it
    # adopted keyed anew: the page reloads to hold the keys kept.
    return JSONResponse({"saved": True, "reload": True, "strict": True})


@router.post("/exercises/{exercise_id}/panels", name="applydesk_exercise_panels_save")
async def exercise_panels_save(request: Request, exercise_id: str) -> Response:
    """Panels' *Save* on a scratch exercise (segment AD1N rung 5): its
    panels and roster, kept for this browser, so Form's questions and
    Process's gates pick from them."""
    exercise, sent = await _scratch_json(request, exercise_id)
    try:
        in_use = frozenset(stages.panel_uses(exercise.public_id))
        kept = scratch_panels.build(sent, exercise.public_id, in_use)
        scratch.save_page(exercise.public_id, scratch_panels.PAGE, kept)
    except (scratch_panels.Refused, scratch.Refused) as why:
        return JSONResponse({"error": str(why)}, status_code=400)
    # A panel made on the page has its own key now: the page reloads to
    # hold it, or its next Save would key it anew (cold read).
    return JSONResponse({"saved": True, "reload": True})


@router.post("/exercises/{exercise_id}/emails", name="applydesk_exercise_email_save")
async def exercise_email_save(request: Request, exercise_id: str) -> Response:
    """An Emails card's *Save* on a scratch exercise (segment AD1N rung 6):
    one template, by the item and audience Process owes it for, kept for
    this browser, so the card, the status row and Home read it."""
    exercise, sent = await _scratch_json(request, exercise_id)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    item, audience = got.get("item"), got.get("audience")
    subject, body = got.get("subject"), got.get("body")
    owed = next(
        (
            e
            for e in workflow.emails(exercise.public_id)
            if (e.item, e.audience, e.name) == (item, audience, got.get("name"))
        ),
        None,
    )
    # A page opened before Process last saved names outcomes by keys that
    # may now be another's, even under the same name (two stages can share
    # one): refused by the revision it was opened at (Codex on #4028).
    stale = got.get("revision") != workflow.process_revision(exercise.public_id)
    if stale or owed is None or not isinstance(subject, str) or not isinstance(body, str):
        return JSONResponse(
            {"error": "That email is not one Process owes now: reload Emails."},
            status_code=400,
        )
    if len(subject) > 300 or len(body) > 20000:
        return JSONResponse(
            {"error": "A subject is at most 300 characters, a body 20,000."}, status_code=400
        )
    bad = workflow.foreign_tags(owed.kind, subject + "\n" + body)
    if bad:
        tags = ", ".join(f"${t}" for t in bad)
        return JSONResponse({"error": f"{tags} is not a tag of this email."}, status_code=400)
    try:
        kept = dict(workflow.scratch_templates(exercise.public_id) or {})
        kept[(owed.item, owed.audience)] = (subject, body)
        scratch.save_page(exercise.public_id, workflow.SCRATCH_PAGE, kept)
    except scratch.Refused as why:
        return JSONResponse({"error": str(why)}, status_code=400)
    return JSONResponse({"saved": True, "written": bool(subject.strip() and body.strip())})


@router.post("/exercises/{exercise_id}/details", name="applydesk_exercise_details")
async def exercise_details(request: Request, exercise_id: str) -> Response:
    """Details' *Lock* on a scratch exercise (segment AD1N): the fields
    kept in memory for this browser; a sample exercise has no such post."""
    _same_site(request)
    exercise = exercise_or_404(exercise_id)
    if not scratch.is_scratch(exercise.public_id):
        raise HTTPException(status_code=404)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="Not saved: the page sent no JSON.")
    body = await request.body()
    if len(body) > scratch.MAX_BODY:
        raise HTTPException(status_code=413, detail=_TOO_LARGE)
    try:
        sent = json.loads(body)
        if not isinstance(sent, dict):
            raise scratch.Refused("The details are malformed.")
        changes = _details(exercise, cast(dict[str, Any], sent))
        scratch.update(exercise.public_id, **changes)
    except (ValueError, scratch.Refused) as why:
        reason = str(why) if isinstance(why, scratch.Refused) else "The details are malformed."
        field = why.field if isinstance(why, _Refusal) else "name"
        return JSONResponse({"error": reason, "field": field}, status_code=400)
    return JSONResponse({"saved": True})


#: The Operators card's status line, by the key its redirect carries (as
#: the Lobby's): a link cannot put words on it.
OPS_SAID: dict[str, str] = {
    "added": "Added as an operator.",
    "removed": "Removed. They can be added again.",
    "owner": "Ownership handed over; the former Owner stays an operator.",
    "not_owner": "Only the exercise's Owner changes its operators.",
    "not_listed": "Only someone on the operator list can be added or made Owner.",
    "already_operator": "Already an operator.",
    "already_owner": "Already the Owner.",
    "is_owner": "The Owner cannot be removed; hand ownership over first.",
    "not_operator": "Add them as an operator first.",
    "gone": "That person is no longer on record; look again.",
    "changed": "Someone else changed the operators just now; look again and retry.",
}


def _ops_back(request: Request, exercise_id: str, said: str) -> RedirectResponse:
    path = f"/operator/exercises/{exercise_id}?{urlencode({'ops_said': said})}#operators"
    return RedirectResponse(url_path(request, path), status_code=303)


def _ops_change(
    request: Request,
    exercise_id: str,
    change: Callable[[Session, str, Identity, int], None],
    person_id: int,
    done: str,
) -> Response:
    """One change to the exercise's operators (`team.py`), a refusal
    turned into a status key."""
    _same_site(request)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    session = db.new_session()
    try:
        # Bind the actor and commit first, so no person row is held while
        # the change waits on the exercise's lock (bug sweep: a deadlock
        # with an Owner's change on Postgres).
        people.resolve(session, identity)
        session.commit()
        change(session, exercise_id, identity, person_id)
        session.commit()
    except operators.Refused as why:
        session.rollback()
        return _ops_back(request, exercise_id, why.key if why.key in OPS_SAID else "changed")
    except (IntegrityError, OperationalError) as error:
        # A concurrent change won (the one-Owner index; SQLite's busy file).
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return _ops_back(request, exercise_id, "changed")
    finally:
        session.close()
    return _ops_back(request, exercise_id, done)


@router.post("/exercises/{exercise_id}/operators/add", name="applydesk_operators_add")
async def operators_add(request: Request, exercise_id: str) -> Response:
    body = await request.body()
    if len(body) > 1024:
        raise HTTPException(status_code=413)
    raw = parse_qs(body.decode("utf-8", "replace")).get("person_id", [""])[0]
    person_id = row_id(raw)
    if person_id is None:
        raise HTTPException(status_code=400)
    # The change itself off the event loop (as the operator list's, Codex on #4113).
    return await run_in_threadpool(_ops_change, request, exercise_id, team.add, person_id, "added")


@router.post(
    "/exercises/{exercise_id}/operators/{person_id}/remove", name="applydesk_operators_remove"
)
def operators_remove(request: Request, exercise_id: str, person_id: RowId) -> Response:
    return _ops_change(request, exercise_id, team.remove, person_id, "removed")


@router.post(
    "/exercises/{exercise_id}/operators/{person_id}/owner", name="applydesk_operators_owner"
)
def operators_owner(request: Request, exercise_id: str, person_id: RowId) -> Response:
    return _ops_change(request, exercise_id, team.make_owner, person_id, "owner")


@router.get("/exercises/{exercise_id}", name="applydesk_exercise_home")
def exercise_home(request: Request, exercise_id: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    tl = timeline.of(exercise)
    op_q = request.query_params.get("op_q", "").strip()
    session = db.new_session()
    try:
        ops = team.card(session, exercise.public_id, current_identity(request))
        op_found = team.candidates(session, exercise.public_id, op_q) if op_q and ops.manage else []
        session.commit()
    finally:
        session.close()
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
        ops=home_ops.of(exercise),
        missing=sample_data.setup_missing(exercise),
        operators_card=ops,
        op_q=op_q,
        op_found=op_found,
        op_min_query=directory.MIN_QUERY,
        ops_said=OPS_SAID.get(request.query_params.get("ops_said", ""), ""),
        timezones=sample_data.TIMEZONES,
        default_contact=sample_data.DEFAULT_HELP_CONTACT,
        blind_lock=locks.blind_lock(exercise),
        stage_rows=locks.stage_rows(exercise),
        STATUS_CHIP=locks.STATUS_CHIP,
        # Every other exercise's code and name, so Details refuses a
        # clashing code on the page (segment AD1I Semantics).
        other_codes=[
            [e.code, e.name]
            for e in exercise_store.stored_all(sample_data.exercises())
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
    or a draft exercise. The digits are bounded, so a number past
    Python's integer-string limit is a 404, not a 500 (findings
    2026-11-20 S8)."""
    number = re.fullmatch(r"gate_([1-9][0-9]{0,8})", gate)
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


def _people(pairs: tuple[stages.Pair, ...]) -> tuple[tuple[str, str, int], ...]:
    """Each paired evaluator once, in the pairs' order: name, email and
    how many pairs they hold (the card's Progress rows)."""
    seen: dict[str, list[object]] = {}
    for p in pairs:
        if p.email:
            seen.setdefault(p.email.lower(), [p.name, p.email.lower(), 0])
            got = seen[p.email.lower()]
            got[2] = cast(int, got[2]) + 1
    return tuple((str(n), str(e), cast(int, c)) for n, e, c in seen.values())


def _rr_me(request: Request) -> str:
    """Review Robin's ``/me``, where an invited evaluator signs in
    (ruling 24): beside Apply Desk under the host's mounts (`/reviewrobin`,
    segment 21D), as an absolute URL for an email."""
    mount = root_path(request)
    host = mount[: -len("/applydesk")] if mount.endswith("/applydesk") else ""
    return f"{request.url.scheme}://{request.url.netloc}{host}/reviewrobin/me"


def _rr_data(
    exercise: sample_data.Exercise,
    gate: stages.Gate,
    state: tuple[str, str],
    opened: bool,
    sent_with: handoff.Bundle,
    people: tuple[tuple[str, str, int], ...],
    rr_me: str,
) -> dict[str, object]:
    """What the Review Robin card's script needs to send and re-send in
    the tab (segment AD1M rung 4, ruling 55): the gate's state as the
    sample has it, whether only approvals stand between it and *Ready*,
    the bundle's name, code and digest, and the other gates' codes, which
    a send may not take (ruling 56); and for rung 5, each evaluator's
    progress as a pull would read it, and what an invitation or a
    reminder says, with Review Robin's ``/me`` as its link."""
    plan = stages.plan_of(exercise.public_id)
    return {
        "ex": exercise.public_id,
        "key": gate.key,
        "state": state[0],
        "why": state[1] if state[0] == "Not ready" else "",
        "opened": opened,
        "approveOnly": workflow.awaits_approval(exercise.public_id, gate),
        "name": sent_with.name,
        "code": sent_with.code,
        "digest": sent_with.digest(),
        "others": [
            [c.key, f"Gate {c.number}", handoff.session_code(exercise, c)]
            for c in plan.columns
            if isinstance(c, stages.Gate) and c.key != gate.key
        ],
        "line": state[1],
        "progress": [
            [email, n, done] for _, email, n, done in workflow.progress_of(*state, people)
        ],
        "exercise": exercise.name,
        "gate": gate.label or f"Gate {gate.number}",
        "help": sample_data.help_contact(exercise),
        "rrMe": rr_me,
    }


@router.get(
    "/exercises/{exercise_id}/evaluations/{gate}/{kind}.csv", name="applydesk_gate_bundle_file"
)
def gate_bundle_file(request: Request, exercise_id: str, gate: str, kind: str) -> Response:
    """One of the four files a gate would be sent with (segment AD1M),
    named as Review Robin names its own: ``<code>_<kind>.csv``. Guarded
    against formulas here, for the person who opens it; the handoff sends
    the bytes unguarded (findings 2026-11-20 S12)."""
    exercise = exercise_or_404(exercise_id)
    found = _gate_or_404(exercise, gate)
    if kind not in handoff.KINDS:
        raise HTTPException(status_code=404)
    sent = _bundle(request, exercise, found)
    return _download(
        f"{sent.code}_{kind}.csv",
        extract.guarded(sent.files[kind]).encode(),
        "text/csv; charset=utf-8",
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
    sent_with = _bundle(request, exercise, found)
    rows, spread = stages.assignments(exercise.public_id, found)
    pairs = stages.pairs_of(rows)
    people = _people(pairs)
    state = workflow.gate_state(exercise.public_id, found.key)
    sent = workflow.gate_opened(*state)
    # Blind review, or a confidential gate (ruling 42): its page shows
    # Dossier IDs, never names, as its files do.
    ids_only = exercise.blind or found.confidential
    # Sorted on the server, across every page (author, 2026-11-17: as
    # Review Robin's tables; a page shows 200 of up to 2,980).
    order = paging.parse_sort(sort)
    shown = stages.sorted_pairs(stages.matching(pairs, q, ids_only), order, found, sent, ids_only)
    # An offset that is not a whole number reads as the first page. Only
    # its first 12 characters are read, which keeps its sign and leaves a
    # long one past the last page, where it clamps: past Python's 4,300
    # digits ``int`` would raise (findings 2026-11-20 S8).
    start = int(offset[:12]) if re.fullmatch(r"-?[0-9]+", offset) else 0
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
        bundle=sent_with,
        people=people,
        rr_data=_rr_data(exercise, found, state, sent, sent_with, people, _rr_me(request)),
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


@router.get("/exercises/{exercise_id}/dossiers/{dossier_id}", name="applydesk_operator_dossier")
def operator_dossier(request: Request, exercise_id: str, dossier_id: str) -> Response:
    """A dossier as the operator sees it (ruling 64, U20; segment AD1P):
    under Dossiers, its application, its row's gates and outcomes, and what
    evaluators read; *View as evaluators see it* opens the dossier's `/me`
    page, the one evaluators open, in a new tab, as Review Robin's *Open
    reviewer surface*. A draft has no dossier (ruling 32): a 404."""
    exercise = exercise_or_404(exercise_id)
    app = dossier_or_404(exercise, dossier_id)
    if app.state == "Draft":  # no dossier until it is submitted (ruling 32)
        raise HTTPException(status_code=404)
    plan = stages.plan_of(exercise.public_id)
    row = next((r for r in plan.rows if r.application.public_id == app.public_id), None)
    return render(
        request,
        "applydesk/operator/dossier.html",
        area=OPERATOR_LOBBY,
        crumb_child=f"Dossier {dossier_id}",
        nav=exercise_nav(exercise.public_id, "dossiers"),
        status=workflow.status_row(exercise),
        exercise=exercise,
        application=app,
        columns=plan.columns,
        cells=row.cells if row else {},
        going_on=stages.going_on,
        shown=extract.form_answers(exercise, app)[0],
    )


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
    gate = re.fullmatch(r"gate_([1-9][0-9]{0,8})\.csv", file)
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
        emails=(owed := workflow.emails(exercise.public_id)),
        tag_rows=workflow.tag_rows(owed),
        email_defaults=workflow.DEFAULT_TEMPLATES,
        email_text=functools.partial(workflow.template_text, exercise.public_id),
        process_revision=workflow.process_revision(exercise.public_id),
        email_fields=workflow.EMAIL_FIELDS,
        tag_help=workflow.TAG_HELP,
        email_sample=functools.partial(_email_sample, request, exercise),
        sends=functools.partial(workflow.sends, exercise.public_id),
        form_state=workflow.form_state(exercise),
    )
