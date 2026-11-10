"""RA Leave's RA pages (`/ra-leave/`), segment 1C item 1: placeholders on
`sample_leave`, drawn for one sample viewer, phone first."""

from __future__ import annotations

import dataclasses
import re

import pytest
from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_leave
from residentialapps.residentialops.main import create_app as ops_app

RA = "/ra-leave/"
PAGES = ("", "apply", "appeal", "cover", "history", "applications/L-0101")


@pytest.fixture(autouse=True)
def _appeals_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests exercise extra leave, so appeals are Open in them; the
    default, By invitation, has its own test (author, 2026-11-09)."""
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Open")


def _by_id(application_id: str) -> sample_leave.Application:
    """A sample application the test names, which the sample holds."""
    found = sample_leave.by_id(application_id)
    assert found is not None, application_id
    return found


def client() -> TestClient:
    return TestClient(ops_app())


def test_every_ra_page_answers_for_the_sample_viewer() -> None:
    c = client()
    for path in PAGES:
        page = c.get(RA + path)
        assert page.status_code == 200, path
        assert "Sample data" in page.text and "Viewing as Chloe Lim" in page.text, path
    tabs = re.findall(
        r'<a href="(/ra-leave/[^"]*)"',
        c.get(RA).text.split('class="tabs-in"')[1].split("</nav>")[0],
    )
    assert tabs == [
        "/ra-leave/",
        "/ra-leave/apply",
        "/ra-leave/appeal",
        "/ra-leave/cover",
        "/ra-leave/history",
    ]


def test_home_shows_balance_cover_asked_and_applications_in_progress() -> None:
    """Spec §8: balance per leave type with extra leave apart; what is asked
    of the RA; applications in progress; the actions."""
    page = client().get(RA).text
    # One balance card, first, its types side by side; no tiles repeat it
    # (author, 2026-11-09).
    assert 'class="tile' not in page
    main = page.split('class="main stack">')[1]
    assert main.lstrip().startswith('<section class="card card-pad" aria-labelledby="bal-h">')
    pair = main.split('class="pair"')[1].split("</section>")[0]
    assert re.findall(r"<h3>([^<]*)</h3>", pair) == ["Personal leave", "Official leave"]
    assert re.findall(r"<dt>Available</dt><dd>([^<]*)</dd>", pair) == ["2 days", "1 day"]
    # The main column is the balance and Apply; the side holds My
    # applications, Drafts, then Asked to cover, the order a phone shows
    # them after Apply (author, 2026-11-09).
    main, side = main.split('<div class="side">')
    assert ">Apply for leave</a>" in main
    assert not any(h in main for h in ('id="mine-h"', 'id="drafts-h"', 'id="ask-h"'))
    assert side.index('id="mine-h"') < side.index('id="drafts-h"') < side.index('id="ask-h"')
    hana = client().get(RA + "?as=Hana%20Ito").text.split('<div class="side">')[1]
    assert 'id="mine-h"' in hana
    assert "kept apart from your entitlement" in page
    ask = page.split('id="ask-h"')[1].split("</section>")[0]
    assert "Ethan Wong" in ask and "4 Dec – 6 Dec" in ask
    mine = page.split('id="mine-h"')[1].split("</section>")[0]
    assert re.findall(r'href="/ra-leave/applications/(L-\d+)"', mine) == ["L-0101"]
    assert ">Apply for leave</a>" in page and ">Request extra leave</a>" in page


def test_apply_offers_cover_from_the_pool_never_oneself() -> None:
    page = client().get(RA + "apply").text
    assert sample_leave.cover_choices() == (
        "Ethan Wong",
        "Hana Ito",
    )  # Same Precinct, Cypress A 04-12
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
    assert ">Withdraw to draft</button>" in detail and "Submitted by Chloe Lim" in detail
    assert c.get(RA + "applications/L-0102").status_code == 404  # Isaac Goh's
    history = c.get(RA + "history").text
    assert re.findall(r'href="/ra-leave/applications/(L-\d+)"', history) == [
        a.id for a in sample_leave.my_applications()
    ]


def test_appeals_off_removes_the_extra_leave_route(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    c = client()
    home = c.get(RA).text
    assert "/ra-leave/appeal" not in home and "kept apart from your entitlement" not in home
    assert c.get(RA + "appeal").status_code == 404  # not offered, not there
    apply = c.get(RA + "apply").text
    assert "Leave in a blackout cannot be submitted." in apply
    assert "appeals are off" not in apply and "Request extra leave" not in apply


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
    older = sample_leave.Application(
        "L-0901",
        "Chloe Lim",
        "Personal leave",
        sample_leave.date(2026, 9, 1),
        sample_leave.date(2026, 9, 2),
        "Ethan Wong",
        "Confirmed",
        "Approved",
        sample_leave.date(2026, 8, 20),
    )
    monkeypatch.setattr(sample_leave, "APPLICATIONS", sample_leave.APPLICATIONS + (older,))
    history = client().get(RA + "history").text
    assert re.findall(r'href="/ra-leave/applications/(L-\d+)"', history) == [
        "L-0101",
        "L-0117",
        "L-0901",
    ]
    assert "sent 27 Oct" in history
    assert client().get(RA + "applications/L-9999").status_code == 404


def test_by_invitation_the_ra_is_not_offered_an_appeal_until_invited(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    c = client()

    def page(
        path: str,
    ) -> str:  # the page less its sample viewer switch, which names every RA's state
        return re.sub(
            r'<nav [^>]*aria-label="Sample viewer">.*?</nav>', "", c.get(path).text, flags=re.S
        )

    home = page(RA)
    # Not shown to an uninvited RA at all (author, 2026-10-29).
    assert (
        ">Request extra leave</a>" not in home and 'href="/ra-leave/appeal"' not in home
    )  # no tab either
    assert "Extra leave" not in home and "the Master" not in home
    assert c.get(RA + "appeal").status_code == 404
    apply = page(RA + "apply")
    assert "Leave in a blackout cannot be submitted." in apply and "Master" not in apply
    monkeypatch.setattr(
        sample_leave,
        "INVITATIONS",
        sample_leave.INVITATIONS
        + (
            sample_leave.Invitation(
                "Chloe Lim",
                "Sam Lee",
                sample_leave.date(2026, 10, 28),
                sample_leave.date(2026, 11, 4),
                "Agreed",
            ),
        ),
    )
    monkeypatch.setattr(sample_leave, "VIEWER", "Chloe Lim")
    invited = c.get(RA + "appeal").text
    assert "The Master has agreed to consider your appeal; send it by 4 Nov." in invited
    assert ">Request extra leave</a>" in c.get(RA).text
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
    declined = dataclasses.replace(_by_id("L-0101"), cover_recorded="Declined")
    monkeypatch.setattr(
        sample_leave,
        "APPLICATIONS",
        tuple(declined if a.id == "L-0101" else a for a in sample_leave.APPLICATIONS),
    )
    assert "cannot cover you. Name someone else" in client().get(RA + "applications/L-0101").text
    assert "Change cover" not in client().get(RA + "applications/L-0117").text  # decided


def test_the_ra_sees_the_emails_they_sent_and_resends_a_failed_one() -> None:
    """Spec §17.2 (author, 2026-10-29): an email the RA's action sent that
    failed is shown on the application with Resend."""
    page = TestClient(ops_app()).get("/ra-leave/applications/L-0101").text
    emails = page.split('id="emails-h"')[1].split("</section>")[0]
    assert "Emails you sent" in page
    assert (
        "Application submitted to Daniel Koh</span>" in emails
        and ">Resend to Daniel Koh</button>" in emails
    )
    assert (
        "Cover asked to Ethan Wong</span>" in emails and ">Resend to Ethan Wong" not in emails
    )  # sent
    assert "Cover confirmed" not in emails  # Ethan Wong's email, not the viewer's
    assert (
        'disabled aria-label="Resend application submitted to Daniel Koh">' in emails
    )  # inert, named for its row


def test_an_application_can_be_saved_as_a_draft_and_reopened() -> None:
    """Spec §11's Draft (author, 2026-10-29): Save draft keeps it unsent and
    the RA's alone; it reopens on Apply, filled in, to submit or discard,
    and appears on the RA's home and history, nowhere else."""
    c = TestClient(ops_app())
    draft = sample_leave.my_drafts()[0]
    assert ">Save draft</button>" in c.get("/ra-leave/apply").text
    assert (
        ">Save draft</button>" not in c.get("/ra-leave/appeal").text
    )  # an appeal's draft waits for the wiring
    assert "Discard draft" not in c.get("/ra-leave/apply").text
    page = c.get(f"/ra-leave/apply?draft={draft.id}").text
    assert "Draft saved 26 Oct." in page and ">Discard draft</button>" in page
    assert (
        f'value="{draft.start.isoformat()}"' in page and f'value="{draft.end.isoformat()}"' in page
    )
    assert (
        f'<span class="token">{draft.cover}<button' in page
        and f">{draft.remarks}</textarea>" in page
    )
    assert "<option selected>Official leave</option>" in page
    assert c.get("/ra-leave/apply?draft=D-9999").status_code == 404
    assert c.get("/ra-leave/apply?draft=D-0002").status_code == 404  # Ethan Wong's, not Chloe Lim's
    for path in ("/ra-leave/", "/ra-leave/history"):
        listed = c.get(path).text.split('id="drafts-h"')[1].split("</section>")[0]
        assert f'href="/ra-leave/apply?draft={draft.id}"' in listed and "not yet asked" in listed, (
            path
        )
    # A draft is not an application: no staff or admin page, list or count
    # sees it, not even its RA's own approver's.
    for path in (
        "/ra-leave/admin/",
        "/ra-leave/admin/applications",
        "/ra-leave/staff/",
        "/ra-leave/staff/precinct?period=term",
    ):
        assert "18 Dec" not in c.get(path).text, path
    assert all(a.id != draft.id for a in sample_leave.APPLICATIONS)


def test_the_audit_s_ra_page_fixes() -> None:
    """The 1C.1 audit (2026-10-29): the back link names the page it opens,
    and withdrawing, which ends the application, is Destructive. Since
    2026-11-10 withdrawing ordinary leave returns it to the drafts, so it is
    Secondary; an appeal's still ends it."""
    page = TestClient(ops_app()).get("/ra-leave/applications/L-0101").text
    assert '<a class="back" href="/ra-leave/history">‹ My history</a>' in page
    assert 'class="btn btn-secondary" aria-label="Withdraw 6 Nov – 8 Nov to your drafts"' in page


def test_the_ra_pages_switch_sample_viewer() -> None:
    """The 1C.1 audit (2026-10-29): RA states Chloe Lim's applications do not
    reach are seen by switching the RA pages' sample viewer (`?as=`),
    carried by the tabs and links."""
    c = TestClient(ops_app())
    hana = c.get("/ra-leave/?as=Hana%20Ito").text
    assert "Viewing as Hana Ito" in hana
    assert 'href="/ra-leave/applications/L-0109?as=Hana%20Ito"' in hana  # her declined cover
    assert 'href="/ra-leave/apply?as=Hana%20Ito"' in hana
    tabs = hana.split('class="tabs-in"')[1].split("</nav>")[0]
    assert all(href.endswith("?as=Hana%20Ito") for href in re.findall(r'<a href="([^"]*)"', tabs))
    detail = c.get("/ra-leave/applications/L-0109?as=Hana%20Ito").text
    assert "cannot cover you. Name someone else" in detail
    assert c.get("/ra-leave/applications/L-0109").status_code == 404  # Chloe Lim's view: not hers
    for name, state in (
        ("Faris Iskandar", "Rejected"),
        ("Kai Ng", "Cancelled"),
        ("Ethan Wong", "Withdrawn"),
    ):
        assert (
            f'<span class="chip chip-mute">{state}</span>'
            in c.get("/ra-leave/history", params={"as": name}).text
        ), name
    assert (
        "Viewing as Chloe Lim" in c.get("/ra-leave/?as=Nobody").text
    )  # an unknown viewer: the default
    draft = c.get("/ra-leave/").text
    assert (
        'href="/ra-leave/apply?draft=D-0001"' in draft
    )  # the default viewer's links carry nothing
    # Every RA-side link on every RA page carries the viewer, and is a clean URL.
    for path in ("", "apply", "appeal", "cover", "history", "applications/L-0109"):
        page = c.get(f"/ra-leave/{path}?as=Hana%20Ito").text
        assert '\\"' not in page, path
        page = re.sub(r'<nav [^>]*aria-label="Sample viewer">.*?</nav>', "", page, flags=re.S)
        links = re.findall(r'href="(/ra-leave/(?!staff|admin)[^"#]*)"', page)
        assert links and all("as=Hana%20Ito" in href for href in links), (
            path,
            [h for h in links if "as=Hana" not in h],
        )


def test_each_appeal_mode_can_be_previewed() -> None:
    """The 1C.1 audit (2026-10-29): Leave policy's sample switch previews
    appeals open, by invitation or off in this browser, so their screens
    can be seen; the policy's own mode clears the preview."""
    c = TestClient(ops_app())
    assert sample_leave.policy_appeals() == "Open"
    went = c.get("/ra-leave/admin/policy/preview-appeals?mode=Off", follow_redirects=False)
    assert (
        went.status_code == 303 and went.headers["location"] == "/ra-leave/admin/policy#appeals-h"
    )
    home = c.get("/ra-leave/").text
    assert ">Previewing appeals: Off</a>" in home
    assert (
        "/ra-leave/appeal" not in home.split('class="tabs-in"')[1].split("</nav>")[0]
    )  # no Extra leave tab
    c.get("/ra-leave/admin/policy/preview-appeals?mode=By%20invitation")
    assert c.get("/ra-leave/appeal").status_code == 404  # Chloe Lim is not invited
    assert 'id="inv-ra"' in c.get("/ra-leave/admin/appeals").text  # opened for an RA
    policy = c.get("/ra-leave/admin/policy").text
    assert (
        'aria-current="true">By invitation</a>' in policy
        and ">Open (the sample policy)</a>" in policy
    )
    c.get("/ra-leave/admin/policy/preview-appeals?mode=Open")  # the policy's own mode clears it
    assert "Previewing appeals" not in c.get("/ra-leave/").text
    # A preview is the browser's: another client sees the policy itself.
    c.get("/ra-leave/admin/policy/preview-appeals?mode=Off")
    assert "Previewing appeals" not in TestClient(ops_app()).get("/ra-leave/").text
    assert (
        'href="/">Home' in c.get("/ra-leave/?as=Hana%20Ito").text
    )  # the landing does not know her


def test_the_ra_sees_an_appeal_s_split_and_a_refused_appeal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 1C.1 audit (2026-10-29): granted extra leave shows apart from
    entitlement (§7.5); a refused appeal reads in history (scenario I); the
    appeal page works an example. Lucas Teo and Maya Seah are no longer RA
    viewers (2026-11-09), so they are added back here: an RA's own record
    still shows extra leave."""
    monkeypatch.setattr(
        sample_leave,
        "RA_VIEWERS",
        (*sample_leave.RA_VIEWERS, ("Lucas Teo", ""), ("Maya Seah", "")),
    )
    c = TestClient(ops_app())
    lucas = c.get("/ra-leave/applications/L-0118?as=Lucas%20Teo").text
    assert "<dt>Extra leave</dt><dd>3 days, kept apart (spec §7.5)</dd>" in lucas
    maya = c.get("/ra-leave/history?as=Maya%20Seah").text
    assert "Rejected by Sam Lee" in maya
    assert (
        "For example, 4 days of Personal leave asked with 2 available: 2 from your entitlement, "
        "2 extra" in c.get("/ra-leave/appeal").text
    )


def test_no_ra_viewer_is_there_for_extra_leave_alone() -> None:
    """Author, 2026-11-09: extra leave is not shown to RAs, so the RA pages'
    viewers no longer include those whose only state was an appeal; a name
    not among them falls back to Chloe Lim."""
    names = [name for name, _ in sample_leave.RA_VIEWERS]
    assert names == ["Chloe Lim", "Hana Ito", "Ethan Wong", "Faris Iskandar", "Kai Ng"]
    card = TestClient(ops_app()).get("/ra-leave/").text.split('id="sample-viewer"')[1]
    assert "appeal" not in card and "Gwen Ho" not in card
    assert sample_leave.ra_viewer("Lucas Teo") == "Chloe Lim"


def test_apply_names_approvers_and_blackouts_and_warns_on_a_draft_over_balance() -> None:
    """The 1C.1 audit (2026-10-29): Apply names the RA's approvers (§9.1)
    and this term's blackouts (§6); a draft asking more than the RA has says
    so on Apply and in the lists (§10, scenario G)."""
    c = TestClient(ops_app())
    apply = c.get("/ra-leave/apply").text
    assert f"Your approvers, from your slot: {sample_leave.approvers_for('Chloe Lim')}." in apply
    assert sample_leave.approvers_for("Chloe Lim") == "Daniel Koh, then Rachel Yeo"
    assert "Examinations, 15 Nov – 28 Nov: appeal only" in apply
    assert "Move-in and orientation" not in apply  # over already
    draft = sample_leave.my_drafts()[0]
    assert sample_leave.draft_short(draft) == 2  # 3 days of Official leave, 1 available
    assert (
        "It asks 2 days more Official leave than you have: submitting it offers Request extra "
        "leave instead." in c.get(f"/ra-leave/apply?draft={draft.id}").text
    )
    assert (
        '<span class="chip chip-warn">2 days over your Official leave</span>'
        in c.get("/ra-leave/").text
    )


def test_apply_s_blackouts_follow_whether_the_ra_may_appeal() -> None:
    """Cold read, 2026-10-29: with appeals off, an Appeal-only blackout
    admits no leave, as the form above it says."""
    c = TestClient(ops_app())
    c.cookies.set(sample_leave.PREVIEW_COOKIE, "Off")
    apply = c.get("/ra-leave/apply").text
    assert "Leave in a blackout cannot be submitted." in apply  # no word of appeals
    assert "Examinations, 15 Nov – 28 Nov: no leave" in apply and "appeal only" not in apply


def test_at_the_default_open_is_previewed_and_by_invitation_clears_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guide's default flow: the policy is By invitation, so previewing
    Open shows Chloe the Extra leave tab and By invitation clears it."""
    monkeypatch.undo()
    assert sample_leave.policy_appeals() == "By invitation"
    c = TestClient(ops_app())
    c.get("/ra-leave/admin/policy/preview-appeals?mode=Open")
    home = c.get("/ra-leave/").text
    assert ">Previewing appeals: Open</a>" in home
    assert "/ra-leave/appeal" in home.split('class="tabs-in"')[1].split("</nav>")[0]
    assert c.get("/ra-leave/appeal").status_code == 200
    c.get("/ra-leave/admin/policy/preview-appeals?mode=By%20invitation")
    assert "Previewing appeals" not in c.get("/ra-leave/").text
    assert c.get("/ra-leave/appeal").status_code == 404


def test_extra_leave_is_by_invitation_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Author, 2026-11-09: a default deployment does not show extra leave
    to RAs. An RA appeals offline; if it is agreed, an admin opens an
    invitation, and only that RA is then offered the appeal page. To an RA
    not invited (Chloe Lim) no page offers it: no Extra leave tab, no
    Request extra leave, no hint on Apply, no Extra leave in the balance,
    and the appeal page is not there; the invited RA (Kai Ng) has it."""
    assert sample_leave.APPEALS_DEFAULT == "By invitation"
    monkeypatch.undo()  # this file's fixture opens appeals; see the shipped policy
    assert sample_leave.policy_appeals() == sample_leave.APPEALS_DEFAULT
    kai = TestClient(ops_app())
    assert kai.get("/ra-leave/appeal?as=Kai%20Ng").status_code == 200
    client = TestClient(ops_app())
    for path in (
        "/ra-leave/",
        "/ra-leave/apply",
        "/ra-leave/cover",
        "/ra-leave/history",
        "/ra-leave/applications/L-0101",
    ):
        page = client.get(path).text
        assert 'href="/ra-leave/appeal' not in page, path
        assert ">Extra leave<" not in page and "Request extra leave" not in page, path
    assert client.get("/ra-leave/appeal").status_code == 404


def test_cover_has_a_summary_beside_its_cards() -> None:
    """Author, 2026-11-09: Cover's side column sums up an RA's cover, as
    Apply's Available to you does: days covered, days now or upcoming,
    requests to answer and declined."""
    page = client().get(RA + "cover").text
    main, side = page.split('<div class="side">')
    assert 'id="answer-h"' in main and 'id="summary-h"' in side
    s = sample_leave.cover_summary("Chloe Lim")
    assert s["to_answer"] == 1  # Ethan Wong, 4 Dec – 6 Dec
    assert f"<dt>Requests to answer</dt><dd>{s['to_answer']}</dd>" in side
    assert f"<dt>Days now or upcoming</dt><dd>{s['coming']}</dd>" in side
    assert f"<dt>Days covered</dt><dd>{s['covered']}</dd>" in side
    assert f"<dt>Declined</dt><dd>{s['declined']}</dd>" in side
    # The sample viewers each read differently (the cold read's table).
    assert {
        n: tuple(sample_leave.cover_summary(n).values()) for n, _ in sample_leave.RA_VIEWERS
    } == {
        "Chloe Lim": (0, 2, 1, 1),
        "Hana Ito": (1, 0, 0, 0),
        "Ethan Wong": (0, 3, 0, 0),
        "Faris Iskandar": (2, 0, 0, 0),
        "Kai Ng": (0, 0, 1, 0),
    }


def test_home_s_side_shows_only_the_cards_an_ra_has() -> None:
    """Kai Ng has a cover request and no drafts; Hana Ito only her
    applications: the side keeps its order and leaves out the rest."""
    kai = client().get(RA + "?as=Kai%20Ng").text.split('<div class="side">')[1]
    assert kai.index('id="mine-h"') < kai.index('id="ask-h"') and 'id="drafts-h"' not in kai
    hana = client().get(RA + "?as=Hana%20Ito").text.split('<div class="side">')[1]
    assert 'id="mine-h"' in hana and 'id="drafts-h"' not in hana and 'id="ask-h"' not in hana


def test_apply_puts_dates_beside_leave_type_and_its_day_count() -> None:
    """Author, 2026-11-09: First day and Last day on the left, Leave type
    and the days of leave on the right (that order on a phone), then
    Covering RA and Remarks the full width."""
    page = client().get(RA + "apply").text
    pair = page.split('class="form-pair"')[1].split('class="field-wide full"')[0]
    order = [pair.index(f'id="{i}"') for i in ("first", "last", "ltype", "days")]
    assert order == sorted(order)
    left, right = re.split(r"</div>\s*</div>\s*<div>", pair, maxsplit=1)
    assert 'id="first"' in left and 'id="last"' in left and 'id="ltype"' not in left
    assert 'id="ltype"' in right and 'id="days"' in right
    assert '<label for="days">Days of leave</label>' in right  # an accessible name
    assert 'id="days-note"' in pair and "Choose your dates." in pair
    after = page.split('class="form-pair"')[1]
    assert after.index('for="cover"') < after.index('for="remarks"')
    assert '<div class="field-wide full"><label for="remarks">' in page
    assert '<div class="field-wide full"><label for="cover">' in page
    draft = sample_leave.my_drafts("Chloe Lim")[0]
    with_draft = client().get(RA + f"apply?draft={draft.id}").text
    assert f">{draft.days} day{'s' if draft.days != 1 else ''}</output>" in with_draft


def test_the_dates_are_checked_as_they_are_keyed_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Author, 2026-11-09: under Days of leave, what is wrong with the
    dates; the form may be sent only when they pass. An appeal may run past
    the balance or into an Appeal-only blackout."""
    from datetime import timedelta

    check, t = sample_leave.check_dates, sample_leave.TODAY
    one = timedelta(days=1)

    def msg(first, last, appeal=False, kind="Personal leave", ra="Chloe Lim"):
        return check(ra, kind, first, last, appeal)

    assert msg(None, None) == {"days": None, "message": "Choose your dates.", "ok": False}
    assert msg(t + 5 * one, t + 3 * one)["message"] == "The last day is before the first day."
    assert msg(t - 2 * one, t)["message"] == "The first day has passed."
    assert "Leave falls within" in msg(t + one, sample_leave.TERM.end + one)["message"]
    assert msg(t + one, t + one) == {"days": 1, "message": "", "ok": True}
    # Where she may appeal, more than her balance or an Appeal-only blackout
    # still submits, with a note, not a refusal (author, 2026-10-29; §7.2).
    over = msg(t + one, t + 5 * one)  # 5 days; Chloe Lim has 2 Personal leave
    assert over["days"] == 5 and over["ok"]
    assert over["message"].startswith(
        "3 days more than your Personal leave (2 available): submitting offers Request extra leave"
    )
    assert msg(t + one, t + 5 * one, appeal=True) == {"days": 5, "message": "", "ok": True}
    exams = (sample_leave.date(2026, 11, 16), sample_leave.date(2026, 11, 17))
    assert msg(*exams)["ok"] and "Appeal-only blackout (Examinations" in msg(*exams)["message"]
    assert msg(*exams, appeal=True) == {"days": 2, "message": "", "ok": True}
    # Her own live leave, and an unknown leave type, are refused (§10).
    mine = next(
        a for a in sample_leave.my_applications("Chloe Lim") if a.stage in sample_leave.OPEN_STAGES
    )
    clash = msg(mine.start, mine.end)
    assert not clash["ok"] and clash["message"].startswith("These dates overlap your leave of")
    assert msg(t + one, t + one, kind="Bogus leave")["message"] == "Choose a leave type."
    # Without appeals open to her, she is told to shorten it, and a blackout
    # is simply no leave.
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    assert msg(t + one, t + 5 * one)["message"].endswith("shorten it.")
    assert msg(*exams)["message"].endswith(": no leave.")
    # A weekend alone under a weekdays count counts no days.
    monkeypatch.setitem(sample_leave.POLICY, "day_count", "Weekdays")
    saturday = t + timedelta(days=(5 - t.weekday()) % 7 or 7)
    assert msg(saturday, saturday + one) == {
        "days": 0,
        "message": "These dates count no days of leave.",
        "ok": False,
    }


def test_the_check_answers_as_json_for_the_viewer() -> None:
    c = TestClient(ops_app())
    got = c.get(
        "/ra-leave/check-dates",
        params={"first": "2026-10-29", "last": "2026-11-02", "type": "Personal leave"},
    ).json()
    assert (
        got["days"] == 5
        and got["ok"] is True  # with a note: appeals are open here
        and "more than your Personal leave" in got["message"]
    )
    assert c.get("/ra-leave/check-dates", params={"first": "nonsense"}).json()["message"] == (
        "Choose your dates."
    )
    appeal = c.get(
        "/ra-leave/check-dates",
        params={"first": "2026-10-29", "last": "2026-11-02", "appeal": "1"},
    ).json()
    assert appeal["ok"] is True


def test_submit_is_disabled_until_the_dates_pass() -> None:
    """Apply's Submit and the appeal's Send start disabled; a draft whose
    dates pass opens with Submit enabled. The appeal page shares Apply's
    dates block and its full-width fields (author, 2026-11-09)."""
    c = client()
    send = '<button type="button" id="send" aria-describedby="days-note" class="btn btn-primary"'
    assert f"{send} disabled>Submit</button>" in c.get(RA + "apply").text
    appeal = c.get(RA + "appeal").text
    assert (
        'id="send" aria-describedby="days-note" class="btn btn-primary" disabled>Send to the Master'
        in appeal
    )
    assert 'class="form-pair" data-date-check=' in appeal and 'data-appeal="1"' in appeal
    assert '<div class="field-wide full"><label for="reason">' in appeal
    for d in sample_leave.my_drafts("Chloe Lim"):
        ok = sample_leave.check_dates("Chloe Lim", d.leave_type, d.start, d.end)["ok"]
        page = c.get(RA + f"apply?draft={d.id}").text
        assert (f"{send}>Submit</button>" in page) is ok


def test_at_the_default_an_ra_not_invited_is_simply_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """By invitation, the default (2026-11-09): Chloe Lim, not invited, is
    told to shorten it and a blackout is no leave; Kai Ng, invited, gets
    the appeal notes, and his ?as= reaches the JSON check."""
    monkeypatch.undo()
    t = sample_leave.TODAY
    from datetime import timedelta

    one = timedelta(days=1)
    chloe = sample_leave.check_dates("Chloe Lim", "Personal leave", t + one, t + 5 * one)
    assert not chloe["ok"] and chloe["message"].endswith("shorten it.")
    exams = (sample_leave.date(2026, 11, 16), sample_leave.date(2026, 11, 17))
    assert sample_leave.check_dates("Chloe Lim", "Personal leave", *exams)["message"].endswith(
        ": no leave."
    )
    kai = (
        TestClient(ops_app())
        .get(
            "/ra-leave/check-dates",
            params={
                "as": "Kai Ng",
                "first": "2026-11-16",
                "last": "2026-11-17",
                "type": "Personal leave",
            },
        )
        .json()
    )
    assert kai["ok"] and "Appeal-only blackout" in kai["message"]
    # Appeal rules only for an RA who may appeal: Chloe's appeal=1 is ignored.
    got = (
        TestClient(ops_app())
        .get(
            "/ra-leave/check-dates",
            params={"first": "2026-11-16", "last": "2026-11-17", "appeal": "1"},
        )
        .json()
    )
    assert not got["ok"] and got["message"].endswith(": no leave.")


def test_an_ra_withdraws_pending_leave_to_draft_and_cancels_approved_leave() -> None:
    """Author, 2026-11-10: on an application's page, pending ordinary leave
    can be withdrawn back to the drafts, and approved leave not yet begun
    cancelled; leave already begun is the Residential Admin's."""
    by = sample_leave.by_id
    pending, future, begun, past = by("L-0101"), by("L-0115"), by("L-0106"), by("L-0112")
    assert pending and future and begun and past
    assert sample_leave.withdraws_to_draft(pending) and not sample_leave.can_cancel(pending)
    assert sample_leave.can_cancel(future) and not sample_leave.can_withdraw(future)
    assert not sample_leave.can_cancel(begun) and not sample_leave.can_cancel(past)
    appeal = by("L-0105")
    assert appeal and sample_leave.can_withdraw(appeal)
    assert not sample_leave.withdraws_to_draft(appeal)

    c = client()
    chloe = c.get(RA + "applications/L-0101").text
    assert "back to your drafts, filled in as you sent it" in chloe
    assert "Cancel leave" not in chloe
    hana = c.get(RA + "applications/L-0115?as=Hana%20Ito").text
    assert 'aria-label="Cancel leave, 14 Dec – 15 Dec" disabled>Cancel leave</button>' in hana
    assert "gives back its 2 days" in hana and "Withdraw" not in hana
    # No sample RA viewer has leave under way or an appeal pending; the rules
    # above cover those. Leave already taken offers nothing.
    done = c.get(RA + "applications/L-0117").text  # Chloe's, 25 Sep
    assert "Cancel leave</button>" not in done and "Withdraw" not in done
    kai = c.get(RA + "applications/L-0116?as=Kai%20Ng").text  # already cancelled
    assert "Cancel leave</button>" not in kai and "Withdraw" not in kai
