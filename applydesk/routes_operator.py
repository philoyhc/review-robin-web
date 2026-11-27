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
    allowlist,
    candidates,
    clock,
    db,
    directory,
    email_store,
    extract,
    form_store,
    gate,
    handoff,
    home_ops,
    invitees,
    lobby,
    locks,
    operators,
    paging,
    panels_store,
    people,
    process_save,
    process_store,
    rules,
    sample_data,
    stages,
    team,
    timeline,
    timeline_checks,
    workflow,
)
from applydesk import exercises as exercise_store
from applydesk.ids import RowId, is_public_id, row_id
from applydesk.lookups import dossier_or_404, exercise_or_404
from applydesk.models import Person
from applydesk.web import (
    MAX_BODY,
    OPERATIONS_PAGES,
    OPERATOR_LOBBY,
    SETUP_PAGES,
    exercise_nav,
    render,
    root_path,
    url_path,
)
from cordware.graph import GraphError
from cordware.identity import Identity, current_identity

router = APIRouter(prefix="/operator", dependencies=[Depends(gate.require_exercise_operator)])

#: An exercise's operator pages beyond Home, each a partial of
#: `operator/section.html`, headed by its tab's label (ruling 14).
SECTIONS: dict[str, str] = dict(SETUP_PAGES + OPERATIONS_PAGES)


@router.get("/exercises", name="applydesk_exercises")
def exercises(request: Request) -> Response:
    """The Operator Lobby (segment AD2B rung 6): the live exercises the
    viewer operates, sorted, tagged and filtered by the query string."""
    # Each row's values and the revision its Save names, from one read.
    found = [
        s
        # Only the viewer's are read further (cold read, AD2G).
        for s in exercise_store.stored_all_at(
            tuple(e for e in sample_data.exercises() if gate.operates(request, e.public_id))
        )
        if s.live
    ]
    mine = [s.exercise for s in found]
    # Your role on each (segment AD2O), from the viewer's own grants.
    roles = {e.public_id: "Owner" if gate.owns(request, e.public_id) else "Operator" for e in mine}
    query = lobby.Query.parse(request.query_params, request.query_params.getlist("tag"))
    shown = lobby.apply(mine, query, roles)
    return render(
        request,
        "applydesk/operator/exercises.html",
        area=OPERATOR_LOBBY,
        exercises=shown,
        total=len(mine),
        query=query,
        base=url_path(request, "/operator/exercises"),
        back=query.href(""),
        revisions={s.exercise.public_id: s.revision for s in found},
        most_made=exercise_store.MOST_MADE,
        lobby_said=SAID.get(request.query_params.get("said", ""), ""),
        exercise_status=locks.exercise_status,
        is_draft=locks.is_draft,
        status_counts=locks.status_counts(mine),
        stage_position=workflow.stage_position,
        timezone=sample_data.timezone,
        utc_offset=sample_data.utc_offset,
        created_label=sample_data.created_label,
        lobby_tags=sample_data.all_tags(mine),
        roles=roles,
    )


@router.get("/exercises/archived", name="applydesk_exercises_archived")
def exercises_archived(request: Request) -> Response:
    """The Archive (segment AD2B): the archived exercises the viewer
    operates, tagged and filtered as the Lobby, newest archived first,
    each with *Restore*. Registered before ``/exercises/{exercise_id}``,
    which would otherwise take the path."""
    when = exercise_store.archived_at()
    found = [s for s in sample_data.exercises() if s.public_id in when]
    mine = [
        e for e in exercise_store.stored_all(tuple(found)) if gate.operates(request, e.public_id)
    ]
    query = lobby.Query.parse(request.query_params, request.query_params.getlist("tag"))
    shown = sorted(
        (e for e in mine if lobby.matches(e, query)),
        key=lambda e: when[e.public_id],
        reverse=True,
    )
    return render(
        request,
        "applydesk/operator/exercises_archived.html",
        area=OPERATOR_LOBBY,
        exercises=shown,
        total=len(mine),
        query=query,
        base=url_path(request, "/operator/exercises/archived"),
        archived={
            e.public_id: clock.stamp(when[e.public_id], sample_data.timezone(e)) for e in shown
        },
        created_label=sample_data.created_label,
        lobby_tags=sample_data.all_tags(mine),
        roles={
            e.public_id: "Owner" if gate.owns(request, e.public_id) else "Operator" for e in shown
        },
        said=SAID.get(request.query_params.get("said", ""), ""),
    )


#: The panel's actions, as its buttons post them.
PANEL_ACTIONS = ("save", "add_tags", "remove_tags", "duplicate", "archive", "delete")


#: The most exercises one panel action takes: every ordinary exercise is
#: listed now (segment AD2G), not only the samples and a browser's five.
MOST_TICKED = 500


@router.post("/exercises/panel", name="applydesk_exercises_panel")
async def exercises_panel(request: Request) -> Response:
    """The Lobby panel's actions (segment AD2B rung 6) on the ticked
    exercises; the Lobby again, its query kept, saying how it went."""
    gate.same_site(request)
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413)
    form = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
    action = form.get("action", [""])[0]
    ids = [i for i in form.get("id", []) if is_public_id(i)][:MOST_TICKED]
    if action not in PANEL_ACTIONS or not ids:
        raise HTTPException(status_code=400)
    back = _lobby_query(form.get("back", [""])[0])
    if action == "duplicate":
        return await _duplicate(request, ids[0], back)
    said = await run_in_threadpool(_panel_change, request, action, ids, form)
    return _back_to_lobby(request, back, said)


def _lobby_query(raw: str) -> str:
    """The Lobby's query a panel post came from, rebuilt from its parts
    so nothing else rides back (Semantics: never echoed)."""
    pairs = parse_qs(raw.lstrip("?"))
    flat = {k: v[0] for k, v in pairs.items() if v}
    return lobby.Query.parse(flat, pairs.get("tag", [])).href("")


def _back_to_lobby(request: Request, back: str, said: str) -> RedirectResponse:
    joiner = "&" if back else "?"
    path = "/operator/exercises" + back + (f"{joiner}{urlencode({'said': said})}" if said else "")
    return RedirectResponse(url_path(request, path), status_code=303)


def _panel_change(request: Request, action: str, ids: list[str], form: dict[str, list[str]]) -> str:
    """One panel action's transaction; the status key it ends with."""
    if not all(gate.operates(request, i) for i in ids):
        return "gone"
    identity = current_identity(request)
    if identity is None:
        return "gone"
    session = db.new_session()
    try:
        actor = team.actor_for(session, identity)
        session.commit()  # bind the actor first, as `_ops_change` does

        def first(key: str) -> str:
            return form.get(key, [""])[0]

        if action == "save":
            opened = int(first("revision")) if first("revision").isdigit() else -1
            exercise_store.save_panel(
                session,
                ids[0],
                first("name"),
                first("code"),
                exercise_store.parse_tags(first("tags")),
                opened,
                actor.person,
            )
        elif action in ("add_tags", "remove_tags"):
            tags = exercise_store.parse_tags(first("tags"))
            if not tags:
                return "no_tags"
            exercise_store.retag(session, ids, tags, actor.person, add=action == "add_tags")
        elif action == "archive":
            exercise_store.archive(session, ids, actor)
        else:
            if first("confirm") != "yes":
                return "delete_unconfirmed"
            exercise_store.delete(session, ids, actor)
        session.commit()
    except exercise_store.Refused as why:
        session.rollback()
        return why.key if why.key in SAID else "refused"
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return "code_taken" if "uq_exercise_live_code" in str(error.orig) else "stale"
    finally:
        session.close()
    gate.forget_viewer(request)
    return {
        "save": "saved",
        "add_tags": "tagged",
        "remove_tags": "untagged",
    }.get(action, action + "d")


async def _duplicate(request: Request, source_id: str, back: str) -> Response:
    """*Duplicate settings only*: a new exercise, its row taking the
    source's settings and tags; its Home next (as *New exercise*)."""
    if not gate.operates(request, source_id):
        return _back_to_lobby(request, back, "gone")
    # Off the event loop: an ordinary exercise is a database read (cold read).
    source = await run_in_threadpool(sample_data.exercise, source_id)
    if source is None:
        return _back_to_lobby(request, back, "gone")
    made, said = await run_in_threadpool(_make, request, f"Copy of {source.name}"[:200], source_id)
    if made is None:
        return _back_to_lobby(request, back, said)
    return RedirectResponse(url_path(request, f"/operator/exercises/{made}"), status_code=303)


def _make(request: Request, name: str, source_id: str | None = None) -> tuple[str | None, str]:
    """*New exercise* or *Duplicate*'s transaction (segment AD2G): the new
    exercise's public ID, else None and the Lobby's status key."""
    identity = current_identity(request)
    if identity is None:
        return None, "not_made"
    session = db.new_session()
    try:
        actor = team.actor_for(session, identity)
        session.commit()  # bind the actor first, as `_ops_change` does
        made = exercise_store.make(session, actor, name, source_id=source_id)
        session.commit()
        public_id = made.public_id
    except exercise_store.Refused as why:
        session.rollback()
        return None, why.key if why.key in SAID else "not_made"
    except OperationalError as error:  # SQLite: another change holds the file
        session.rollback()
        if not db.is_busy(error):
            raise
        return None, "not_made"
    finally:
        session.close()
    gate.forget_viewer(request)  # their grants changed
    return public_id, ""


@router.post("/exercises/archived/restore", name="applydesk_exercises_restore")
async def exercises_restore(request: Request) -> Response:
    """*Restore* on the Archive (segment AD2B rung 6), Owner-only."""
    gate.same_site(request)
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413)
    public_id = parse_qs(body.decode("utf-8", "replace")).get("id", [""])[0]
    if not is_public_id(public_id):
        raise HTTPException(status_code=400)
    said = await run_in_threadpool(_restore, request, public_id)
    path = "/operator/exercises/archived?" + urlencode({"said": said})
    return RedirectResponse(url_path(request, path), status_code=303)


def _restore(request: Request, public_id: str) -> str:
    identity = current_identity(request)
    if identity is None or not gate.operates(request, public_id):
        return "gone"
    session = db.new_session()
    try:
        actor = team.actor_for(session, identity)
        session.commit()
        exercise_store.restore(session, public_id, actor)
        session.commit()
    except exercise_store.Refused as why:
        session.rollback()
        return why.key if why.key in SAID else "refused"
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return "stale"
    finally:
        session.close()
    return "restored"


#: The Lobby's status line, by the key its redirect carries: the page
#: shows only these, so a link cannot put words on it (findings
#: 2026-11-20 S11, ruled: a message key, not the text).
SAID: dict[str, str] = {
    **exercise_store.MAKE_REFUSALS,
    "not_made": "The exercise could not be made.",
    # The panel and the Archive (segment AD2B rung 6).
    "saved": "Saved.",
    "tagged": "Tags added.",
    "untagged": "Tags removed.",
    "archived": "Archived: see Go to Archive.",
    "deleted": "Deleted.",
    "restored": "Restored to the Lobby.",
    "no_tags": "Type the tags first.",
    "delete_unconfirmed": "Not deleted: tick Yes, delete first.",
    "not_owner": "Only an exercise's Owner may archive, restore or delete it.",
    "code_taken": "Not saved: another live exercise has that code.",
    "code_fixed": "Not saved: a published exercise's code is fixed until it is re-published.",
    "code_long": "Not saved: an exercise code is at most 40 characters.",
    "name": "Not saved: a name of 1 to 200 characters is needed.",
    "tag_long": "Not saved: a tag is at most 40 characters.",
    "tags_many": "Not saved: an exercise carries at most 20 tags.",
    "archived_readonly": "Not saved: an archived exercise is read-only. Restore it first.",
    "left": "You left the exercise.",
    "restore_taken": "Not restored: another live exercise now has its code. Change one first.",
    "stale": "Not saved: someone else changed it just now. Look again and retry.",
    "gone": "That exercise is no longer on record, or not yours to change.",
    "refused": "Not done.",
}


def _to_lobby(request: Request, said: str = "") -> RedirectResponse:
    """The Lobby, with ``said`` a key of :data:`SAID`."""
    path = "/operator/exercises" + (("?" + urlencode({"said": said})) if said else "")
    return RedirectResponse(url_path(request, path), status_code=303)


@router.post("/exercises/new", name="applydesk_exercise_new")
async def exercise_new(request: Request) -> Response:
    """*New exercise* (segment AD2G): a blank draft named by the operator,
    its row and Owner made in one transaction, its Home next."""
    gate.same_site(request)
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413)
    name = parse_qs(body.decode("utf-8", "replace")).get("name", [""])[0]
    made, said = await run_in_threadpool(_make, request, name)
    if made is None:
        return _to_lobby(request, said)
    return RedirectResponse(url_path(request, f"/operator/exercises/{made}"), status_code=303)


_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class _Refusal(Exception):
    """A Details refusal naming the field it is about, so the card points
    there rather than at Name (cold read)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _details(v: dict[str, Any]) -> dict[str, Any]:
    """Details as Lock sends them, checked as the card checks them; the
    reason for the first fault, else the fields in the sample's words (a
    clashing code is the database's to refuse, `exercises.save_details`)."""
    text = {k: v.get(k) for k in ("name", "code", "description", "contact", "timezone")}
    if not all(isinstance(x, str) for x in text.values()) or not isinstance(v.get("blind"), bool):
        raise _Refusal("name", "The details are malformed.")
    name, code = str(text["name"]).strip(), str(text["code"]).strip()
    if not name or len(name) > 200:
        raise _Refusal("name", "A name of 1 to 200 characters is needed.")
    if max(len(code), len(code.casefold())) > 40:  # its key is casefolded ("ß" is "ss")
        raise _Refusal("code", "An exercise code is at most 40 characters.")
    contact = str(text["contact"]).strip()
    if len(str(text["description"]).strip()) > 2000:
        raise _Refusal("description", "A description is at most 2,000 characters.")
    if contact and not _EMAIL.fullmatch(contact):
        raise _Refusal("contact", "A help contact is an email address.")
    zone = str(text["timezone"])
    if zone not in sample_data.TIMEZONES:
        raise _Refusal("timezone", "That timezone is not offered.")
    return {
        "name": name,
        "code": code,
        "summary": str(text["description"]).strip(),
        "help_contact": contact,
        "timezone": "" if zone == sample_data.DEFAULT_TIMEZONE else zone,
        "blind": v["blind"],
    }


#: What a page post past ``MAX_BODY`` is told (cold read: the
#: plan's "past a limit the page says so").
_TOO_LARGE = "Not saved: a page posts at most 256 KiB."


async def _page_json(request: Request) -> Any:
    """A Setup page's post (segment AD2C): from Apply Desk's own page,
    JSON, at most ``MAX_BODY``; the exercise is the caller's to
    look up, off the event loop."""
    gate.same_site(request)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="Not saved: the page sent no JSON.")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413, detail=_TOO_LARGE)
    try:
        return json.loads(body)
    except (ValueError, RecursionError):  # too deep a body reads as malformed
        raise HTTPException(status_code=400) from None


def _made_pools(cards: Any, known: dict[str, Any]) -> set[str]:
    """The panels a Form snapshot's questions name that the page made
    with *+New panel…* (``new-1``), not yet the exercise's."""
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
    """The form as Form's *Save* sends it, checked (`form_store.parse`);
    a panel the page made is named by the key ``renamed`` gives it."""
    return form_store.parse(sent, sample_data.people_pools(exercise_id), renamed)


@router.post("/exercises/{exercise_id}/form", name="applydesk_exercise_form_save")
async def exercise_form_save(request: Request, exercise_id: str) -> Response:
    """Form's *Save* (segment AD1N rung 3; every exercise since AD2D): the
    form kept in the database (`form_store.save`), guarded by the revision
    the page opened at."""
    sent = await _page_json(request)
    return await run_in_threadpool(_save_form, request, exercise_id, sent)


def _save_form(request: Request, exercise_id: str, sent: Any) -> Response:
    """Form's *Save*, past the request's own checks: the transaction. A
    panel made with *+New panel…* is stored with it (segment AD2E), or
    not at all."""
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    opened = got.get("revision")
    if not isinstance(opened, int) or isinstance(opened, bool):
        return JSONResponse({"error": "The form is malformed."}, status_code=400)
    session = db.new_session()
    try:
        actor = people.resolve(session, identity)
        session.commit()
        # The exercise's lock before the panels are read, held until the
        # form is kept, so a Panels save cannot retire a panel a question
        # names in between (Codex on #4171).
        panels_store.lock(session, exercise.public_id)
        wanted = _made_pools(got.get("cards"), sample_data.people_pools(exercise.public_id))
        renamed = panels_store.adopt(session, exercise.public_id, got.get("pools"), wanted, actor)
        form = _form(sent, exercise.public_id, renamed)
        # Both read under the lock, as they stand once any Process save
        # before this one has landed (cold read).
        revision = form_store.save(
            session,
            exercise.public_id,
            form,
            opened,
            actor,
            published=lambda: locks.form_lock(exercise).fixed,
            in_use=lambda: stages.form_reads(stages.plan_of(exercise.public_id)),
        )
        kept = form_store.load(session, exercise.public_id)
        keyed = kept is None or [c.key for c in kept.cards] != [c["key"] for c in form["cards"]]
        session.commit()
    except panels_store.Refused as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=400)
    except form_store.Refused as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=409 if why.key == "stale" else 400)
    except (IntegrityError, OperationalError) as error:
        # A concurrent save won: on SQLite the row lock is the file's, so
        # two first saves can meet on a key's unique index.
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return JSONResponse(
            {"error": "Not saved: someone else saved just now; reload and retry."},
            status_code=409,
        )
    finally:
        session.close()
    # A card or a panel keyed anew on saving: the page reloads to hold its
    # keys, or its next Save would key it again. Edits made while the save
    # was on its way cannot be saved before that reload ("strict").
    reload = keyed or bool(renamed)
    return JSONResponse({"saved": True, "reload": reload, "strict": reload, "revision": revision})


@router.post("/exercises/{exercise_id}/process", name="applydesk_exercise_process_save")
async def exercise_process_save(request: Request, exercise_id: str) -> Response:
    """Process's *Save* (segment AD1N rung 4; every exercise since AD2C):
    its stages, gates and outcomes and their rules, kept in the database
    (`process_store.save`), and the emails each item ticks
    (`email_store.save_sends`, segment AD2L)."""
    sent = await _page_json(request)
    return await run_in_threadpool(_save_process, request, exercise_id, sent)


def _save_process(request: Request, exercise_id: str, sent: object) -> Response:
    """Process's *Save*, past the request's own checks: the transaction."""
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    opened = got.get("revision")
    if not isinstance(opened, int) or isinstance(opened, bool):
        return JSONResponse({"error": "The process is malformed."}, status_code=400)
    session = db.new_session()
    try:
        # Bind the actor and commit first, as Details does.
        actor = people.resolve(session, identity)
        session.commit()
        # The exercise's row lock before its panels are read, so a Panels
        # save cannot retire one between the check and this save (AD2E).
        panels_store.lock(session, exercise.public_id)
        # A panel made with *+New panel…* joins the exercise's panels,
        # stored with the process or not at all (segment AD2E).
        wanted = process_save.made_panels(sent, exercise.public_id)
        renamed = panels_store.adopt(session, exercise.public_id, got.get("pools"), wanted, actor)
        taken = process_store.taken_keys(session, exercise.public_id)
        built, ticks = process_save.build(sent, exercise.public_id, renamed, taken)
        process_store.save(session, exercise.public_id, built, opened, actor)
        # How many dossiers one person may hold, one setting for the
        # exercise shown on each populating item (segment AD2K).
        most = process_save.per_person(sent)
        if most is not None:
            candidates.set_per_person(session, exercise.public_id, most, actor)
        # The Form's Who may apply (ruling 84, segment AD2I).
        who = process_save.who_may_apply(sent)
        if who is not None:
            exercise_store.set_eligibility(session, exercise, who, actor)
        # The emails each item ticks, kept with the timeline (segment AD2L).
        email_store.save_sends(session, exercise.public_id, ticks)
        session.commit()
    except (
        process_save.Refused,
        panels_store.Refused,
        candidates.Refused,
        exercise_store.Refused,
    ) as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=400)
    except process_store.Refused as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=409 if why.key == "stale" else 400)
    except (IntegrityError, OperationalError) as error:
        # A concurrent save won: on SQLite the row lock is the file's, so
        # two first saves can meet on a key's unique index (cold read).
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return JSONResponse(
            {"error": "Not saved: someone else saved just now; reload and retry."},
            status_code=409,
        )
    finally:
        session.close()
    # A column the page added took the server's key, and a panel it
    # adopted keyed anew: the page reloads to hold the keys kept.
    return JSONResponse({"saved": True, "reload": True, "strict": True})


@router.post("/exercises/{exercise_id}/process/problems", name="applydesk_process_problems")
async def process_problems(request: Request, exercise_id: str) -> Response:
    """What each rule on the Process page reads amiss, by its column's key
    (ruling 78: the server checks rules, the page shows it). The page's
    snapshot, as *Save* sends it; nothing is kept."""
    sent = await _page_json(request)
    return await run_in_threadpool(_check_process, exercise_id, sent)


def _check_process(exercise_id: str, sent: Any) -> Response:
    exercise = exercise_or_404(exercise_id)
    made = process_save.made_panels(sent, exercise.public_id)
    try:
        built, _ = process_save.build(sent, exercise.public_id, {k: k for k in made}, checking=True)
    except process_save.Refused as why:
        return JSONResponse({"error": str(why)}, status_code=400)
    plan = stages.Plan(stages.form_keyed(built, exercise.public_id), (), exercise.public_id)
    forms = sample_data.list_questions(exercise.public_id)
    return JSONResponse(
        {"problems": {c.key: list(stages.rule_problems(plan, c, forms)) for c in plan.columns}}
    )


@router.get("/exercises/{exercise_id}/candidates/search", name="applydesk_candidates_search")
def candidates_search(request: Request, exercise_id: str, q: str = "") -> Response:
    """The Candidates item's people search (ruling 75): people on record,
    then the directory's not on record; those listed as often as allowed
    left out (segment AD2K)."""
    return _people_search(request, exercise_id, q, candidates)


@router.get("/exercises/{exercise_id}/invitees/search", name="applydesk_invitees_search")
def invitees_search(request: Request, exercise_id: str, q: str = "") -> Response:
    """The Form's invite list's people search (ruling 84, segment AD2I), as
    Create dossiers'; those invited already left out."""
    return _people_search(request, exercise_id, q, invitees)


def _people_search(request: Request, exercise_id: str, q: str, svc: Any) -> Response:
    exercise = exercise_or_404(exercise_id)
    session = db.new_session()
    try:
        listed = svc.full(session, exercise.public_id)
        found = allowlist.search(session, q, lambda: directory.for_request(request), exclude=listed)
    finally:
        session.close()
    return JSONResponse(
        {
            "on_record": [
                {"id": p.id, "name": p.display_name or "", "email": p.email or ""}
                for p in found.on_record
            ],
            "directory": [
                {
                    "object_id": u.id,
                    "name": u.display_name,
                    "address": u.mail or u.user_principal_name,
                    # The sign-in name the search may have matched, so the
                    # typeahead can offer it (Codex on #4255).
                    "upn": u.user_principal_name or "",
                }
                for u in found.in_directory
            ],
            "directory_failed": bool(found.directory_failed),
        }
    )


@router.post("/exercises/{exercise_id}/candidates", name="applydesk_candidates_change")
async def candidates_change(request: Request, exercise_id: str) -> Response:
    """The Candidates item's changes (rulings 77, 83): add an entry for
    someone picked in the search, remove an entry, or upload a CSV; the
    list as it now stands."""
    sent = await _page_json(request)
    return await run_in_threadpool(_change_list, request, exercise_id, sent, candidates)


@router.post("/exercises/{exercise_id}/invitees", name="applydesk_invitees_change")
async def invitees_change(request: Request, exercise_id: str) -> Response:
    """The Form's invite list's changes (ruling 84, segment AD2I): invite
    someone picked in the search, take one off, or upload a CSV; the list
    as it now stands."""
    sent = await _page_json(request)
    return await run_in_threadpool(_change_list, request, exercise_id, sent, invitees)


def _listed_json(rows: tuple[candidates.Listed, ...]) -> list[dict[str, object]]:
    return [
        {
            "id": c.id,
            "person_id": c.person_id,
            "title": c.title,
            "name": c.name,
            "email": c.email,
            "via": c.via,
            "verified": c.verified,
            "added": clock.short(c.added_at),
        }
        for c in rows
    ]


def _change_list(request: Request, exercise_id: str, sent: Any, svc: Any) -> Response:
    """A people list's change, Create dossiers' or the Form's invitees'."""
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    action = got.get("action")
    session = db.new_session()
    said = ""
    bad: tuple[str, ...] = ()
    try:
        actor = people.resolve(session, identity)
        session.commit()
        count = got.get("count")
        if (
            svc is candidates
            and count is not None
            and (not isinstance(count, int) or isinstance(count, bool))
        ):
            # Codex on #4265: a count that is not a whole number refuses the
            # add rather than falling back to one dossier.
            raise candidates.Refused(
                f"Dossiers per person is a whole number from 1 to {candidates.MAX_PER_PERSON}."
            )

        def put(person: Person) -> str:
            # Create dossiers' Add makes as many dossiers as its box says
            # (author, 2026-11-27); an invitee is one.
            if isinstance(count, int) and not isinstance(count, bool) and svc is candidates:
                n = candidates.add_many(session, exercise.public_id, person, "search", actor, count)
                return f"Added {n} {'dossier' if n == 1 else 'dossiers'}."
            return (
                "Added."
                if svc.add(session, exercise.public_id, person, "search", actor)
                else svc.already(session, exercise.public_id)
            )

        if action == "add" and isinstance(got.get("person_id"), int):
            person = session.get(Person, got["person_id"])
            if person is None:
                raise candidates.Refused("That person is no longer on record; search again.")
            said = put(person)
        elif (
            action == "add"
            and isinstance(got.get("object_id"), str)
            and isinstance(got.get("address"), str)
        ):
            tenant = (identity.tenant_id or "").strip()
            if not tenant:
                raise candidates.Refused("The directory cannot be searched from this sign-in.")
            address, object_id = got["address"], got["object_id"]
            found = next(
                (
                    u
                    for u in directory.for_request(request).find_users(address)
                    if u.id == object_id
                ),
                None,
            )
            if found is None:
                raise candidates.Refused("The directory no longer has that account; search again.")
            person = people.from_directory(session, found, tenant, actor)
            said = put(person)
        elif action == "remove" and isinstance(got.get("entry_id"), int):
            said = (
                "Removed."
                if svc.remove(session, exercise.public_id, got["entry_id"], actor)
                else "Not on the list: removed already."
            )
        elif action == "csv" and isinstance(got.get("text"), str):
            done = svc.import_csv(session, exercise.public_id, got["text"], actor)
            said = (
                f"{done.added} added"
                + (f", {done.already} listed already" if done.already else "")
                + "."
            )
            bad = done.bad
        else:
            raise candidates.Refused("That change is malformed.")
        session.commit()
        listed = svc.listing(session, exercise.public_id)
    except candidates.Refused as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=400)
    except GraphError:
        session.rollback()
        return JSONResponse(
            {"error": "The directory could not be reached; try again."}, status_code=400
        )
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return JSONResponse(
            {"error": "Someone else changed the list just now; try again."}, status_code=409
        )
    finally:
        session.close()
    return JSONResponse({"said": said, "bad": list(bad), "candidates": _listed_json(listed)})


def _per_person_of(public_id: str) -> int:
    session = db.new_session()
    try:
        return candidates.per_person(session, public_id)
    finally:
        session.close()


def _invitees_of(public_id: str) -> tuple[candidates.Listed, ...]:
    session = db.new_session()
    try:
        return invitees.listing(session, public_id)
    finally:
        session.close()


def _candidates_of(public_id: str) -> tuple[candidates.Listed, ...]:
    session = db.new_session()
    try:
        return candidates.listing(session, public_id)
    finally:
        session.close()


#: The largest table *Apply rules* sends, in bytes: every row's settable
#: cells, a few dozen bytes each.
_PROPOSAL_BODY = 4 * 1024 * 1024


@router.post("/exercises/{exercise_id}/dossiers/proposal", name="applydesk_dossiers_proposal")
async def dossiers_proposal(request: Request, exercise_id: str) -> Response:
    """Dossiers' *Apply rules* (ruling 78): what the server's rule engine
    would change in the table the page sends (each row's settable cells,
    value and hand mark), as a proposal. Changes nothing."""
    gate.same_site(request)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415)
    body = await request.body()
    if len(body) > _PROPOSAL_BODY:
        raise HTTPException(status_code=413)
    try:
        sent = json.loads(body)
    except (ValueError, RecursionError):  # too deep a body reads as malformed
        raise HTTPException(status_code=400) from None
    return await run_in_threadpool(_propose, exercise_id, sent)


def _table_sent(v: Any) -> dict[str, dict[str, tuple[str, bool]]] | None:
    """The page's cells, ``{app: {key: [value, hand]}}``, else None."""
    if not isinstance(v, dict):
        return None
    out: dict[str, dict[str, tuple[str, bool]]] = {}
    for app, cells in cast(dict[Any, Any], v).items():
        if not isinstance(app, str) or not isinstance(cells, dict):
            return None
        own: dict[str, tuple[str, bool]] = {}
        for key, cell in cast(dict[Any, Any], cells).items():
            if not (
                isinstance(key, str) and isinstance(cell, list) and len(cast(list[Any], cell)) == 2
            ):
                return None
            value, hand = cast(list[Any], cell)
            if (
                not isinstance(value, str) or not isinstance(hand, bool) or len(value) > 500
            ):  # an outcome value's limit
                return None
            own[key] = (value, hand)
        out[app] = own
    return out


def _propose(exercise_id: str, sent: Any) -> Response:
    exercise = exercise_or_404(exercise_id)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    table = _table_sent(got.get("cells"))
    only, hand = got.get("only_pending"), got.get("replace_hand")
    if table is None or not isinstance(only, bool) or not isinstance(hand, bool):
        return JSONResponse({"error": "The table sent is malformed."}, status_code=400)
    plan = stages.plan_of(exercise.public_id)
    columns = rules.columns_of(plan, lambda gate: locks.cells_lock(exercise, gate).fixed)
    rows = rules.rows_of(plan, functools.partial(sample_data.answers, exercise.public_id), table)
    proposal = rules.propose(columns, rows, only_pending=only, replace_hand=hand)
    return JSONResponse(
        {
            "changes": [
                {"app": c.app, "key": c.key, "from": c.old, "to": c.new} for c in proposal.changes
            ],
            "skipped": list(proposal.skipped),
        }
    )


@router.post("/exercises/{exercise_id}/panels", name="applydesk_exercise_panels_save")
async def exercise_panels_save(request: Request, exercise_id: str) -> Response:
    """Panels' *Save* (segment AD1N rung 5; every exercise since AD2E): its
    panels and roster, kept in the database (`panels_store.save`), so
    Form's questions and Process's gates pick from them."""
    sent = await _page_json(request)
    return await run_in_threadpool(_save_panels, request, exercise_id, sent)


def _save_panels(request: Request, exercise_id: str, sent: object) -> Response:
    """Panels' *Save*, past the request's own checks: the transaction."""
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    opened = got.get("revision")
    if not isinstance(opened, int) or isinstance(opened, bool):
        return JSONResponse({"error": "The panels are malformed."}, status_code=400)
    session = db.new_session()
    try:
        actor = people.resolve(session, identity)
        session.commit()
        revision = panels_store.save(
            session,
            exercise.public_id,
            sent,
            opened,
            actor,
            lambda: frozenset(stages.panel_uses(exercise.public_id)),
        )
        session.commit()
    except panels_store.Refused as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=409 if why.key == "stale" else 400)
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return JSONResponse(
            {"error": "Not saved: someone else saved just now; reload and retry."},
            status_code=409,
        )
    finally:
        session.close()
    # A panel made on the page has its own key now: the page reloads to
    # hold it, or its next Save would key it anew (cold read). The new
    # revision rides along, so a page that kept edits made during the save
    # can save them next (AD2E cold read).
    return JSONResponse({"saved": True, "reload": True, "revision": revision})


@router.post("/exercises/{exercise_id}/emails", name="applydesk_exercise_email_save")
async def exercise_email_save(request: Request, exercise_id: str) -> Response:
    """An Emails card's *Save* (segment AD1N rung 6; every exercise since
    AD2L): one template, by the item and audience Process owes it for,
    kept in the database (`email_store.save_template`)."""
    sent = await _page_json(request)
    return await run_in_threadpool(_save_email, request, exercise_id, sent)


def _save_email(request: Request, exercise_id: str, sent: Any) -> Response:
    """An Emails card's *Save*, past the request's own checks."""
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    item, audience, name = got.get("item"), got.get("audience"), got.get("name")
    subject, body = got.get("subject"), got.get("body")
    opened, version = got.get("revision"), got.get("version")
    if (
        not isinstance(subject, str)
        or not isinstance(body, str)
        or not isinstance(version, int)
        or isinstance(version, bool)
        or not isinstance(opened, int)
        or isinstance(opened, bool)
    ):
        return JSONResponse({"error": "The email is malformed."}, status_code=400)

    def owed_now() -> workflow.Email | None:
        return next(
            (
                e
                for e in workflow.emails(exercise.public_id)
                if (e.item, e.audience, e.name) == (item, audience, name)
            ),
            None,
        )

    owed = owed_now()
    if owed is None:
        return JSONResponse(
            {"error": "That email is not one Process owes now: reload Emails."},
            status_code=400,
        )
    bad = workflow.foreign_tags(owed.kind, subject + "\n" + body)
    if bad:
        tags = ", ".join(f"${t}" for t in bad)
        return JSONResponse({"error": f"{tags} is not a tag of this email."}, status_code=400)
    session = db.new_session()
    try:
        actor = people.resolve(session, identity)
        session.commit()
        # Under the exercise's lock: a page opened before Process last saved
        # names outcomes by keys that may now be another's, even under the
        # same name (Codex on #4028); and the email must still be owed.
        kept = email_store.save_template(
            session,
            exercise.public_id,
            (owed.item, owed.audience),
            subject,
            body,
            version,
            actor,
            owed=lambda: (
                opened == workflow.process_revision(exercise.public_id) and owed_now() is not None
            ),
        )
        session.commit()
    except email_store.Refused as why:
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=409 if why.key == "stale" else 400)
    except panels_store.Refused as why:
        # The exercise deleted after the page's lookup (cold read).
        session.rollback()
        return JSONResponse({"error": str(why)}, status_code=400)
    except (IntegrityError, OperationalError) as error:
        # Two first saves of one template can meet on its unique index.
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return JSONResponse(
            {"error": "Not saved: someone else saved just now; reload and retry."},
            status_code=409,
        )
    finally:
        session.close()
    return JSONResponse(
        {"saved": True, "written": bool(subject.strip() and body.strip()), "version": kept}
    )


@router.post("/exercises/{exercise_id}/details", name="applydesk_exercise_details")
async def exercise_details(request: Request, exercise_id: str) -> Response:
    """Details' *Lock* (segment AD2B rung 3): saved on the exercise's row,
    any exercise the viewer operates, refused if someone saved since the
    page opened (the revision it sends). The body is read here; the
    database is reached off the event loop (Codex on #4137)."""
    gate.same_site(request)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="Not saved: the page sent no JSON.")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413, detail=_TOO_LARGE)
    try:
        sent = json.loads(body)
    except (ValueError, RecursionError):  # too deep a body reads as malformed
        sent = None
    return await run_in_threadpool(_save_details, request, exercise_id, sent)


def _locks_hold(exercise: sample_data.Exercise, values: dict[str, Any]) -> None:
    """What the page locks, the server refuses too (cold read): a published
    exercise's code and who may apply (G2), and blind review once a stage
    holding a gate is published (`locks.blind_lock`)."""
    if values["blind"] != exercise.blind and locks.blind_lock(exercise).fixed:
        raise _Refusal("blind", locks.blind_lock(exercise).reason)
    # By its state or its stages (Codex on cordware#230).
    if not locks.is_draft(exercise) and values["code"] != (exercise.code or None):
        raise _Refusal("code", "Fixed once published: a change waits for re-publishing.")


def _save_details(request: Request, exercise_id: str, sent: object) -> Response:
    """Details' *Lock*, past the request's own checks: the transaction."""
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None:
        raise HTTPException(status_code=404)
    try:
        if not isinstance(sent, dict):
            raise _Refusal("name", "The details are malformed.")
        got = cast(dict[str, Any], sent)
        opened = got.get("revision")
        if not isinstance(opened, int) or isinstance(opened, bool):
            raise _Refusal("name", "The details are malformed.")
        # Who may apply is the Form's now (ruling 84): Details keeps it.
        values = exercise_store.details_from_page(
            {**_details(got), "eligibility": exercise.eligibility}
        )
        _locks_hold(exercise, values)
    except _Refusal as why:
        return JSONResponse({"error": str(why), "field": why.field}, status_code=400)
    session = db.new_session()
    try:
        # Bind the actor and commit first, as `_ops_change` does.
        actor = people.resolve(session, identity)
        session.commit()
        revision = exercise_store.save_details(session, exercise, values, opened, actor)
        session.commit()
    except exercise_store.Refused as why:
        session.rollback()
        status = 409 if why.key == "stale" else 400
        return JSONResponse({"error": str(why), "field": why.field}, status_code=status)
    except (IntegrityError, OperationalError) as error:
        # Another live exercise took the code, or a concurrent save won.
        session.rollback()
        if not db.lost_a_race(error):
            raise
        if "uq_exercise_live_code" in str(error.orig):
            return JSONResponse(
                {
                    "error": "Not saved: another live exercise took that code just now.",
                    "field": "code",
                },
                status_code=409,
            )
        return JSONResponse(
            {"error": "Not saved: someone else saved just now; reload and retry.", "field": "name"},
            status_code=409,
        )
    finally:
        session.close()
    return JSONResponse({"saved": True, "revision": revision})


#: The Operators card's status line, by the key its redirect carries (as
#: the Lobby's): a link cannot put words on it.
OPS_SAID: dict[str, str] = {
    "added": "Added as an operator.",
    "removed": "Removed. They can be added again.",
    "owner": "Ownership transferred: they are an Owner, and you an operator.",
    "not_owner": "Only an Owner of this exercise changes its Owners and operators.",
    "not_listed": "Only someone on the operator list can be added or made Owner.",
    "already_operator": "Already an operator.",
    "already_owner": "Already an Owner.",
    "is_owner": "An Owner is made an operator before being removed.",
    "not_operator": "Add them as an operator first.",
    "gone": "That person is no longer on record; look again.",
    "changed": "Someone else changed the operators just now; look again and retry.",
    # The ownership moves (segment AD2O).
    "made_owner": "Made an Owner.",
    "demoted": "Made an operator.",
    "stepped_down": "You stepped down to operator.",
    "left": "You left the exercise.",
    "last_owner": "The only Owner stays one: make another Owner or transfer first.",
    "not_an_owner": "They are not an Owner of this exercise.",
    "owner_leaving": "An Owner steps down to operator before leaving.",
    "not_self": "Only you can take yourself off.",
    "archived": "Archived: restore it to change who runs it.",
    "sole_owner": "The only Owner of a live exercise: hand its ownership over first.",
}


#: Home's line after the form's move (ruling 76), by the key its redirect
#: carries.
FORM_SAID: dict[str, str] = {
    "open": "The form is open.",
    "closed": "The form is closed.",
    "draft": "A draft's form opens once the exercise is published.",
    "form_state": "The form has moved since this page opened: see where it stands now.",
    "no_form": "This exercise has no application form.",
    "archived": "Archived: restore it to change it.",
    "changed": "Someone else changed it just now; try again.",
    "unsaved": "Process cannot be saved as it stands: save it there first.",
}


@router.post("/exercises/{exercise_id}/form/move", name="applydesk_form_move")
async def form_move(request: Request, exercise_id: str) -> Response:
    """*Open form* or *Close form*, Home's next step (ruling 76): the
    form's state moves forward, audited."""
    gate.same_site(request)
    body = await request.body()
    if len(body) > 1024:
        raise HTTPException(status_code=413)
    to = parse_qs(body.decode("utf-8", "replace")).get("to", [""])[0]
    return await run_in_threadpool(_move_form, request, exercise_id, to)


def _move_form(request: Request, exercise_id: str, to: str) -> Response:
    exercise = exercise_or_404(exercise_id)
    identity = current_identity(request)
    if identity is None or to not in process_store.FORM_MOVES:
        raise HTTPException(status_code=404 if identity is None else 400)
    said = to
    session = db.new_session()
    try:
        actor = people.resolve(session, identity)
        session.commit()
        published = locks.exercise_status(exercise) != "Draft"  # by its stages
        process_store.move_form(session, exercise.public_id, to, published, actor)
        session.commit()
    except process_store.Refused as why:
        session.rollback()
        said = why.key if why.key in FORM_SAID else "changed"
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        said = "changed"
    finally:
        session.close()
    path = f"/operator/exercises/{exercise_id}?{urlencode({'form_said': said})}"
    return RedirectResponse(url_path(request, path), status_code=303)


def _ops_back(request: Request, exercise_id: str, said: str) -> RedirectResponse:
    path = f"/operator/exercises/{exercise_id}?{urlencode({'ops_said': said})}#operators"
    return RedirectResponse(url_path(request, path), status_code=303)


def _ops_change(
    request: Request,
    exercise_id: str,
    change: Callable[[Session, str, Identity, int], None],
    person_id: int,
    done: str,
    *,
    to_lobby: bool = False,
) -> Response:
    """One change to the exercise's operators (`team.py`), a refusal
    turned into a status key. `to_lobby`: done, the viewer no longer runs
    the exercise (Leave), so the Lobby says so."""
    gate.same_site(request)
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
    gate.forget_viewer(request)  # their grants changed (plan's Semantics)
    if to_lobby:
        return _to_lobby(request, done)
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
    """*Transfer ownership* (the old *Make owner*; its path is kept)."""
    return _ops_change(request, exercise_id, team.transfer, person_id, "owner")


@router.post(
    "/exercises/{exercise_id}/operators/{person_id}/make-owner",
    name="applydesk_operators_make_owner",
)
def operators_make_owner(request: Request, exercise_id: str, person_id: RowId) -> Response:
    """*Make Owner*: an Owner beside the others (segment AD2O)."""
    return _ops_change(request, exercise_id, team.make_owner, person_id, "made_owner")


@router.post(
    "/exercises/{exercise_id}/operators/{person_id}/demote", name="applydesk_operators_demote"
)
def operators_demote(request: Request, exercise_id: str, person_id: RowId) -> Response:
    """*Make operator* on another Owner's row (segment AD2O)."""
    return _ops_change(request, exercise_id, team.demote, person_id, "demoted")


@router.post(
    "/exercises/{exercise_id}/operators/{person_id}/step-down",
    name="applydesk_operators_step_down",
)
def operators_step_down(request: Request, exercise_id: str, person_id: RowId) -> Response:
    """*Step down to operator* on the viewer's own row (segment AD2O)."""
    return _ops_change(request, exercise_id, team.step_down, person_id, "stepped_down")


@router.post(
    "/exercises/{exercise_id}/operators/{person_id}/leave", name="applydesk_operators_leave"
)
def operators_leave(request: Request, exercise_id: str, person_id: RowId) -> Response:
    """*Leave*: the viewer takes themself off; the Lobby next (AD2O)."""
    return _ops_change(request, exercise_id, team.leave, person_id, "left", to_lobby=True)


@router.get("/exercises/{exercise_id}", name="applydesk_exercise_home")
def exercise_home(request: Request, exercise_id: str) -> Response:
    exercise_or_404(exercise_id)
    found = sample_data.exercise(exercise_id)
    if found is None:
        raise HTTPException(status_code=404)
    # The settings and the revision Details' Lock names, from one read.
    exercise, revision = exercise_store.stored_at(found)
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
        short=clock.short,
        next_line=timeline.next_step(exercise, tl),
        # Ruling 76: Home's next step carries the form's own move.
        form_action=workflow.form_action(exercise),
        form_said=FORM_SAID.get(request.query_params.get("form_said", ""), ""),
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
        # G2's code lock (Who may apply is the Form's, ruling 84): published by its state or its
        # stages (Codex on cordware#230).
        exercise_published=not locks.is_draft(exercise),
        revision=revision,
        # Read-only until restored (the author, 2026-11-22).
        archived=exercise_store.is_archived(exercise.public_id),
        stage_rows=locks.stage_rows(exercise),
        STATUS_CHIP=locks.STATUS_CHIP,
        # The viewer's other exercises' codes and names, so Details refuses
        # a clashing code on the page (segment AD1I Semantics); a clash with
        # one they do not operate is the server's to refuse, unnamed (cold
        # read, AD2G: never another operator's names).
        other_codes=[
            [e.code, e.name]
            for e in (
                s.exercise
                for s in exercise_store.stored_all_at(
                    tuple(
                        e
                        for e in sample_data.exercises()
                        if e.public_id != exercise.public_id and gate.operates(request, e.public_id)
                    )
                )
                if s.live  # an archived or deleted exercise frees its code
            )
            if e.code
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
    """The gate a path names by its key (ruling 37, AD-48), 404 for one
    the exercise lacks or a draft exercise."""
    found = stages.gate_keyed(stages.plan_of(exercise.public_id), gate)
    # Published by its state or its stages (`locks.is_draft`, Codex on
    # cordware#230).
    if found is None or locks.is_draft(exercise):
        raise HTTPException(status_code=404)
    return found


def _old_gate_link(
    request: Request, exercise: sample_data.Exercise, gate: str, tail: str = ""
) -> RedirectResponse | None:
    """An old ``gate_<n>`` link (sent emails and bookmarks hold them)
    redirected to the gate numbered so now, its query kept: a 302, since
    a number names another gate once gates move; None for a
    path that is not one. 404 as ``_gate_or_404`` for a number naming no
    gate. The digits are bounded, so a number past Python's
    integer-string limit is a 404, not a 500 (findings 2026-11-20 S8)."""
    number = re.fullmatch(r"gate_([1-9][0-9]{0,8})", gate)
    if number is None:
        return None
    found = stages.gate_numbered(stages.plan_of(exercise.public_id), int(number.group(1)))
    if found is None or locks.is_draft(exercise):
        raise HTTPException(status_code=404)
    path = url_path(
        request, f"/operator/exercises/{exercise.public_id}/evaluations/{found.key}{tail}"
    )
    query = request.url.query
    return RedirectResponse(path + (f"?{query}" if query else ""), status_code=302)


def _bundle(request: Request, exercise: sample_data.Exercise, gate: stages.Gate) -> handoff.Bundle:
    """The gate's bundle, each ``ProfileLink`` the dossier's page as an
    absolute URL under the mount (segment AD1M)."""
    origin = f"{request.url.scheme}://{request.url.netloc}"
    return handoff.bundle(
        exercise,
        gate,
        lambda d: (
            origin + url_path(request, f"/me/exercises/{exercise.public_id}/dossiers/{d.public_id}")
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


def _rr_by_code(request: Request) -> str:
    """Where *Open in Review Robin* goes, less the session's code (segment
    23J, amended): Review Robin's ``/operator/sessions/by-code/`` beside
    Apply Desk under the host's mounts, which opens the session with that
    code for its operators. Apply Desk knows a gate's code (ruling 56), so
    the link needs no stored ``session_home_url``."""
    return _rr_me(request).removesuffix("/me") + "/operator/sessions/by-code/"


def _rr_data(
    exercise: sample_data.Exercise,
    gate: stages.Gate,
    state: tuple[str, str],
    opened: bool,
    sent_with: handoff.Bundle,
    people: tuple[tuple[str, str, int], ...],
    rr_me: str,
    rr_by_code: str = "",
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
        # Open in Review Robin, less the code (segment 23J, amended).
        "rrByCode": rr_by_code,
        "state": state[0],
        "why": state[1] if state[0] == "Not ready" else "",
        "opened": opened,
        # A field Review Robin would refuse (segment AD2S): a send or a
        # re-send is refused as Review Robin's import would refuse it, the
        # re-send included, which publishing does not guard (the
        # cumulative read).
        "fieldProblems": list(stages.field_problems(gate)),
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
    if kind not in handoff.KINDS:
        raise HTTPException(status_code=404)
    old = _old_gate_link(request, exercise, gate, f"/{kind}.csv")
    if old is not None:
        return old
    found = _gate_or_404(exercise, gate)
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
    old = _old_gate_link(request, exercise, gate)
    if old is not None:
        return old
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
        rr_data=_rr_data(
            exercise, found, state, sent, sent_with, people, _rr_me(request), _rr_by_code(request)
        ),
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
    row = next((r for r in plan.rows if r.dossier.key == app.public_id), None)
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
    gate = re.fullmatch(r"gate_([a-z][a-z0-9]{0,15})\.csv", file)  # its key (AD-48)
    if gate:
        found = extract.gate_file(exercise, gate.group(1), shape, names)
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
    # The revision before the panels it guards: a save landing between the
    # two reads makes the page stale, never newer than what it shows.
    panels_revision = panels_store.revision(exercise.public_id) if section == "panels" else 0
    form_revision = form_store.revision(exercise.public_id) if section == "form" else 0
    # Process's too, before its timeline is read (Codex on cordware#230):
    # read after, a save between would pair the old timeline with the new
    # revision, and the page's next save would overwrite it unrefused.
    process_revision = workflow.process_revision(exercise.public_id)
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
        today=clock.short(clock.today(sample_data.timezone(exercise))),
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
        panels_revision=panels_revision,
        form_revision=form_revision,
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
        # The form's List questions by key, each its label and options
        # (segment AD2D), for Process's rule editor.
        form_lists={
            key: {"label": q.label, "options": list(q.options)}
            for key, q in sample_data.list_questions(exercise.public_id).items()
        },
        # Ruling 77: the Candidates list, read where Process or Dossiers
        # draws it (segment AD2N).
        cand_list=(
            _candidates_of(exercise.public_id) if section in ("process", "dossiers") else ()
        ),
        # Ruling 84: the Form's invite list, read where Process or Invitees
        # draws it (segment AD2N).
        invitee_list=(
            _invitees_of(exercise.public_id) if section in ("process", "invitees") else ()
        ),
        # Segment AD2K: how many dossiers one person may hold, on the
        # populating item.
        per_person=_per_person_of(exercise.public_id) if section == "process" else 1,
        # The Form's Who may apply as stored (ruling 84): unset reads open.
        who_may_apply=exercise_store.eligibility_of(exercise.eligibility) or "open",
        # Segment AD2N: whether the Setup row shows Invitees, so Process
        # says to save first and Invitees says when the list is unused.
        invitees_tab=(
            invitees.tab_shown(exercise.public_id) if section in ("process", "invitees") else False
        ),
        # The timeline checked as a whole, as saved (segment AD2K).
        checked=timeline_checks.of(exercise.public_id) if section == "process" else None,
        short=clock.short,
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
        now_value=stages.local_value(clock.midday(sample_data.timezone(exercise))),
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
        field_choices=stages.FIELD_CHOICES,
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
        gate_type=stages.gate_type,
        evaluators_summary=stages.evaluators_summary,
        gate_types=stages.GATE_TYPES,
        # Published by its stages, as the gate pages read it (Codex on
        # cordware#230): Evaluations' and the gate cards' links follow it.
        exercise_published=not locks.is_draft(exercise),
        # Create Review Robin session on the gate card (segment 23J,
        # amended): the session's name and code, a field Review Robin would
        # refuse, and where a session opens by its code.
        session_name=functools.partial(handoff.session_name, exercise),
        session_code=functools.partial(handoff.session_code, exercise),
        field_problems=stages.field_problems,
        rr_by_code=_rr_by_code(request),
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
        process_revision=process_revision,
        email_fields=workflow.EMAIL_FIELDS,
        tag_help=workflow.TAG_HELP,
        email_sample=functools.partial(_email_sample, request, exercise),
        sends=functools.partial(workflow.sends, exercise.public_id),
        form_state=workflow.form_state(exercise),
    )
