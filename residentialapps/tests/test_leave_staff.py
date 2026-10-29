"""RA Leave's staff pages (`/ra-leave/staff/`), segment 1C item 1:
placeholders on `sample_leave`, drawn for a sample viewer chosen with
`?as=` (an RF, the admin, the Master)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_leave
from residentialapps.residentialops.main import create_app as ops_app

STAFF = "/ra-leave/staff/"
RACHEL = "?as=Rachel%20Yeo"
SAM = "?as=Sam%20Lee"


def client() -> TestClient:
    return TestClient(ops_app())


def ids(html: str, section: str) -> list[str]:
    part = html.split(f'id="{section}"')[1].split("</section>")[0]
    return re.findall(r'href="/ra-leave/staff/decide/(L-\d+)', part)


def test_every_staff_page_answers_for_each_sample_viewer() -> None:
    c = client()
    for query, name in (("", "Daniel Koh"), (RACHEL, "Rachel Yeo"), (SAM, "Sam Lee")):
        for path in ("", "decide", "decided", "precinct"):
            page = c.get(STAFF + path + query)
            assert page.status_code == 200, (path, query)
            assert "Sample data" in page.text and f"Viewing as {name}" in page.text, (path, query)
            assert 'aria-current="true">' in page.text
    tabs = c.get(STAFF + RACHEL).text.split('class="tabs-in"')[1].split("</nav>")[0]
    assert re.findall(r'<a href="([^"]*)"', tabs) == [
        f"/ra-leave/staff/{p}{RACHEL}" for p in ("", "decide", "decided", "precinct", "appeals")
    ]
    # Every overseer gets the same tabs, Appeals included while appeals are on.
    assert "/ra-leave/staff/appeals" in c.get(STAFF).text.split('class="tabs-in"')[1].split("</nav>")[0]
    assert sample_leave.staff_viewer("Nobody") == "Daniel Koh"


def test_each_viewer_s_queue_is_the_decision_theirs_to_make() -> None:
    """Spec §16, §24: first approval for the slot's approver, final for the
    policy's final approver, appeals for the Master; oldest first."""
    c = client()
    assert ids(c.get(STAFF + "decide").text, "queue-h") == ["L-0109", "L-0101", "L-0114"]
    assert ids(c.get(STAFF + "decide" + RACHEL).text, "queue-h") == ["L-0103"]
    assert ids(c.get(STAFF + "decide" + SAM).text, "queue-h") == ["L-0105"]
    home = c.get(STAFF).text
    tiles = re.findall(r'<span class="tile-n">(\d+)</span><span class="tile-l">([^<]*)', home)
    assert tiles == [("3", "Awaiting my decision"), ("2", "Of those, waiting on cover"), ("2", "Decided")]
    waiting = c.get(STAFF + "decide?cover=waiting").text
    assert ids(waiting, "queue-h") == ["L-0109", "L-0114"]
    assert 'href="/ra-leave/staff/decide?as=Sam%20Lee&amp;cover=waiting"' in c.get(STAFF + SAM).text


def test_decide_shows_entitlement_cover_and_precinct_context() -> None:
    c = client()
    hana = c.get(STAFF + "decide/L-0109").text
    assert ">Waiting on cover</span> Chloe Lim has declined; the RA must name new cover" in hana
    assert ">Approve</button>" in hana
    assert "<dt>Available</dt><dd>0 days</dd>" in hana
    appeal = c.get(STAFF + "decide/L-0105" + SAM).text
    assert "Decide the appeal" in appeal and "<dt>Beyond entitlement</dt><dd>4 days</dd>" in appeal
    assert "kept apart from the entitlement" in appeal
    clash = c.get(STAFF + "decide/L-0108" + SAM).text  # Pranav Iyer, decided: read-only
    assert "Decided; shown read-only." in clash and ">Approve</button>" not in clash
    ctx = clash.split('id="ctx-h"')[1].split("</section>")[0]
    assert "Olivia Ng" in ctx


def test_a_staff_member_sees_only_their_scope() -> None:
    """Spec §22: an RF their Precinct(s), the admin and the Master the
    whole Unit; Decide 404s outside the viewer's scope."""
    c = client()
    assert sample_leave.scope("Daniel Koh") == ("Cypress A 04-12",)
    assert len(sample_leave.scope("Marcus Tan")) == 3  # an RSLM: the Maple Wing
    assert len(sample_leave.scope("Sam Lee")) == 9
    assert c.get(STAFF + "decide/L-0105").status_code == 404  # Maple 09-14, not Daniel Koh's
    assert c.get(STAFF + "decide/L-9999" + SAM).status_code == 404
    precinct = c.get(STAFF + "precinct").text
    assert "Isaac Goh" not in precinct and "Ethan Wong" in precinct


def test_decided_lists_the_viewer_s_own_decisions() -> None:
    c = client()
    assert ids(c.get(STAFF + "decided").text, "dec-h") == ["L-0115", "L-0117"]
    rachel = c.get(STAFF + "decided" + RACHEL).text
    assert len(ids(rachel, "dec-h")) == 9 and "Final approval: Approved" in rachel
    assert ids(c.get(STAFF + "decided" + SAM).text, "dec-h") == ["L-0118"]  # the appeal the Master granted


def test_whatever_a_viewer_may_decide_opens(monkeypatch) -> None:
    """Every row in a viewer's queue or Decided list opens Decide, under
    each approval setting, a delegate's and a named approver's included."""
    import itertools

    c = client()
    people = ("Daniel Koh", "Rachel Yeo", "Sam Lee", "Benjamin Chua", "Grace Ho", "Marcus Tan", "Mei Ling Tan")
    settings = (
        {}, {"first_types": ("RF", "RSLM")}, {"first": "none"},
        {"final": "named", "final_names": ("Daniel Koh",)}, {"appeals": "Off"}, {"appeals": "By invitation"},
    )
    for setting, day in itertools.product(settings, (None, sample_leave.date(2026, 12, 10))):
        with monkeypatch.context() as m:
            for key, value in setting.items():
                m.setitem(sample_leave.POLICY, key, value)
            if day:
                m.setattr(sample_leave, "routes", lambda d=None, _r=sample_leave.routes: _r(day))
            for person in people:
                for a in [a for a, _ in sample_leave.queue(person)] + [a for a, _, _ in sample_leave.decided(person)]:
                    assert sample_leave.can_open(person, a), (setting, day, person, a.id)
    assert c.get(STAFF + "decide/L-0103?as=Benjamin%20Chua").status_code == 404  # not a staff viewer: defaults to Daniel
    assert sample_leave.can_open("Benjamin Chua", sample_leave.by_id("L-0103"))  # standing in for Grace Ho


def test_with_no_first_approval_rejections_belong_to_the_final_approver(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert ("L-0110", "Final approval", "Rejected") in [(a.id, r, o) for a, r, o in sample_leave.decided("Rachel Yeo")]


def test_decide_shows_the_applicant_s_other_leave_and_precinct_numbers() -> None:
    c = client()
    appeal = c.get(STAFF + "decide/L-0105" + SAM).text.split('id="own-h"')[1].split("</section>")[0]
    assert appeal.count("<li>") == 2 and "17 Aug – 19 Aug" in appeal
    rows = re.findall(r'<td class="strong nowrap">([^<]*)</td><td class="num">(\d+)</td><td class="num">(\d+)</td><td class="num">(\d+)</td>',
                      c.get(STAFF + "precinct" + SAM).text)
    assert ("Willow A 13-25", "4", "2", "0") in rows and len(rows) == 9


def test_the_master_and_the_admin_delegate_open_appeals_from_the_staff_pages() -> None:
    """Ruled 2026-10-29: as on the admin Appeals page, with the agreer
    preset to the viewer and links into Decide."""
    c = client()
    for query, name in ((SAM, "Sam Lee"), (RACHEL, "Rachel Yeo")):
        page = c.get(STAFF + "appeals" + query).text
        assert f"<option selected>{name}</option>" in page and ">Open the appeal</button>" in page
        assert f'href="/ra-leave/staff/decide/L-0105{query}">Sent: L-0105</a>' in page
        assert c.get(f"/ra-leave/staff/decide/L-0105{query}").status_code == 200
    for query in ("", "?as=Daniel%20Koh"):
        page = c.get(STAFF + "appeals" + query).text
        assert "you are not among them" in page and ">Open the appeal</button>" not in page


def test_who_may_open_an_appeal_follows_the_policy(monkeypatch) -> None:
    """Ruled 2026-10-29: chosen as approvers are. The RA's slot's RF opens
    appeals for their own slots' RAs only; named staff for anyone."""
    c = client()
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "slot")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_types", ("RF",))
    assert sample_leave.inviters_for("Chloe Lim") == ("Daniel Koh",)
    assert sample_leave.invitable_ras("Daniel Koh") == ("Chloe Lim", "Ethan Wong", "Hana Ito")
    page = c.get(STAFF + "appeals").text
    assert "3 RAs you may" in page and "<option selected>Daniel Koh</option>" in page
    pool = page.split('id="ra-names"')[1].split("</datalist>")[0]
    assert re.findall(r'value="([^"]*)"', pool) == ["Chloe Lim", "Ethan Wong", "Hana Ito"]
    assert "read-only for you" in c.get(STAFF + "appeals" + SAM).text  # Sam oversees, may not open
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Rachel Yeo",))
    assert sample_leave.all_inviters() == ("Rachel Yeo",)
    assert "you are not among them" in c.get(STAFF + "appeals" + SAM).text



def test_inviter_settings_at_their_edges(monkeypatch) -> None:
    c = client()
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Rachel Yeo",))
    rachel = c.get(STAFF + "appeals" + RACHEL).text
    assert f"{len(sample_leave.sample_data.RAS)} RAs you may" in rachel
    assert '/ra-leave/staff/appeals' in c.get(STAFF + RACHEL).text.split('class="tabs-in"')[1].split("</nav>")[0]
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ())
    assert sample_leave.inviter_label() == "" and sample_leave.all_inviters() == ()
    assert "Leave policy names no one to open appeals." in c.get(STAFF + "appeals" + SAM).text
    assert "No one may open an appeal: Leave policy names no one for it." in c.get("/ra-leave/admin/appeals").text
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "slot")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_types", ("RF", "RSLM"))
    assert sample_leave.inviters_for("Chloe Lim") == ("Daniel Koh", "Priya Raman")
    assert sample_leave.inviters_for("Nobody") == ()  # on no slot: no one may
    policy = c.get("/ra-leave/admin/policy").text
    assert re.findall(r'name="inviter-slot-types" value="(\w+)"( checked)?', policy) == [("RF", " checked"), ("RSLM", " checked")]
    assert 'name="inviters" value="slot" checked' in policy
    agreed = c.get("/ra-leave/admin/appeals").text.split('id="inv-by"')[1].split("</select>")[0]
    assert agreed.count("<option>") == 9 + 3  # every RF and RSLM on a slot


def test_a_staff_appeals_page_lists_only_the_viewer_s_ras(monkeypatch) -> None:
    """Codex on #3344: the staff page's tables follow the RAs the viewer
    may open appeals for; the admin page keeps every one, and every link
    on either opens."""
    c = client()
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "slot")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_types", ("RF",))
    page = c.get(STAFF + "appeals").text  # Daniel Koh: Cypress A 04-12's RAs
    assert "Gwen Ho" not in page and "L-0105" not in page and "Invitations <span class=\"count\">· 0" in page
    benjamin = c.get(STAFF + "appeals?as=Benjamin%20Chua")
    assert benjamin.status_code == 200  # not a sample viewer: Daniel Koh's page
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Daniel Koh",))
    page = c.get(STAFF + "appeals").text
    assert "Gwen Ho" in page
    for link in re.findall(r'href="(/ra-leave/staff/decide/L-\d+)"', page):
        assert c.get(link).status_code == 200, link
    admin = c.get("/ra-leave/admin/appeals").text
    assert "Invitations <span class=\"count\">· 3" in admin


def test_review_fixes_on_the_staff_side(monkeypatch) -> None:
    """The 2026-10-29 review: back links and tabs follow where a Decide page
    was opened from, a decided application shows no wait, and the sample
    viewers' roles follow the policy."""
    c = client()
    queued = sample_leave.queue("Daniel Koh")[0][0]
    page = c.get(STAFF + "decide/" + queued.id).text
    assert "‹ Awaiting my decision" in page and 'href="/ra-leave/staff/decide" aria-current="true"' in page
    past = sample_leave.decided("Daniel Koh")[0][0]
    page = c.get(STAFF + "decide/" + past.id).text
    assert "‹ Decided" in page and "<dt>Waiting</dt>" not in page
    assert 'href="/ra-leave/staff/decided" aria-current="true"' in page
    # An appeal opened from Appeals goes back there, not to Precinct leave.
    page = c.get(STAFF + "decide/L-0105" + RACHEL).text
    assert "‹ Appeals" in page and 'href="/ra-leave/staff/appeals?as=Rachel%20Yeo" aria-current="true"' in page
    assert "Daniel Koh: RF, first approver for" in c.get(STAFF).text
    assert "opens appeals" not in c.get(STAFF).text  # appeals are open: no one opens them
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    assert "Sam Lee: Master, decides appeals, opens appeals" in c.get(STAFF).text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Open")
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("RSLM",))
    assert "Daniel Koh: RF, no decisions under the policy" in c.get(STAFF).text
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    # Recorded as awaiting first approval, they now await final approval.
    assert sample_leave.by_id("L-0101").stage == "Pending final approval"
    assert "L-0101" in [a.id for a, _ in sample_leave.queue("Rachel Yeo")]
    # The switcher lists what a staff viewer reaches, keeping `?as=`.
    menu = c.get(STAFF + RACHEL).text.split('aria-label="Switch area"')[1].split("</nav>")[0]
    assert 'href="/ra-leave/staff/?as=Rachel%20Yeo"' in menu and 'href="/sys-admin/"' in menu
    assert "/sys-admin/" not in c.get(STAFF).text.split('aria-label="Switch area"')[1].split("</nav>")[0]


def test_leave_shows_only_to_staff_who_oversee_ras(monkeypatch) -> None:
    """Ruled 2026-10-29: the Master and the designated admin oversee every
    RA, as if in every slot; an RF and an RSLM the RAs on their slots;
    Unit-level staff holding no slot see no RA Leave. The pages are the
    same for every overseer; actions follow the approval chain."""
    c = client()
    assert sample_leave.overseers() == ("Sam Lee", "Rachel Yeo")
    assert len(sample_leave.scope("Priya Raman")) == 3  # an RSLM: the Cypress Wing
    assert sample_leave.scope("Hui Min Goh") == ()
    page = c.get(STAFF + "?as=Hui%20Min%20Goh").text
    assert "You oversee no RA" in page and 'class="tabs-in"' not in page
    assert "Hui Min Goh: Residential Executive, oversees no RA, so RA Leave is not shown" in page
    assert c.get(STAFF + "decide/L-0101?as=Hui%20Min%20Goh").status_code == 404
    landing = c.get("/?as=Hui%20Min%20Goh").text
    assert "/ra-leave/" not in landing.split('<main class="page">')[1]
    # An RSLM gets the same tabs as an RF, and decides nothing by default.
    tabs = lambda q: re.findall(r'<a href="/ra-leave/staff/(\w*)', c.get(STAFF + q).text.split('class="tabs-in"')[1].split("</nav>")[0])  # noqa: E731
    assert tabs("?as=Priya%20Raman") == tabs("") == tabs(SAM) == ["", "decide", "decided", "precinct", "appeals"]
    assert "Nothing awaits you." in c.get(STAFF + "decide?as=Priya%20Raman").text
    # Untick the admin: Rachel Yeo still sees every RA, as the final approver.
    monkeypatch.setitem(sample_leave.POLICY, "overseers", ("Master",))
    assert sample_leave.overseers() == ("Sam Lee",) and len(sample_leave.scope("Rachel Yeo")) == 9
    # Tick the Executive: Hui Min Goh oversees every RA, deciding nothing.
    monkeypatch.setitem(sample_leave.POLICY, "overseers", ("Master", "Admin", "Exec"))
    assert len(sample_leave.scope("Hui Min Goh")) == 9
    assert "Nothing awaits you." in c.get(STAFF + "decide?as=Hui%20Min%20Goh").text
