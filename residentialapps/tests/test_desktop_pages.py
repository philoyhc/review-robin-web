"""Desktop-oriented pages (author, 2026-11-08): the page map's class,
which keeps the page's full width for its cards rather than two of its
three columns (`residentialapps/spec/residentialops_ui.md` §1)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from residentialapps.web.pages import DESKTOP_PAGES, desktop_oriented

PAGE_MAP = Path(__file__).resolve().parents[1] / "spec" / "applications.md"


@pytest.mark.parametrize(
    ("app", "path", "desktop"),
    [
        ("residentialops", "/ra-leave/admin/", True),
        ("residentialops", "/ra-leave/admin", True),
        ("residentialops", "/ra-leave/admin/applications/A-1", True),
        ("residentialops", "/ra-leave/staff/precinct", True),
        ("residentialops", "/ra-leave/staff/precincts", False),
        ("residentialops", "/rosters/people/P-01", True),
        ("residentialops", "/ra-leave/staff/", False),
        ("residentialops", "/rosters/staff", True),
        ("residentialops", "/sys-admin/", True),
        ("residentialops", "/", False),
        ("supportlogs", "/sys-admin/audit", True),
        ("supportlogs", "/overview/", False),
        ("supportlogs", "/rosters/", False),
    ],
)
def test_desktop_oriented(app: str, path: str, desktop: bool) -> None:
    assert desktop_oriented(app, path) is desktop


def _page_map_rows() -> list[tuple[str, bool]]:
    """Each classed page-map row's paths, and whether its class is
    desktop-oriented (Support Logs' rows carry no class)."""
    rows: list[tuple[str, bool]] = []
    for row in PAGE_MAP.read_text().splitlines():
        cells = row.split("|")
        if len(cells) < 4 or "`/" not in cells[2]:
            continue
        if not any(c in row for c in ("desktop-oriented", "responsive", "mobile-critical")):
            continue  # a section's heading row, or a page with no class
        for path in re.findall(r"`(/[^`…]*)`", cells[2]):
            rows.append((path, "desktop-oriented" in row))
    return rows


def test_the_list_matches_the_page_map_both_ways() -> None:
    """Every Residential Ops path the map classes desktop-oriented is one,
    and no path of a responsive or mobile-critical row is, so the list can
    neither miss a desktop page nor catch another (Support Logs' Sys admin
    is that spec's own class, `residentialapps/spec/supportlogs_ui.md`)."""
    rows = _page_map_rows()
    assert any(desktop for _, desktop in rows)
    for path, desktop in rows:
        assert desktop_oriented("residentialops", path) is desktop, path
    assert DESKTOP_PAGES["supportlogs"] == ("/sys-admin/",)
