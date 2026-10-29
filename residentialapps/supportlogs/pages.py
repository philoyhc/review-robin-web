"""Support Logs' page rendering: its templates, its areas and tabs, and the
gate each placeholder page names (segment 1D item 1). Support Logs takes
RA Leave's RA layout: the slim top bar, page tabs under it, no bottom bar
(author, 2026-10-29)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import current_identity
from residentialapps.supportlogs import sample_support as sample
from residentialapps.web.pages import initials
from residentialapps.web.urls import templates

TEMPLATES = templates([Path(__file__).resolve().parent / "templates"])

APP_NAME = "Support Logs"
MAIN = "Support Logs"
SYS_ADMIN_AREA = "Sys admin"


def tabs_for(v: sample.Viewer) -> tuple[dict[str, str], ...]:
    """The main area's tabs: Home, then each grant's own (author,
    2026-10-29): the frontline's Log, Students and Plans; Overview for
    senior staff and Other Staff view; Consultation check. No Safety flags
    tab: flags list on Home and Overview."""
    tabs = [("Home", "/")]
    if sample.holds(v, sample.FRONTLINE):
        tabs += [("Log", "/log"), ("Students", "/students/"), ("Plans", "/plans/")]
    if sample.holds(v, sample.SENIOR, *sample.VIEW):
        tabs.append(("Overview", "/overview/"))
    if sample.holds(v, sample.CONSULTATION):
        tabs.append(("Consultation check", "/consultation/"))
    return tuple({"label": label, "path": path, "query": sample.as_query(v)} for label, path in tabs)


SYS_ADMIN_TABS = (
    ("Access", "/sys-admin/"),
    ("Configuration", "/sys-admin/configuration"),
    ("Clusters", "/sys-admin/clusters"),
    ("Audit log", "/sys-admin/audit"),
)


def sys_admin_tabs(v: sample.Viewer) -> tuple[dict[str, str], ...]:
    return tuple({"label": label, "path": path, "query": sample.as_query(v)} for label, path in SYS_ADMIN_TABS)


def reaches_main(v: sample.Viewer) -> bool:
    return bool(v.grants - set(sample.ADMINISTRATION))


def areas_for(v: sample.Viewer) -> tuple[dict[str, str], ...]:
    """The switcher: Support Logs for anyone with a grant beyond
    administration, Sys admin for sys admins and the super-admin."""
    q = sample.as_query(v)
    areas = []
    if reaches_main(v):
        areas.append({"label": MAIN, "path": "/" + q})
    if sample.holds(v, *sample.ADMINISTRATION):
        areas.append({"label": SYS_ADMIN_AREA, "path": "/sys-admin/" + q})
    return tuple(areas)


def render(
    request: Request,
    template: str,
    *,
    me: sample.Viewer,
    area: str,
    tabs: Sequence[dict[str, str]] = (),
    areas: Sequence[dict[str, str]] | None = None,
    status_code: int = 200,
    **context: Any,
) -> Response:
    identity = current_identity(request)
    return TEMPLATES.TemplateResponse(
        request,
        template,
        {
            "app_key": "supportlogs",
            "app_name": APP_NAME,
            "unit_name": sample.UNIT_NAME,
            "area": area,
            "areas": areas_for(me) if areas is None else areas,
            "tabs": tabs,
            "viewer": identity,
            "initials": initials(identity.display_label) if identity else "?",
            "me": me,
            "as_query": sample.as_query(me),
            "sample": sample,
            # The viewer switch goes to each person's Home, which sends them
            # where they belong.
            "viewer_choices": [{"name": v.name, "what": sample.what(v), "path": "/" + sample.as_query(v)} for v in sample.VIEWERS],
            **context,
        },
        status_code=status_code,
    )


def forbidden(request: Request, me: sample.Viewer) -> Response:
    """The `403` page: a linked viewer at a page their grants do not reach,
    or with no grant at all (`residentialapps/spec/applications.md`)."""
    tabs = tabs_for(me) if reaches_main(me) else ()
    return render(request, "supportlogs/forbidden.html", me=me, area=MAIN, tabs=tabs, status_code=403)


def page(request: Request, *grants: str, area: str = MAIN, **context: Any) -> Response:
    """A placeholder page for the sample viewer, or the `403` page when
    they hold none of the grants it needs."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, *grants):
        return forbidden(request, me)
    tabs = sys_admin_tabs(me) if area == SYS_ADMIN_AREA else tabs_for(me)
    return render(request, "supportlogs/placeholder.html", me=me, area=area, tabs=tabs, **context)
