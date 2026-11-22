"""The platform super-admin's pages, `/admin/…` (segment AD2A, ruling 75):
the operator list, who may operate an exercise. Rung 5 landed the page;
rung 6 wires its search, *Admit* and *Revoke* (`applydesk/allowlist.py`).
Exercises Diagnostics and System Status are scaffolds, as Review Robin's
Admin tabs (the author's ask, 2026-11-21)."""

from __future__ import annotations

import functools
import re
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse, Response

from applydesk import allowlist, db, directory, exercises, gate, locks, operators, sample_data
from applydesk.ids import row_id
from applydesk.models import Exercise
from applydesk.web import ADMIN, render, url_path
from cordware.graph import GraphError, directory_for
from cordware.identity import Identity, current_identity, super_admin_configured

router = APIRouter(prefix="/admin", dependencies=[Depends(gate.require_admin)])

_PAGE = "/admin/operators"
#: Longest form body a post here takes.
_MAX_BODY = 4096
#: The bulk bar's: up to a few thousand ticked rows.
_MAX_BULK_BODY = 65536
#: Most rows one bulk post changes.
_MAX_BULK = 1000

#: The page's status line, by the key its redirect carries: the page shows
#: only these, so a link cannot put words on it (as the Lobby's).
SAID: dict[str, str] = {
    "admitted": "Added to the list.",
    "revoked": "Taken off the list. Their exercises are kept for if they are put back.",
    "already_listed": "Already on the list.",
    "not_listed": "Not on the list.",
    "gone": "That person or account is no longer there; search again.",
    "directory": "The directory did not answer; try again.",
    "no_tenant": "Your sign-in names no tenant, so no one can be added from the directory.",
    "not_super_admin": "Only an Admin or the platform super-admin keeps the operator list.",
    "changed": "Someone else changed the list at the same time; check it and try again.",
    "pick": "Pick someone from the suggestions, then Add.",
    "none_ticked": "Tick at least one row, then choose what to do with them.",
    "too_many": "Tick at most 1,000 rows at a time; narrow the list with the chips or search.",
    # Admins (segment AD2M).
    "already_admin": "Already an Admin.",
    "not_admin": "Not an Admin.",
    "last_admin": "The last Admin stays an Admin.",
    "pending": "Only someone who has signed in can be an Admin.",
    "is_admin": "An Admin is demoted before being taken off the list.",
    "protected": "A super-admin's row is not changed here.",
}

#: Exercises Diagnostics' status line, by the key Manage's redirect carries
#: (segment AD2M): adopt's refusals, worded for the page.
ADOPT_SAID: dict[str, str] = {
    "not_loaded": (
        "That exercise is not in the database yet; on a local run, load the samples"
        " with python -m applydesk.seed."
    ),
    "not_admin": (
        "Only an Admin or the platform super-admin adopts an exercise, signed in with"
        " an account Apply Desk can record."
    ),
    "changed": "Someone else changed this exercise's operators at the same time; try again.",
}


def _same_site(request: Request) -> None:
    """Posts come from Apply Desk's own pages (as the Lobby's)."""
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        raise HTTPException(status_code=403)


async def _form_lists(request: Request) -> dict[str, list[str]]:
    """The post's fields, each with every value (the bulk bar's ticks)."""
    _same_site(request)
    body = await request.body()
    if len(body) > _MAX_BULK_BODY:
        raise HTTPException(status_code=413)
    return parse_qs(body.decode("utf-8", "replace"))


async def _form(request: Request) -> dict[str, str]:
    _same_site(request)
    body = await request.body()
    if len(body) > _MAX_BODY:
        raise HTTPException(status_code=413)
    return {k: v[0] for k, v in parse_qs(body.decode("utf-8", "replace")).items() if v}


def _back(request: Request, said: str, return_to: str = "") -> RedirectResponse:
    """The page again with its status line, keeping where Back goes (only
    an Apply Desk path, checked again; Codex on #4115)."""
    query = {"return_to": _back_link(return_to)[0], "said": said}
    return RedirectResponse(url_path(request, f"{_PAGE}?{urlencode(query)}"), 303)


def _identity(request: Request) -> Identity:
    identity = current_identity(request)
    if identity is None:  # the gate let a super-admin through, so never
        raise HTTPException(status_code=404)
    return identity


#: Where the Back link goes, by the page the Admin entry was opened from
#: (`?return_to=`, as Review Robin's Admin): only an Apply Desk path.
def _back_link(return_to: str) -> tuple[str, str]:
    """Only a page path: no dot segment, query or fragment can ride along
    (bug sweep at the AD2A close: `/me/../../.auth/logout` was kept)."""
    if _EXERCISE_PAGE.fullmatch(return_to):
        return return_to, "Back to the exercise"
    if _ME_PAGE.fullmatch(return_to):
        return return_to, "Back to User Lobby"
    return "/operator/exercises", "Back to Operator Lobby"


_EXERCISE_PAGE = re.compile(r"/operator/exercises/[a-z0-9]+(/[a-z0-9_-]+)*")
_ME_PAGE = re.compile(r"/me(/[a-z0-9_-]+)*")


def _bulk_said(request: Request) -> str:
    """The bulk bar's status line, from the redirect's counts: built from
    numbers, so a link cannot put words on the page."""
    params = request.query_params
    done = params.get("done")
    verbs = {
        "admit": "Added to the list",
        "revoke": "Taken off the list",
        "promote": "Made Admins",
        "demote": "No longer Admins",
    }
    if done not in verbs:
        return ""
    changed, skipped = (_row_count(params.get(k, "")) for k in ("n", "skipped"))
    line = f"{verbs[done]}: {changed}."
    if skipped:
        why = {
            "revoke": (
                "already so, an Admin (demote first), the only Owner of a live exercise"
                " (hand it over first), no longer there, or your own row"
            ),
            "promote": "already so, not yet signed in, no longer there, or your own row",
            "demote": "not an Admin, the last Admin, no longer there, or your own row",
        }.get(done, "already so, no longer there, or your own row")
        line += f" Skipped {skipped} ({why})."
    return line


def _row_count(raw: str) -> int:
    return int(raw) if raw.isascii() and raw.isdigit() and len(raw) <= 6 else 0


@router.get("/operators/suggest", name="applydesk_admin_suggest")
def suggest(request: Request, q: str = "", session: Session = Depends(db.get_session)) -> Response:
    """The *Add an operator* box's typeahead (segment AD2W): records, then
    the directory, as JSON; never cached. A sync route, so Graph's blocking
    calls run off the event loop."""
    answer = allowlist.suggest(session, q, lambda: directory_for(request))
    return JSONResponse(answer, headers={"Cache-Control": "no-store"})


@router.get("/operators", name="applydesk_admin_operators")
def operators_page(
    request: Request,
    list_q: str = "",
    role: str = "any",
    return_to: str = "",
    session: Session = Depends(db.get_session),
) -> Response:
    me = allowlist.me(session, _identity(request))
    # No `show` at all is the default chips; a blank one (the form's hidden
    # field) with no chip ticked is none, as Review Robin's.
    shown = request.query_params.getlist("show")
    show = frozenset(s for s in shown if s) if shown else allowlist.DEFAULT_SHOW
    view = allowlist.accounts(session, me, show=show, role=role, query=list_q)
    back_path, back_label = _back_link(return_to)
    return render(
        request,
        "applydesk/admin/operators.html",
        area=ADMIN,
        list_q=list_q,
        min_query=directory.MIN_QUERY,
        overview=allowlist.overview(session),
        listed={p.id for p in allowlist.listed_ids(session)},
        me=me,
        view=view,
        # Promote and Demote: the super-admin's; with none configured, any
        # Admin's (segment AD2M, Review Robin's fallback).
        makes_admins=gate.viewer(request).is_super_admin
        or (not super_admin_configured() and gate.viewer(request).is_admin),
        categories=allowlist.CATEGORIES,
        roles=allowlist.ROLES,
        said=SAID.get(request.query_params.get("said", ""), "") or _bulk_said(request),
        back_path=back_path,
        back_label=back_label,
    )


@router.get("/exercises", name="applydesk_admin_exercises")
def exercises_page(
    request: Request, return_to: str = "", session: Session = Depends(db.get_session)
) -> Response:
    """Exercises Diagnostics, a scaffold (the author's 2026-11-21 ask):
    the sample exercises, as Review Robin's Sessions Diagnostics, each
    with its Owner on record (2026-11-22)."""
    rows = exercises.stored_all(sample_data.EXERCISES)
    back_path, back_label = _back_link(return_to)
    return render(
        request,
        "applydesk/admin/exercises.html",
        area=ADMIN,
        rows=rows,
        owners=operators.owner_labels(session, [e.public_id for e in rows]),
        # Manage opens an exercise the viewer owns or operates, and adopts
        # the rest, asking first (segment AD2M).
        operates=functools.partial(gate.operates, request),
        said=ADOPT_SAID.get(request.query_params.get("said", ""), ""),
        by_status=locks.status_tally(rows),
        exercise_status=locks.exercise_status,
        default_timezone=sample_data.DEFAULT_TIMEZONE,
        back_path=back_path,
        back_label=back_label,
    )


@router.post("/exercises/{public_id}/manage", name="applydesk_admin_manage")
async def manage(request: Request, public_id: str) -> Response:
    """*Manage* on Exercises Diagnostics (segment AD2M): adopt the exercise
    as an Owner unless the viewer already owns or operates it, then open its
    Home. A sample not yet in the database cannot be adopted, and says so."""
    _same_site(request)
    return await run_in_threadpool(_manage, request, public_id)


def _manage(request: Request, public_id: str) -> Response:
    home = url_path(request, f"/operator/exercises/{public_id}")
    if gate.operates(request, public_id):
        return RedirectResponse(home, status_code=303)
    session = db.new_session()
    try:
        # A deleted exercise is gone: nothing to adopt (cold read, AD2B).
        exercise = session.scalar(
            select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
        )
        if exercise is None:
            return RedirectResponse(
                url_path(request, "/admin/exercises?said=not_loaded"), status_code=303
            )
        operators.adopt(session, exercise, allowlist.actor_for(session, _identity(request)))
        session.commit()
    except operators.Refused as refused:
        session.rollback()
        return RedirectResponse(
            url_path(request, f"/admin/exercises?said={refused.key}"), status_code=303
        )
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return RedirectResponse(url_path(request, "/admin/exercises?said=changed"), status_code=303)
    finally:
        session.close()
    gate.forget_viewer(request)  # their grants changed
    return RedirectResponse(home, status_code=303)


@router.get("/system", name="applydesk_admin_system")
def system_page(request: Request, return_to: str = "") -> Response:
    """System Status, a scaffold: the cards, every value a dash."""
    back_path, back_label = _back_link(return_to)
    return render(
        request,
        "applydesk/admin/system.html",
        area=ADMIN,
        back_path=back_path,
        back_label=back_label,
    )


def _admit(request: Request, form: dict[str, str]) -> Response:
    """The admission itself, off the event loop: a directory pick asks
    Graph again, by blocking calls (Codex on #4113)."""
    identity = _identity(request)
    back = form.get("return_to", "")
    session = db.new_session()
    try:
        actor = allowlist.actor_for(session, identity)
        person_id = row_id(form.get("person_id", ""))
        if person_id is not None:
            allowlist.admit_on_record(session, actor, person_id)
        elif form.get("object_id") and form.get("address"):
            tenant = (identity.tenant_id or "").strip()
            if not tenant:
                return _back(request, "no_tenant", back)
            allowlist.admit_from_directory(
                session,
                actor,
                directory_for(request),
                tenant,
                form["object_id"],
                form["address"],
            )
        else:  # typed, not picked from the suggestions
            return _back(request, "pick", back)
        session.commit()
    except operators.Refused as why:
        session.rollback()
        return _back(request, why.key if why.key in SAID else "gone", back)
    except GraphError:
        session.rollback()
        return _back(request, "directory", back)
    except (IntegrityError, OperationalError) as error:  # a concurrent change won
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return _back(request, "changed", back)
    finally:
        session.close()
    return _back(request, "admitted", back)


def _bulk(
    request: Request,
    action: str,
    person_ids: list[int],
    back: str,
    view: dict[str, str],
    shows: list[str],
) -> Response:
    """The bulk bar's change (segment AD2W), off the event loop: one
    transaction, each ticked row through `allowlist.bulk`."""
    session = db.new_session()
    try:
        identity = _identity(request)
        result = allowlist.bulk(
            session,
            allowlist.actor_for(session, identity),
            action,
            person_ids,
            allowlist.me(session, identity),
        )
        session.commit()
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        if not db.lost_a_race(error):
            raise
        return _back(request, "changed", back)
    finally:
        session.close()
    # The view stays as it was (cold read): chips, role and search.
    query: list[tuple[str, str | int]] = [("show", s) for s in shows]
    query += [(k, v) for k, v in view.items()]
    query += [
        ("return_to", _back_link(back)[0]),
        ("done", action),
        ("n", result.changed),
        ("skipped", result.skipped),
    ]
    return RedirectResponse(url_path(request, f"{_PAGE}?{urlencode(query)}#op-list"), 303)


@router.post("/operators/bulk", name="applydesk_admin_bulk")
async def bulk(request: Request) -> Response:
    """The bulk bar: *Admit* or *Revoke* every ticked row."""
    form = await _form_lists(request)
    action = (form.get("action") or [""])[0]
    ids = [i for i in (row_id(v) for v in form.get("person_ids", [])) if i is not None]
    back = (form.get("return_to") or [""])[0]
    view = {k: v for k in ("show", "role", "list_q") for v in form.get(k, []) if k != "show"}
    shows = form.get("show", [])
    if action not in allowlist.BULK_ACTIONS or not ids:
        return _back(request, "none_ticked", back)
    if len(ids) > _MAX_BULK:
        return _back(request, "too_many", back)
    return await run_in_threadpool(_bulk, request, action, ids, back, view, shows)


@router.post("/operators/admit", name="applydesk_admin_admit")
async def admit(request: Request) -> Response:
    form = await _form(request)  # the body is read on the loop, the rest off it
    return await run_in_threadpool(_admit, request, form)
