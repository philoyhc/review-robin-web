"""Residential Operations' landing (`/`), segment 1C item 1: choose an
application the viewer reaches, drawn for a sample viewer (`?as=`)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from residentialapps.residentialops.main import create_app as ops_app


def apps(query: str = "") -> list[tuple[str, str]]:
    page = TestClient(ops_app()).get("/" + query).text
    return re.findall(r'<a class="app" href="([^"]*)"><span class="app-name">([^<]*)', page)


def test_each_viewer_sees_only_what_they_reach() -> None:
    """Author, 2026-10-28: RA Leave now, RA Events later; Rosters and Sys
    admin for sys admins. RA Leave opens on the viewer's own side."""
    assert apps() == [("/ra-leave/", "RA Leave")]  # Chloe Lim, an RA
    assert apps("?as=Daniel%20Koh") == [("/ra-leave/staff/", "RA Leave")]
    assert apps("?as=Sam%20Lee") == [
        ("/ra-leave/staff/?as=Sam%20Lee", "RA Leave"), ("/ra-leave/admin/", "RA Leave admin"),
        ("/rosters/", "Rosters"), ("/sys-admin/", "Sys admin"),
    ]
    assert [label for _, label in apps("?as=Rachel%20Yeo")][1:] == ["RA Leave admin", "Rosters", "Sys admin"]
    page = TestClient(ops_app()).get("/").text
    assert 'aria-disabled="true"><span class="app-name">RA Events</span><span class="app-what">Coming later' in page
    assert "Sample data" in page and "Viewing as Chloe Lim" in page


def test_home_is_in_the_switcher() -> None:
    page = TestClient(ops_app()).get("/rosters/").text
    assert re.search(r'<a href="/">Home', page)
