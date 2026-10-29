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
    assert apps("?as=Rachel%20Yeo")[0] == ("/ra-leave/staff/?as=Rachel%20Yeo", "RA Leave")
    assert [label for _, label in apps("?as=Rachel%20Yeo")][1:] == ["RA Leave admin", "Rosters", "Sys admin"]
    assert apps("?as=Nobody") == apps()  # an unknown viewer: the default
    page = TestClient(ops_app()).get("/").text
    assert '<span class="app app-off"><span class="app-name">RA Events</span><span class="app-what">Coming later' in page
    assert "Sample data" in page and "Viewing as Chloe Lim" in page


def test_home_is_in_the_switcher() -> None:
    page = TestClient(ops_app()).get("/rosters/").text
    assert re.search(r'<a href="/">Home', page)


def test_the_viewer_switch_links_each_person() -> None:
    page = TestClient(ops_app()).get("/?as=Sam%20Lee").text
    switch = page.split('aria-label="Sample viewer"')[1].split("</nav>")[0]
    assert re.findall(r'href="([^"]*)"', switch) == [
        "/", "/?as=Daniel%20Koh", "/?as=Rachel%20Yeo", "/?as=Sam%20Lee",
    ]
    assert 'href="/?as=Sam%20Lee" aria-current="true"' in switch


def test_a_sys_admin_off_the_staff_side_gets_no_staff_pages(monkeypatch) -> None:
    from residentialapps.residentialops import routes_home, sample_data

    monkeypatch.setattr(sample_data, "SYS_ADMINS", sample_data.SYS_ADMINS + (("Priya Raman", "", "", ""),))
    targets = [a["path"] for a in routes_home.choices("Priya Raman")]
    assert "/ra-leave/staff/?as=Priya%20Raman" not in targets and "/ra-leave/admin/" in targets
