"""Support Logs' home at its bare mount, and the not-registered page
(`residentialapps/spec/applications.md`; segment 1D item 1 rung 1).

Home is the frontline's dashboard; for anyone else it lists the pages they
reach, or goes there when there is exactly one; a safety-flag recipient
with nothing else lands on a Home holding only the flags (author,
2026-10-29). A viewer with no grant gets the `403` page."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import MAIN, forbidden, render, sys_admin_tabs, tabs_for
from residentialapps.web.pages import placeholders_local_only
from residentialapps.web.urls import url_path

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def destinations(me: sample.Viewer) -> list[dict[str, str]]:
    """What a viewer off the frontline reaches from Home, each with what it
    holds; Home itself is not one."""
    found = [t for t in tabs_for(me) if t["path"] != "/"]
    if sample.holds(me, *sample.ADMINISTRATION):
        found.append(sys_admin_tabs(me)[0] | {"label": "Sys admin"})
    return found


@router.get("/", name="supportlogs_home")
def home(request: Request) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    if not me.grants:
        return forbidden(request, me)
    flags = sample.holds(me, sample.RECIPIENT)
    if sample.holds(me, sample.FRONTLINE):
        return render(request, "supportlogs/home.html", me=me, area=MAIN, tabs=tabs_for(me), flags=flags)
    # A recipient with Overview finds the flags there; one without lands on
    # a Home holding them.
    flags = flags and not sample.holds(me, sample.SENIOR, *sample.VIEW)
    places = destinations(me)
    if len(places) == 1 and not flags:
        return RedirectResponse(url_path(request, places[0]["path"]) + places[0]["query"], status_code=302)
    return render(request, "supportlogs/home_list.html", me=me, area=MAIN, tabs=tabs_for(me), places=places, flags=flags)


@router.get("/not-registered", name="supportlogs_not_registered")
def not_registered(request: Request) -> Response:
    # The preview of what a signed-in person Residential cannot link sees at
    # any path (`residentialapps/docs/residentialapps_identity.md` §6): no
    # switcher, no tabs, nothing about anyone else.
    return render(request, "supportlogs/not_registered.html", me=sample.DEFAULT, area=MAIN, areas=())
