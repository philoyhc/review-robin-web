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
from applydesk.ids import row_id
from applydesk.web import ADMIN, render, url_path
from cordware.graph import GraphError, directory_for
from cordware.identity import Identity, current_identity

router = APIRouter(prefix="/admin", dependencies=[Depends(gate.require_super_admin)])

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
    "not_super_admin": "Only the platform super-admin keeps the operator list.",
    "changed": "Someone else changed the list at the same time; check it and try again.",
    "pick": "Pick someone from the suggestions, then Add.",
    "none_ticked": "Tick at least one row, then Admit or Revoke.",
    "too_many": "Tick at most 1,000 rows at a time; narrow the list with the chips or search.",
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
    if done not in ("admit", "revoke"):
        return ""
    changed, skipped = (_row_count(params.get(k, "")) for k in ("n", "skipped"))
    verb = "Added to the list" if done == "admit" else "Taken off the list"
    line = f"{verb}: {changed}."
    if skipped:
        line += f" Skipped {skipped} (already so, no longer there, or your own row)."
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
        categories=allowlist.CATEGORIES,
        roles=allowlist.ROLES,
        said=SAID.get(request.query_params.get("said", ""), "") or _bulk_said(request),
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
    if action not in ("admit", "revoke") or not ids:
        return _back(request, "none_ticked", back)
    if len(ids) > _MAX_BULK:
        return _back(request, "too_many", back)
    return await run_in_threadpool(_bulk, request, action, ids, back, view, shows)


@router.post("/operators/admit", name="applydesk_admin_admit")
async def admit(request: Request) -> Response:
    form = await _form(request)  # the body is read on the loop, the rest off it
    return await run_in_threadpool(_admit, request, form)
