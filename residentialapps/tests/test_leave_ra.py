"""RA Leave's RA pages (`/ra-leave/`), segment 1C item 1: placeholders on
`sample_leave`, drawn for one sample viewer, phone first."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_leave
from residentialapps.residentialops.main import create_app as ops_app

RA = "/ra-leave/"
PAGES = ("", "apply", "appeal", "cover", "history", "applications/L-0101")


def client() -> TestClient:
    return TestClient(ops_app())


def test_every_ra_page_answers_for_the_sample_viewer() -> None:
    c = client()
    for path in PAGES:
        page = c.get(RA + path)
        assert page.status_code == 200, path
        assert "Sample data" in page.text and "Viewing as Chloe Lim" in page.text, path
    tabs = re.findall(r'<a href="(/ra-leave/[^"]*)"', c.get(RA).text.split('class="tabs-in"')[1].split("</nav>")[0])
    assert tabs == ["/ra-leave/", "/ra-leave/apply", "/ra-leave/appeal", "/ra-leave/cover", "/ra-leave/history"]


def test_home_shows_balance_cover_asked_and_applications_in_progress() -> None:
    """Spec §8: balance per leave type with extra leave apart; what is asked
    of the RA; applications in progress; the actions."""
    page = client().get(RA).text
    assert re.findall(r'<span class="tile-n">(\d+)</span><span class="tile-l">([^<]*)', page) == [
        ("2", "Personal leave available"), ("2", "Official leave available"),
    ]
    assert "kept apart from your entitlement" in page
    ask = page.split('id="ask-h"')[1].split("</section>")[0]
    assert "Ethan Wong" in ask and "4 Dec – 6 Dec" in ask
    mine = page.split('id="mine-h"')[1].split("</section>")[0]
    assert re.findall(r'href="/ra-leave/applications/(L-\d+)"', mine) == ["L-0101"]
    assert '>Apply for leave</a>' in page and '>Request extra leave</a>' in page


def test_apply_offers_cover_from_the_pool_never_oneself() -> None:
    page = client().get(RA + "apply").text
    assert sample_leave.cover_choices() == ("Ethan Wong", "Hana Ito")  # Same Precinct, Cypress A 04-12
    pool = page.split('id="cover-pool"')[1].split("</datalist>")[0]
    assert re.findall(r'value="([^"]*)"', pool) == ["Ethan Wong", "Hana Ito"]
    assert "waits at first approval" in page


def test_cover_lists_what_to_answer_what_is_agreed_and_the_rest() -> None:
    asked = sample_leave.cover_asked()
    assert [a.id for a in asked["answer"]] == ["L-0114"]
    assert [a.id for a in asked["coming"]] == ["L-0115"]
    assert [a.id for a in asked["past"]] == ["L-0109"]
    page = client().get(RA + "cover").text
    assert 'aria-label="Confirm cover for Ethan Wong, 4 Dec – 6 Dec"' in page


def test_an_ra_sees_only_their_own_applications() -> None:
    c = client()
    detail = c.get(RA + "applications/L-0101").text
    assert ">Withdraw</button>" in detail and "Submitted by Chloe Lim" in detail
    assert c.get(RA + "applications/L-0102").status_code == 404  # Isaac Goh's
    history = c.get(RA + "history").text
    assert re.findall(r'href="/ra-leave/applications/(L-\d+)"', history) == [a.id for a in sample_leave.my_applications()]


def test_appeals_off_removes_the_extra_leave_route(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "appeals", False)
    c = client()
    home = c.get(RA).text
    assert "/ra-leave/appeal" not in home and "kept apart from your entitlement" not in home
    assert "appeals are switched off" in c.get(RA + "appeal").text
