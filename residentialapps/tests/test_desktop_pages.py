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


def test_every_desktop_oriented_page_in_the_map_is_listed() -> None:
    """Each page-map row classed desktop-oriented has its path's prefix
    in DESKTOP_PAGES, so a new desktop page cannot miss the exemption."""
    rows = [r for r in PAGE_MAP.read_text().splitlines() if "desktop-oriented" in r and "`/" in r]
    assert rows
    for row in rows:
        for path in re.findall(r"`(/[^`]*)`", row.split("|")[2]):
            listed = any(
                path.startswith(prefix.rstrip("/"))
                for prefixes in DESKTOP_PAGES.values()
                for prefix in prefixes
            )
            assert listed, path
