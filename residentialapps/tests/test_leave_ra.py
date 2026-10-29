"""RA Leave's RA pages (`/ra-leave/`), segment 1C item 1: placeholders on
`sample_leave`, drawn for one sample viewer, phone first."""

from __future__ import annotations

import dataclasses
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
        ("2", "Personal leave available"), ("1", "Official leave available"),
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
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    c = client()
    home = c.get(RA).text
    assert "/ra-leave/appeal" not in home and "kept apart from your entitlement" not in home
    assert "appeals are switched off" in c.get(RA + "appeal").text
    assert "Leave in any blackout cannot be submitted while appeals are off" in c.get(RA + "apply").text


def test_existing_extra_leave_shows_even_with_appeals_off(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    monkeypatch.setattr(sample_leave, "my_extra", lambda ra=None: {"granted": 0, "pending": 4})
    home = client().get(RA).text
    assert "kept apart from your entitlement" in home and "<dt>Pending</dt><dd>4</dd>" in home


def test_cover_answers_follow_the_cover_setting(monkeypatch) -> None:
    """Named only, or cover not required: no answer is owed for ordinary
    leave (spec §12), so Ethan Wong's ask moves to Covering."""
    detail = client().get(RA + "applications/L-0101").text
    assert "Next: pending first approval" in detail
    monkeypatch.setitem(sample_leave.POLICY, "cover_mode", "Named only")
    asked = sample_leave.cover_asked()
    assert asked["answer"] == () and [a.id for a in asked["coming"]] == ["L-0114", "L-0115"]
    page = client().get(RA).text
    assert 'id="ask-h"' not in page
    monkeypatch.setitem(sample_leave.POLICY, "cover_mode", "Named and confirmed")
    monkeypatch.setitem(sample_leave.POLICY, "cover_required", False)
    assert sample_leave.cover_asked()["answer"] == ()
    assert "Covering RA (optional)" in client().get(RA + "apply").text


def test_history_is_newest_first_and_unknown_ids_are_not_found(monkeypatch) -> None:
    older = sample_leave.Application("L-0901", "Chloe Lim", "Personal leave", sample_leave.date(2026, 9, 1),
                                     sample_leave.date(2026, 9, 2), "Ethan Wong", "Confirmed", "Approved",
                                     sample_leave.date(2026, 8, 20))
    monkeypatch.setattr(sample_leave, "APPLICATIONS", sample_leave.APPLICATIONS + (older,))
    history = client().get(RA + "history").text
    assert re.findall(r'href="/ra-leave/applications/(L-\d+)"', history) == ["L-0101", "L-0117", "L-0901"]
    assert "sent 27 Oct" in history
    assert client().get(RA + "applications/L-9999").status_code == 404


def test_by_invitation_the_ra_is_not_offered_an_appeal_until_invited(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    c = client()
    home = c.get(RA).text
    # Not shown to an uninvited RA at all (author, 2026-10-29).
    assert ">Request extra leave</a>" not in home and 'href="/ra-leave/appeal"' not in home  # no tab either
    assert "Extra leave" not in home and "the Master" not in home
    assert c.get(RA + "appeal").status_code == 404
    apply = c.get(RA + "apply").text
    assert "Leave in a blackout cannot be submitted." in apply and "Master" not in apply
    monkeypatch.setattr(sample_leave, "INVITATIONS", sample_leave.INVITATIONS + (
        sample_leave.Invitation("Chloe Lim", "Sam Lee", sample_leave.date(2026, 10, 28), sample_leave.date(2026, 11, 4), "Agreed"),))
    monkeypatch.setattr(sample_leave, "VIEWER", "Chloe Lim")
    invited = c.get(RA + "appeal").text
    assert "The Master has agreed to consider your appeal; send it by 4 Nov." in invited
    assert '>Request extra leave</a>' in c.get(RA).text
    assert "in an Appeal-only one it goes to the Master as an appeal" in c.get(RA + "apply").text


def test_review_fixes_on_the_ra_side(monkeypatch) -> None:
    """The 2026-10-29 review: the RA's menu holds only what an RA reaches,
    a detail page marks its list's tab, and the next step follows the
    policy."""
    c = client()
    page = c.get(RA).text
    menu = page.split('aria-label="Switch area"')[1].split("</nav>")[0]
    assert 'href="/ra-leave/"' in menu and "/sys-admin/" not in menu and "/rosters/" not in menu
    detail = c.get(RA + "applications/L-0101").text
    assert 'href="/ra-leave/history" aria-current="true"' in detail
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert "pending first approval" not in c.get(RA + "applications/L-0101").text


def test_history_shows_decision_dates_and_remarks(monkeypatch) -> None:
    """Spec §19: each record shows its decision dates and remarks."""
    history = client().get(RA + "history").text
    assert "First approval by Daniel Koh, 15 Sep: “Good luck at the games.”" in history
    assert "Final approval by Rachel Yeo, 16 Sep" in history
    # With no first approval needed, history drops that step as the timeline does.
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert "Good luck at the games." not in client().get(RA + "history").text


def test_an_ra_can_name_new_cover_on_an_open_application(monkeypatch) -> None:
    """Spec §12 and scenario L: an open application offers Change cover,
    and a declined cover says the application waits on new cover."""
    page = client().get(RA + "applications/L-0101").text
    assert "Change cover" in page and "Ethan Wong" in page
    assert '<option value="Ethan Wong">' not in page  # never the cover already named
    declined = dataclasses.replace(sample_leave.by_id("L-0101"), cover_recorded="Declined")
    monkeypatch.setattr(sample_leave, "APPLICATIONS", tuple(declined if a.id == "L-0101" else a for a in sample_leave.APPLICATIONS))
    assert "cannot cover you. Name someone else" in client().get(RA + "applications/L-0101").text
    assert "Change cover" not in client().get(RA + "applications/L-0117").text  # decided


def test_the_ra_sees_the_emails_they_sent_and_resends_a_failed_one() -> None:
    """Spec §17.2 (author, 2026-10-29): an email the RA's action sent that
    failed is shown on the application with Resend."""
    page = TestClient(ops_app()).get("/ra-leave/applications/L-0101").text
    emails = page.split('id="emails-h"')[1].split("</section>")[0]
    assert "Emails you sent" in page
    assert "Application submitted</span> to Daniel Koh" in emails and ">Resend to Daniel Koh</button>" in emails
    assert "Cover asked</span> to Ethan Wong" in emails and ">Resend to Ethan Wong" not in emails  # sent
