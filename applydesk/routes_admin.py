"""The platform super-admin's pages, `/admin/…` (segment AD2A, ruling 75):
the operator list, who may operate an exercise. Rung 5 landed the page;
rung 6 wires its search, *Admit* and *Revoke* (`applydesk/allowlist.py`)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse, Response

from applydesk import allowlist, db, directory, gate, operators
from applydesk.web import OPERATOR_LIST, render, url_path
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
    "already": "Already on the list.",
    "not_listed": "Not on the list.",
    "gone": "That person or account is no longer there; search again.",
    "directory": "The directory did not answer; try again.",
    "no_tenant": "Your sign-in names no tenant, so no one can be added from the directory.",
}
_REFUSALS: dict[str, str] = {
    "Already allowed to operate.": "already",
    "Not on the operator list.": "not_listed",
    "That person is no longer on record.": "gone",
    "The directory no longer has that account; search again.": "gone",
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


def _back(request: Request, said: str) -> RedirectResponse:
    return RedirectResponse(url_path(request, f"{_PAGE}?{urlencode({'said': said})}"), 303)


def _identity(request: Request) -> Identity:
    identity = current_identity(request)
    if identity is None:  # the gate let a super-admin through, so never
        raise HTTPException(status_code=404)
    return identity


@router.get("/operators", name="applydesk_admin_operators")
def operators_page(
    request: Request, q: str = "", session: Session = Depends(db.get_session)
) -> Response:
    found = None
    if q.strip():
        try:
            people_directory = directory_for(request)
        except GraphError as error:
            found = directory.search(session, q, None)
            found = directory.SearchResult(found.on_record, (), directory_failed=error.kind)
        else:
            found = directory.search(session, q, people_directory)
    entries = allowlist.listing(session)
    return render(
        request,
        "applydesk/admin/operators.html",
        area=OPERATOR_LIST,
        q=q,
        found=found,
        min_query=directory.MIN_QUERY,
        entries=entries,
        listed={e.person.id for e in entries},
        said=SAID.get(request.query_params.get("said", ""), ""),
    )


def _admit(request: Request, form: dict[str, str]) -> Response:
    """The admission itself, off the event loop: a directory pick asks
    Graph again, by blocking calls (Codex on #4113)."""
    identity = _identity(request)
    session = db.new_session()
    try:
        actor = allowlist.actor_for(session, identity)
        if form.get("person_id", "").isdigit():
            allowlist.admit_on_record(session, actor, int(form["person_id"]))
        elif form.get("object_id") and form.get("address"):
            tenant = (identity.tenant_id or "").strip()
            if not tenant:
                return _back(request, "no_tenant")
            allowlist.admit_from_directory(
                session,
                actor,
                directory_for(request),
                tenant,
                form["object_id"],
                form["address"],
            )
        else:
            raise HTTPException(status_code=400)
        session.commit()
    except operators.Refused as why:
        session.rollback()
        return _back(request, _REFUSALS.get(str(why), "gone"))
    except GraphError:
        session.rollback()
        return _back(request, "directory")
    finally:
        session.close()
    return _back(request, "admitted")


def _revoke(request: Request, person_id: int) -> Response:
    session = db.new_session()
    try:
        allowlist.revoke(session, allowlist.actor_for(session, _identity(request)), person_id)
        session.commit()
    except operators.Refused as why:
        session.rollback()
        return _back(request, _REFUSALS.get(str(why), "gone"))
    finally:
        session.close()
    return _back(request, "revoked")


@router.post("/operators/admit", name="applydesk_admin_admit")
async def admit(request: Request) -> Response:
    form = await _form(request)  # the body is read on the loop, the rest off it
    return await run_in_threadpool(_admit, request, form)


@router.post("/operators/{person_id}/revoke", name="applydesk_admin_revoke")
async def revoke(request: Request, person_id: int) -> Response:
    await _form(request)
    return await run_in_threadpool(_revoke, request, person_id)
