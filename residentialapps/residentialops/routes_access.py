"""Identity and access screens: person detail, sys admin grants and the
audit log, and the not-registered page. Placeholders with sample data,
segment 1B item 1; wired by item 3."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.residentialops import sample_data
from residentialapps.residentialops.pages import ROSTER_TABS, placeholders_local_only, render

ROSTER_BACK = {
    "staff": {"label": "Staff roster", "path": "/rosters/staff"},
    "ra": {"label": "RA roster", "path": "/rosters/ras"},
}

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


@router.get("/rosters/people/{person_id}", name="residentialops_person")
def person(request: Request, person_id: str) -> Response:
    found = sample_data.PEOPLE.get(person_id)
    if found is None:
        raise HTTPException(status_code=404)
    return render(
        request,
        "residentialops/access/person.html",
        area="Rosters",
        tabs=ROSTER_TABS,
        person=found,
        back=ROSTER_BACK[found.roster],
    )


@router.get("/sys-admin/", name="residentialops_sys_admin")
def sys_admin(request: Request) -> Response:
    return render(
        request,
        "residentialops/access/sys_admin.html",
        area="Sys admin",
        sample=sample_data,
    )


@router.get("/not-registered", name="residentialops_not_registered")
def not_registered(request: Request) -> Response:
    # The preview of what a signed-in person Residential cannot link sees at
    # any path (`residentialapps/docs/residentialapps_identity.md` §6, step 4):
    # no switcher, no tabs, nothing about anyone else.
    return render(request, "residentialops/access/not_registered.html", area="Residential Operations", areas=())
