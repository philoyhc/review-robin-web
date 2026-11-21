"""The platform super-admin's pages, `/admin/…` (segment AD2A, ruling 75):
the operator list, who may operate an exercise. Rung 5 landed the page;
rung 6 wires its search, *Admit* and *Revoke* (`applydesk/allowlist.py`).
Exercises Diagnostics and System Status are scaffolds, as Review Robin's
Admin tabs (the author's ask, 2026-11-21)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse, Response

from applydesk import allowlist, db, directory, gate, locks, operators, sample_data
from applydesk.ids import RowId, row_id
from applydesk.web import ADMIN, render, url_path
from cordware.graph import GraphError, directory_for
from cordware.identity import Identity, current_identity

router = APIRouter(prefix="/admin", dependencies=[Depends(gate.require_super_admin)])

_PAGE = "/admin/operators"
#: Longest form body a post here takes.
_MAX_BODY = 4096

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
    "not_super_admin": "Only the platform super-admin keeps the operator list.",
    "changed": "Someone else changed the list at the same time; check it and try again.",
    "self": "You can't act on your own row.",
    "pick": "Pick someone from the suggestions, then Add.",
}


def _same_site(request: Request) -> None:
    """Posts come from Apply Desk's own pages (as the Lobby's)."""
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        raise HTTPException(status_code=403)


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


@router.get("/operators/suggest", name="applydesk_admin_suggest")
def suggest(request: Request, q: str = "", session: Session = Depends(db.get_session)) -> Response:
    """The *Add an operator* box's typeahead (segment AD2W): records, then
    the directory, as JSON; never cached. A sync route, so Graph's blocking
    calls run off the event loop."""
    found = allowlist.search(session, q, lambda: directory_for(request))
    answer = allowlist.suggestions(found, {p.id for p in allowlist.listed_ids(session)})
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
        categories=allowlist.CATEGORIES,
        roles=allowlist.ROLES,
        said=SAID.get(request.query_params.get("said", ""), ""),
        back_path=back_path,
        back_label=back_label,
    )


@router.get("/exercises", name="applydesk_admin_exercises")
def exercises_page(request: Request, return_to: str = "") -> Response:
    """Exercises Diagnostics, a scaffold (the author's 2026-11-21 ask):
    the sample exercises, as Review Robin's Sessions Diagnostics."""
    rows = sample_data.EXERCISES
    back_path, back_label = _back_link(return_to)
    return render(
        request,
        "applydesk/admin/exercises.html",
        area=ADMIN,
        rows=rows,
        by_status=locks.status_tally(rows),
        exercise_status=locks.exercise_status,
        default_timezone=sample_data.DEFAULT_TIMEZONE,
        back_path=back_path,
        back_label=back_label,
    )


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


def _revoke(request: Request, person_id: int, back: str) -> Response:
    session = db.new_session()
    try:
        identity = _identity(request)
        # As Review Robin: no action on your own row (the author's ruling
        # at the AD2A close); the page offers none.
        if allowlist.me(session, identity).person_id == person_id:
            return _back(request, "self", back)
        allowlist.revoke(session, allowlist.actor_for(session, identity), person_id)
        session.commit()
    except operators.Refused as why:
        session.rollback()
        return _back(request, why.key if why.key in SAID else "gone", back)
    except OperationalError as error:
        session.rollback()
        if not db.is_busy(error):
            raise
        return _back(request, "changed", back)
    finally:
        session.close()
    return _back(request, "revoked", back)


@router.post("/operators/admit", name="applydesk_admin_admit")
async def admit(request: Request) -> Response:
    form = await _form(request)  # the body is read on the loop, the rest off it
    return await run_in_threadpool(_admit, request, form)


@router.post("/operators/{person_id}/revoke", name="applydesk_admin_revoke")
async def revoke(request: Request, person_id: RowId) -> Response:
    form = await _form(request)
    return await run_in_threadpool(_revoke, request, person_id, form.get("return_to", ""))
