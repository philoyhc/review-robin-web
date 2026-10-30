"""Support Logs' page rendering: its templates, its areas and tabs, and the
gate each page takes (segment 1D item 1). Support Logs takes
RA Leave's RA layout: the slim top bar, page tabs under it, no bottom bar
(author, 2026-10-29)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

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


def _grant_tabs(v: sample.Viewer) -> list[tuple[str, str]]:
    """Each grant's own tabs (author, 2026-10-29): the frontline's Log,
    Students and Plans; Overview for senior staff and Other Staff view;
    Consultation check. No Safety flags tab: flags list on Home and
    Overview."""
    tabs = []
    if sample.holds(v, sample.FRONTLINE):
        tabs += [("Log", "/log"), ("Students", "/students/"), ("Plans", "/plans/")]
    if sample.holds(v, sample.SENIOR, *sample.VIEW):
        tabs.append(("Overview", "/overview/"))
    if sample.holds(v, sample.CONSULTATION):
        tabs.append(("Consultation check", "/consultation/"))
    return tabs


def home_flags(v: sample.Viewer) -> bool:
    """A recipient off the frontline without Overview finds the flags on
    Home; one with Overview finds them there."""
    return sample.holds(v, sample.RECIPIENT) and not sample.holds(v, sample.FRONTLINE, sample.SENIOR, *sample.VIEW)


def destinations(v: sample.Viewer) -> list[dict[str, str]]:
    """Where Home sends a viewer off the frontline: each grant's tab, and
    Sys admin."""
    found = [{"label": label, "path": path, "query": sample.as_query(v)} for label, path in _grant_tabs(v)]
    if sample.holds(v, *sample.ADMINISTRATION):
        found.append({"label": SYS_ADMIN_AREA, "path": "/sys-admin/", "query": sample.as_query(v)})
    return found


def home_is_a_page(v: sample.Viewer) -> bool:
    """Home is a page of its own for the frontline (the dashboard), for a
    recipient it holds the flags for, and for a viewer reaching more than
    one page; otherwise it redirects, and the tab bar has no Home."""
    return sample.holds(v, sample.FRONTLINE) or home_flags(v) or len(destinations(v)) > 1


def flags_tab(v: sample.Viewer) -> str | None:
    """Where a recipient's flags list: Home for the frontline and for a
    recipient with nothing else, else Overview (author, 2026-10-29)."""
    if not sample.holds(v, sample.RECIPIENT):
        return None
    return "/" if sample.holds(v, sample.FRONTLINE) or home_flags(v) else "/overview/"


def tabs_for(v: sample.Viewer) -> tuple[dict[str, str], ...]:
    """The main area's tabs, the flags' tab carrying the count of
    unacknowledged flags (UI spec screen 9)."""
    tabs = ([("Home", "/")] if home_is_a_page(v) else []) + _grant_tabs(v)
    count = sample.unacknowledged(v)
    return tuple(
        {"label": label, "path": path, "query": sample.as_query(v),
         "badge": count if path == flags_tab(v) and count else 0}
        for label, path in tabs
    )


SYS_ADMIN_TABS = (
    ("Access", "/sys-admin/"),
    ("Configuration", "/sys-admin/configuration"),
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


def reaches_student(me: sample.Viewer, sid: str) -> bool:
    """A frontline viewer reaches their own working set (§4.3) and what
    colleagues have shared with them (§11.1)."""
    return any(s.id == sid for s, _, _ in sample.working_set(me.name)) or any(
        g.student == sid for g in sample.shared_with(me.name)
    )


def query(me: sample.Viewer, **params: str) -> str:
    """A query string carrying the sample viewer and ``params``, or empty."""
    pairs = ([("as", me.name)] if me != sample.DEFAULT else []) + [(k, v) for k, v in params.items() if v]
    return "?" + urlencode(pairs, quote_via=quote) if pairs else ""


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
            "qs": lambda **params: query(me, **params),
            "sample": sample,
            # The viewer switch goes to each person's Home, which sends them
            # where they belong.
            "viewer_choices": [{"name": v.name, "what": sample.what(v), "path": "/" + sample.as_query(v)} for v in sample.VIEWERS],
            **context,
        },
        status_code=status_code,
    )


def forbidden(request: Request, me: sample.Viewer) -> Response:
    """The `403` page: a linked viewer with no grant at all, or at a page
    their grants do not reach (`residentialapps/spec/applications.md`)."""
    if reaches_main(me):
        return render(request, "supportlogs/forbidden.html", me=me, area=MAIN, tabs=tabs_for(me), status_code=403)
    area = SYS_ADMIN_AREA if sample.holds(me, *sample.ADMINISTRATION) else MAIN
    tabs = sys_admin_tabs(me) if area == SYS_ADMIN_AREA else ()
    return render(request, "supportlogs/forbidden.html", me=me, area=area, tabs=tabs, status_code=403)


def gated(request: Request, template: str, *grants: str, area: str = MAIN, **context: Any) -> Response:
    """A page for the sample viewer, or the `403` page when they hold none
    of the grants it needs."""
    me = sample.viewer(request.query_params.get("as"))
    if not sample.holds(me, *grants):
        return forbidden(request, me)
    tabs = sys_admin_tabs(me) if area == SYS_ADMIN_AREA else tabs_for(me)
    return render(request, template, me=me, area=area, tabs=tabs, **context)


def records_unlocked(request: Request) -> bool:
    """Your records, at the end of Students and My plans, opens only once
    its holder has confirmed (author, 2026-10-30): the unlock form sends
    `records=open` with the confirmation ticked. A sample: the state lives
    in the address, so leaving the page locks it again."""
    q = request.query_params
    return q.get("records") == "open" and q.get("understood") == "yes"

