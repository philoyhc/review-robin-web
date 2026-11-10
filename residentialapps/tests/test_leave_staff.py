"""RA Leave's staff pages (`/ra-leave/staff/`), segment 1C item 1:
placeholders on `sample_leave`, drawn for a sample viewer chosen with
`?as=` (an RF, the admin, the Master)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.main import create_app as ops_app

STAFF = "/ra-leave/staff/"
RACHEL = "?as=Rachel%20Yeo"
SAM = "?as=Sam%20Lee"


def _by_id(application_id: str) -> sample_leave.Application:
    """A sample application the test names, which the sample holds."""
    found = sample_leave.by_id(application_id)
    assert found is not None, application_id
    return found


def client() -> TestClient:
    return TestClient(ops_app())


def ids(html: str, section: str) -> list[str]:
    part = html.split(f'id="{section}"')[1].split("</section>")[0]
    return re.findall(r'href="/ra-leave/staff/decide/(L-\d+)', part)


def test_every_staff_page_answers_for_each_sample_viewer() -> None:
    c = client()
    for query, name in (("", "Daniel Koh"), (RACHEL, "Rachel Yeo"), (SAM, "Sam Lee")):
        for path in ("", "decided", "precinct"):
            page = c.get(STAFF + path + query)
            assert page.status_code == 200, (path, query)
            assert "Sample data" in page.text and f"Viewing as {name}" in page.text, (path, query)
            assert 'aria-current="true">' in page.text
    tabs = c.get(STAFF + RACHEL).text.split('class="tabs-in"')[1].split("</nav>")[0]
    assert re.findall(r'<a href="([^"]*)"', tabs) == [
        f"/ra-leave/staff/{p}{RACHEL}" for p in ("", "decided", "precinct", "appeals")
    ]
    # Precinct for the admin, the Master and an RSLM; My Precinct for an RF,
    # whose own Precinct it is (author, 2026-11-09).
    assert ">Precinct</a>" in tabs and "My Precinct" not in tabs
    daniel = c.get(STAFF).text
    assert ">My Precinct</a>" in daniel.split('class="tabs-in"')[1].split("</nav>")[0]
    assert ">My Precinct</a>" in daniel.split('id="week-h"')[1]  # Home's button
    precinct = c.get(STAFF + "precinct").text
    assert "<title>My Precinct" in precinct and ">My Precinct</h1>" in precinct
    assert ">Precinct</h1>" in c.get(STAFF + "precinct" + SAM).text
    # Every overseer but an RF gets Appeals while an appeal is open; an RF
    # (Daniel Koh) has no Appeals tab (author, 2026-11-09).
    assert (
        "/ra-leave/staff/appeals"
        not in c.get(STAFF).text.split('class="tabs-in"')[1].split("</nav>")[0]
    )
    assert (
        "/ra-leave/staff/appeals?as=Priya%20Raman"
        in c.get(STAFF + "?as=Priya%20Raman").text.split('class="tabs-in"')[1].split("</nav>")[0]
    )
    assert sample_leave.staff_viewer("Nobody") == "Daniel Koh"


def test_each_viewer_s_queue_is_the_decision_theirs_to_make() -> None:
    """Spec §16, §24: first approval for the slot's approver, final for the
    policy's final approver, appeals for the Master; oldest first."""
    c = client()
    # Home is the queue, every item on it, and no tiles (author, 2026-11-09).
    assert ids(c.get(STAFF).text, "await-h") == ["L-0109", "L-0101", "L-0114"]
    assert ids(c.get(STAFF + RACHEL).text, "await-h") == ["L-0103"]
    assert ids(c.get(STAFF + SAM).text, "await-h") == ["L-0105"]
    home = c.get(STAFF).text
    assert 'class="tile' not in home
    assert 'href="/ra-leave/staff/?cover=waiting">Waiting on cover · 2</a>' in home
    assert (
        'href="/ra-leave/staff/?as=Sam%20Lee&amp;cover=waiting">Waiting on cover · 1</a>'
        in c.get(STAFF + SAM).text
    )
    waiting = c.get(STAFF + "?cover=waiting").text
    assert (
        ids(waiting, "await-h") == ["L-0109", "L-0114"] and "Show everything awaiting me" in waiting
    )
    # The old Awaiting page lands on Home, its query kept.
    went = c.get(STAFF + "decide" + SAM + "&cover=waiting", follow_redirects=False)
    assert went.status_code == 303
    assert went.headers["location"] == "/ra-leave/staff/?as=Sam%20Lee&cover=waiting"


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
    assert ids(c.get(STAFF + "decided" + SAM).text, "dec-h") == [
        "L-0120",
        "L-0118",
    ]  # the appeals the Master refused and granted


def test_whatever_a_viewer_may_decide_opens(monkeypatch) -> None:
    """Every row in a viewer's queue or Decided list opens Decide, under
    each approval setting, a delegate's and a named approver's included."""
    import itertools

    c = client()
    people = (
        "Daniel Koh",
        "Rachel Yeo",
        "Sam Lee",
        "Benjamin Chua",
        "Grace Ho",
        "Marcus Tan",
        "Mei Ling Tan",
        "Priya Raman",
    )
    settings = (
        {},
        {"first_types": ("RF", "RSLM")},
        {"first": "none"},
        {"final": "named", "final_names": ("Daniel Koh",)},
        {"appeals": "Open"},
        {"appeals": "Off"},
    )
    for setting, day in itertools.product(settings, (None, sample_leave.date(2026, 12, 10))):
        with monkeypatch.context() as m:
            for key, value in setting.items():
                m.setitem(sample_leave.POLICY, key, value)
            if day:
                m.setattr(
                    sample_leave,
                    "routes",
                    lambda d=None, _r=sample_leave.routes, _day=day: _r(_day),
                )
            for person in people:
                for a in [a for a, _ in sample_leave.queue(person)] + [
                    a for a, _, _ in sample_leave.decided(person)
                ]:
                    assert sample_leave.can_open(person, a), (setting, day, person, a.id)
    assert (
        c.get(STAFF + "decide/L-0103?as=Benjamin%20Chua").status_code == 404
    )  # not a staff viewer: defaults to Daniel
    assert sample_leave.can_open("Marcus Tan", _by_id("L-0103"))  # standing in for Grace Ho


def test_with_no_first_approval_rejections_belong_to_the_final_approver(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert ("L-0110", "Final approval", "Rejected") in [
        (a.id, r, o) for a, r, o in sample_leave.decided("Rachel Yeo")
    ]


def test_decide_shows_the_applicant_s_other_leave_and_precinct_numbers() -> None:
    c = client()
    appeal = c.get(STAFF + "decide/L-0105" + SAM).text.split('id="own-h"')[1].split("</section>")[0]
    assert appeal.count("<li>") == 2 and "17 Aug – 19 Aug" in appeal
    rows = re.findall(
        (
            r'<td class="strong nowrap">([^<]*)</td><td class="num">(\d+)</td>'
            r'<td class="num">(\d+)</td><td class="num">(\d+)</td>'
        ),
        c.get(STAFF + "precinct" + SAM).text,
    )
    assert ("Willow A 13-25", "4", "2", "0") in rows and len(rows) == 9


def test_the_master_and_the_admin_delegate_open_appeals_from_the_staff_pages(monkeypatch) -> None:
    """Ruled 2026-10-29: as on the admin Appeals page, with the agreer
    preset to the viewer and links into Decide."""
    c = client()
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")  # where appeals are opened
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
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")  # where appeals are opened
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
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")  # where appeals are opened
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Rachel Yeo",))
    rachel = c.get(STAFF + "appeals" + RACHEL).text
    assert f"{len(sample_leave.sample_data.RAS)} RAs you may" in rachel
    assert (
        "/ra-leave/staff/appeals"
        in c.get(STAFF + RACHEL).text.split('class="tabs-in"')[1].split("</nav>")[0]
    )
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ())
    assert sample_leave.inviter_label() == "" and sample_leave.all_inviters() == ()
    assert "Leave policy names no one to open appeals." in c.get(STAFF + "appeals" + SAM).text
    assert (
        "Leave policy names no one to open appeals." in c.get("/ra-leave/admin/appeals").text
    )  # as the staff page
    assert 'id="inv-ra"' not in c.get("/ra-leave/admin/appeals").text
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "slot")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_types", ("RF", "RSLM"))
    assert sample_leave.inviters_for("Chloe Lim") == ("Daniel Koh", "Priya Raman")
    assert sample_leave.inviters_for("Nobody") == ()  # on no slot: no one may
    policy = c.get("/ra-leave/admin/policy").text
    assert re.findall(r'name="inviter-slot-types" value="(\w+)"( checked)?', policy) == [
        ("RF", " checked"),
        ("RSLM", " checked"),
    ]
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
    assert (
        "Gwen Ho" not in page
        and "L-0105" not in page
        and 'Invitations <span class="count">· 0' in page
    )
    benjamin = c.get(STAFF + "appeals?as=Benjamin%20Chua")
    assert benjamin.status_code == 200  # not a sample viewer: Daniel Koh's page
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Daniel Koh",))
    page = c.get(STAFF + "appeals").text
    # Named, he still opens appeals only for RAs in his slots (ruled 2026-10-29).
    assert "Gwen Ho" not in page and sample_leave.invitable_ras("Daniel Koh") == (
        "Chloe Lim",
        "Ethan Wong",
        "Hana Ito",
    )
    for link in re.findall(r'href="(/ra-leave/staff/decide/L-\d+)"', page):
        assert c.get(link).status_code == 200, link
    admin = c.get("/ra-leave/admin/appeals").text
    assert 'Invitations <span class="count">· 3' in admin


def test_review_fixes_on_the_staff_side(monkeypatch) -> None:
    """The 2026-10-29 review: back links and tabs follow where a Decide page
    was opened from, a decided application shows no wait, and the sample
    viewers' roles follow the policy."""
    c = client()
    queued = sample_leave.queue("Daniel Koh")[0][0]
    page = c.get(STAFF + "decide/" + queued.id).text
    assert "‹ Home" in page and 'href="/ra-leave/staff/" aria-current="true"' in page
    past = sample_leave.decided("Daniel Koh")[0][0]
    page = c.get(STAFF + "decide/" + past.id).text
    assert "‹ Decided" in page and "<dt>Waiting</dt>" not in page
    assert 'href="/ra-leave/staff/decided" aria-current="true"' in page
    # An appeal opened from Appeals goes back there, not to Precinct.
    page = c.get(STAFF + "decide/L-0105" + RACHEL).text
    assert (
        "‹ Appeals" in page
        and 'href="/ra-leave/staff/appeals?as=Rachel%20Yeo" aria-current="true"' in page
    )
    assert "Daniel Koh: RF, first approver for" in c.get(STAFF).text
    # By invitation, the default (2026-11-09), Sam Lee opens appeals ...
    assert "Sam Lee: Master, decides appeals, opens appeals" in c.get(STAFF).text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Open")
    assert "opens appeals" not in c.get(STAFF).text  # ... open, no one opens them
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    assert "Sam Lee: Master, decides appeals, opens appeals" in c.get(STAFF).text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Open")
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("RSLM",))
    assert "Daniel Koh: RF, no decisions under the policy" in c.get(STAFF).text
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    # Recorded as awaiting first approval, they now await final approval.
    assert _by_id("L-0101").stage == "Pending final approval"
    assert "L-0101" in [a.id for a, _ in sample_leave.queue("Rachel Yeo")]
    # The switcher lists what a staff viewer reaches, keeping `?as=`.
    # Sys admin is the account's, in the account menu (author, 2026-11-02).
    signed_in = {
        "X-MS-CLIENT-PRINCIPAL-NAME": "rachel@example.edu",
        "X-MS-CLIENT-PRINCIPAL-ID": "rachel-oid",
    }
    page = c.get(STAFF + RACHEL, headers=signed_in).text
    menu = page.split('aria-label="Switch area"')[1].split("</nav>")[0]
    account = page.split('aria-label="Account"')[1].split("</nav>")[0]
    assert 'href="/ra-leave/staff/?as=Rachel%20Yeo"' in menu and "/sys-admin/" not in menu
    assert 'href="/sys-admin/">Sys admin</a>' in account
    page = c.get(STAFF, headers=signed_in).text
    assert "/sys-admin/" not in page.split('aria-label="Account"')[1].split("</nav>")[0]


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
    tabs = lambda q: re.findall(  # noqa: E731
        r'<a href="/ra-leave/staff/(\w*)',
        c.get(STAFF + q).text.split('class="tabs-in"')[1].split("</nav>")[0],
    )
    assert tabs("?as=Priya%20Raman") == tabs(SAM) == ["", "decided", "precinct", "appeals"]
    assert tabs("") == ["", "decided", "precinct"]  # an RF: no Appeals tab
    assert "Nothing awaits you." in c.get(STAFF + "?as=Priya%20Raman").text
    # Untick the admin: Rachel Yeo holds no slot, so she sees no RA and
    # her final approval leaves every Precinct with a gap (ruled 2026-10-29).
    monkeypatch.setitem(
        sample_leave.sample_data.EVERY_SLOT,
        sample_leave.TERM.key,
        {"appointments": ("Master",), "names": ()},
    )
    assert sample_leave.overseers() == ("Sam Lee",) and sample_leave.scope("Rachel Yeo") == ()
    assert sample_leave.final_gaps() == sample_leave.precincts()
    # Tick the Executive: Hui Min Goh oversees every RA, deciding nothing.
    monkeypatch.setitem(
        sample_leave.sample_data.EVERY_SLOT,
        sample_leave.TERM.key,
        {"appointments": ("Master", "Admin", "Exec"), "names": ()},
    )
    assert len(sample_leave.scope("Hui Min Goh")) == 9
    assert "Nothing awaits you." in c.get(STAFF + "?as=Hui%20Min%20Goh").text


def test_oversight_follows_the_policy_setting(monkeypatch) -> None:
    """Ruled 2026-10-29: staff approve, first or final, decide or open
    appeals only for RAs in whose slots they hold a place; the overseers
    hold one in every slot. A role given elsewhere is a gap, never a view."""
    c = client()
    monkeypatch.setitem(
        sample_leave.sample_data.EVERY_SLOT,
        sample_leave.TERM.key,
        {"appointments": (), "names": ()},
    )
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    assert sample_leave.scope("Rachel Yeo") == () and sample_leave.all_inviters() == ()
    assert "the fix is in Assignments" in c.get(STAFF + RACHEL).text
    assert all(not sample_leave.decides_appeals(p) for p in sample_leave.precincts())
    routing = c.get("/ra-leave/admin/routing").text
    assert routing.count("none named holds a place in its slots") == len(sample_leave.precincts())
    # A named final approver approves only in their own slots.
    monkeypatch.setitem(
        sample_leave.sample_data.EVERY_SLOT,
        sample_leave.TERM.key,
        {"appointments": ("Master", "Admin"), "names": ()},
    )
    monkeypatch.setitem(sample_leave.POLICY, "final", "named")
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ("Daniel Koh",))
    assert (
        sample_leave.final_for("Cypress A 04-12") == ("Daniel Koh",)
        and sample_leave.final_for("Maple 03-08") == ()
    )
    assert len(sample_leave.final_gaps()) == len(sample_leave.precincts()) - 1
    # A delegate outside the slots they would stand in for does not stand in.
    D = sample_leave.Delegate
    monkeypatch.setattr(
        sample_leave,
        "DELEGATES",
        (D("Grace Ho", "Benjamin Chua", None, None, "has not signed in yet"),),
    )
    maple = next(r for r in sample_leave.routes() if r.precinct == "Maple 03-08")
    assert maple.first == "Grace Ho" and "Benjamin Chua is not in these slots" in maple.note
    assert "Not in their slots" in c.get("/ra-leave/admin/routing").text
    monkeypatch.setitem(sample_leave.POLICY, "final", "unit")
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    # Under Open, a non-inviter's Appeals page says no one opens appeals.
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Open")
    assert "every RA may send one, so none is opened for them" in c.get(STAFF + "appeals").text
    # An appeal opened from Appeals goes back there, inviter or not.
    monkeypatch.setitem(
        sample_leave.sample_data.EVERY_SLOT,
        sample_leave.TERM.key,
        {"appointments": ("Master", "Admin", "Exec"), "names": ()},
    )
    page = c.get(STAFF + "decide/L-0105?as=Hui%20Min%20Goh").text
    assert "‹ Appeals" in page


def test_precinct_leave_shows_a_chosen_period() -> None:
    """Spec §22, "for a selected period" (author, 2026-10-29): this week by
    default, next week, the next four weeks or the rest of the term; who is
    away, the Precinct counts and the clashes follow it."""
    c = client()

    def away(query: str) -> list[str]:
        page = c.get(STAFF + "precinct" + query).text
        part = page.split('id="away-h"')[1].split("</section>")[0]
        return re.findall(r'<td class="strong nowrap">([^<]+)</td>', part)

    assert sample_leave.period("bogus")[:2] == ("week", "This week")
    assert away(SAM) == away(SAM + "&period=week") == ["Maya Seah", "Olivia Ng", "Pranav Iyer"]
    assert away(SAM + "&period=next") == []
    assert "Hana Ito" in away(SAM + "&period=term") and "Hana Ito" not in away(SAM)
    week, nxt = (c.get(STAFF + "precinct" + SAM + q).text for q in ("", "&period=next"))
    assert '<option value="week" selected>This week</option>' in week
    assert '<option value="next" selected>Next week</option>' in nxt
    assert '<input type="hidden" name="as" value="Sam Lee">' in week  # the viewer survives a change
    assert (
        "Olivia Ng and Pranav Iyer" in week and "Olivia Ng and Pranav Iyer" not in nxt
    )  # clashes follow
    _, _, start, end = sample_leave.period("next")
    assert (
        sample_leave.clashes(start, end) == () and sample_leave.clashes()
    )  # none next week, some in all

    # The Precinct counts follow the period too, counting RAs.
    def counts(key: str) -> dict[str, int]:
        _, _, start, end = sample_leave.period(key)
        return {r["precinct"]: r["away"] for r in sample_leave.by_precinct("Sam Lee", start, end)}

    assert sum(counts("week").values()) == 3 and sum(counts("next").values()) == 0
    assert sum(counts("term").values()) == 4
    four = sample_leave.period("four")
    assert (four[1], four[2], four[3].toordinal() - four[2].toordinal()) == (
        "These four weeks",
        sample_leave.TODAY,
        27,
    )


def test_precinct_counts_need_both_ends_of_a_period() -> None:
    """A start with no end is no period: the counts fall back to this
    week rather than raising (segment 22C rung 5a)."""
    week = sample_leave.by_precinct("Sam Lee")
    _, _, start, _ = sample_leave.period("next")
    assert sample_leave.by_precinct("Sam Lee", start) == week
    assert sample_leave.by_precinct("Sam Lee", start, None) == week


def test_staff_see_only_the_emails_they_sent() -> None:
    """Spec §17.2 (author, 2026-10-29): the actor resends their own failed
    email from the application; another overseer sees no outbox there."""
    c = client()
    mine = c.get(STAFF + "decide/L-0115").text  # Daniel Koh approved it first
    assert ">Resend to Hana Ito</button>" in mine.split('id="emails-h"')[1].split("</section>")[0]
    assert 'id="emails-h"' not in c.get(STAFF + "decide/L-0115" + SAM).text


def test_decide_lists_this_term_s_other_leave_only() -> None:
    """Leave days go with their term (ruled 2026-10-29): Decide's other leave
    is this term's, and an empty list says so."""
    term = sample_leave.TERM
    for a in sample_leave.APPLICATIONS:
        assert all(o.start <= term.end and o.end >= term.start for o in sample_leave.other_leave(a))
    lucas = _by_id("L-0118")
    assert [o.id for o in sample_leave.other_leave(lucas)] == ["L-0119"]
    assert sample_leave.delegate_choices("Hui Min Goh") == []  # in no slot


def test_the_audit_s_appeal_screens() -> None:
    """The 1C.1 audit (2026-10-29): staff in the RA's slot add remarks to an
    appeal for the Master (§15); the Master may decide over unconfirmed
    cover (§7.4); a refused appeal is decided; an appeal's days split
    between entitlement and extra leave (§7.5); blackouts show."""
    c = client()
    rachel = c.get(STAFF + "decide/L-0105" + RACHEL).text  # in every slot, not the decider
    assert "Your remarks for the Master" in rachel and ">Add remarks</button>" in rachel
    assert ">Approve</button>" not in rachel
    sam = c.get(STAFF + "decide/L-0105" + SAM).text  # the Master
    assert "Your remarks for the Master" not in sam
    assert "Decide without the cover's confirmation" in sam  # Elise Tan has not confirmed
    assert (
        "<dt>From entitlement</dt><dd>0 days of Personal leave</dd><dt>Extra leave</dt><dd>4 days"
        in sam
    )
    assert "<dt>Blackout</dt><dd>Examinations, 15 Nov – 28 Nov: appeal only</dd>" in sam
    refused = _by_id("L-0120")
    assert refused.appeal and refused.stage == "Rejected"
    assert refused.days == 7 and sample_leave.timeline(refused)[-1] == (
        "11 Sep",
        "Rejected by Sam Lee",
        "The Precinct is short that week; take your five days, or apply in a quieter week.",
    )
    assert (
        c.get(STAFF + "decide/L-0105" + "?as=Daniel%20Koh").status_code == 404
    )  # outside his scope
    assert (
        "From entitlement" not in c.get(STAFF + "decide/L-0120" + SAM).text
    )  # refused: nothing to split


def test_an_appeal_charges_the_ra_s_own_days_first(monkeypatch) -> None:
    """Spec §7.5: an appeal's days are charged to the RA's own entitlement
    as far as it goes; only the rest is extra leave, and the balance, the
    extra-leave totals and Decide agree (audit, 2026-10-29)."""
    row = next(
        r
        for r in sample_leave.entitlement_rows()
        if r["ra"] == "Isaac Goh" and r["type"] == "Personal leave"
    )
    have = row["available"]
    assert have > 0
    start = sample_leave.date(2026, 12, 1)
    appeal = sample_leave.Application(
        "L-0199",
        "Isaac Goh",
        "Personal leave",
        start,
        sample_leave.date.fromordinal(start.toordinal() + have + 1),
        "Kai Ng",
        "Awaiting",
        "Appeal to the Master",
        sample_leave.TODAY,
    )
    monkeypatch.setattr(sample_leave, "APPLICATIONS", sample_leave.APPLICATIONS + (appeal,))
    assert sample_leave.appeal_split(appeal) == {"charged": have, "extra": 2}
    after = next(
        r
        for r in sample_leave.entitlement_rows()
        if r["ra"] == "Isaac Goh" and r["type"] == "Personal leave"
    )
    assert (
        after["available"] == 0 and after["pending"] == row["pending"] + have
    )  # its own days, pending
    assert sample_leave.my_extra("Isaac Goh")["pending"] == 2  # only the rest is extra


def test_staff_home_shows_this_week_and_admin_detail_the_balance() -> None:
    """Author, 2026-11-09: This week is who is away today; Later this week
    approved leave starting from tomorrow to the week's end. The admin
    application page shows the RA's balance for correcting the record
    (§21.4, scenario M)."""
    c = client()
    home = c.get(STAFF + SAM).text
    today = home.split('id="week-h">This week</h2>')[1].split("</section>")[0]
    assert ["Maya Seah", "Olivia Ng"] == re.findall(r'<span class="strong">([^<]+)</span>', today)
    later = home.split('id="later-h">Later this week</h2>')[1].split("</section>")[0]
    assert re.findall(r'<span class="strong">([^<]+)</span>', later) == ["Pranav Iyer"]
    assert [a.id for a in sample_leave.later_this_week("Sam Lee")] == ["L-0108"]
    admin = c.get("/ra-leave/admin/applications/L-0101").text
    card = admin.split('id="bal-h">')[1].split("</section>")[0]
    assert card.startswith("Chloe Lim's Personal leave, ")
    assert re.findall(r"<dt>(\w+)</dt><dd>(\d+)</dd>", card) == [
        ("Entitlement", "5"),
        ("Used", "0"),
        ("Pending", "3"),
        ("Available", "2"),
    ]


def test_staff_home_says_when_no_one_is_away_this_week() -> None:
    home = client().get(STAFF).text  # Daniel Koh's Precinct
    assert "No one is away today." in home and "No one starts leave later this week." in home


def test_staff_home_shows_a_month_of_leave_in_a_calendar() -> None:
    """Author, 2026-11-09: under the cards, a calendar of the month with the
    approved and pending leave of RAs in the viewer's scope, blackout weeks
    marked, and the previous and next month a link away; a phone keeps the
    month, each entry a first name in a tag (author, 2026-11-10)."""
    october = sample_leave.month_of(None)
    assert october == sample_leave.date(2026, 10, 1)
    weeks = sample_leave.leave_calendar("Sam Lee", october)
    assert all(len(w) == 7 for w in weeks) and weeks[0][0]["day"].isoweekday() == 7  # a Sunday
    today = next(c for w in weeks for c in w if c["today"])
    assert today["day"] == sample_leave.TODAY
    assert {a.ra for a, approved in today["leave"] if approved} == {"Maya Seah", "Olivia Ng"}
    # Pending leave is marked, not approved; an RA out of scope is not shown.
    nov = sample_leave.leave_calendar("Sam Lee", sample_leave.date(2026, 11, 1))
    sixth = next(c for w in nov for c in w if c["day"] == sample_leave.date(2026, 11, 6))
    assert ("Chloe Lim", False) in {(a.ra, ok) for a, ok in sixth["leave"]}
    daniel = sample_leave.leave_calendar("Daniel Koh", october)
    assert not any(a.ra == "Maya Seah" for w in daniel for c in w for a, _ in c["leave"])
    # An appeal awaiting the Master is left off (author, 2026-11-09): Gwen
    # Ho's L-0105, 20 Nov – 23 Nov.
    assert not any(a.id == "L-0105" for w in nov for c in w for a, _ in c["leave"])
    exams = next(c for w in nov for c in w if c["day"] == sample_leave.date(2026, 11, 16))
    assert exams["blackout"] == "Examinations"
    assert sample_leave.month_of("2026-13") == october and sample_leave.month_of("x") == october
    assert sample_leave.shift_month(sample_leave.date(2026, 12, 1), 1) == sample_leave.date(
        2027, 1, 1
    )

    c = client()
    page = c.get(STAFF + SAM).text.split('id="cal-h"')[1]
    assert "<strong>October 2026</strong>" in page
    assert 'href="/ra-leave/staff/?as=Sam%20Lee&amp;month=2026-11#cal-h"' in page
    assert (
        'class="cal-leave cal-link approved" href="/ra-leave/staff/decide/L-0106?as=Sam%20Lee"'
        in page
    )
    # A phone keeps the month (author, 2026-11-10): each entry also a first
    # name in a tag, the full name and status for a screen reader.
    assert 'class="items cal-list"' not in page
    assert (
        '<span class="cal-leave cal-tag approved"' in page
        and '>Maya<span class="visually-hidden"> Seah</span></span>' in page
    )
    november = c.get(STAFF + "?month=2026-11").text.split('id="cal-h"')[1]
    assert "<strong>November 2026</strong>" in november
    assert 'class="cal-leave cal-link pending" href="/ra-leave/staff/decide/L-0101"' in november
    assert '>Chloe<span class="visually-hidden"> Lim, pending</span></span>' in november
    assert '<span class="cal-black">Examinations</span>' in november  # named, not hatched alone
    assert ">Chloe Lim (pending)</a>" in november  # pending in words, not color alone
    assert "Blackouts: Examinations, 15 Nov – 28 Nov." in november
    assert "No leave this month." in c.get(STAFF + "?month=2027-03").text
    assert 'aria-current="date"' in page  # today, for a screen reader too
    # The cold read: the calendar's far ends are never reached, and every
    # academic year's blackouts show.
    for far in ("0001-01", "9999-12", "2026-13", "x"):
        assert c.get(STAFF + f"?month={far}").status_code == 200, far
    last_year = sample_leave.leave_calendar("Sam Lee", sample_leave.date(2025, 11, 1))
    assert any(d["blackout"] == "Examinations" for w in last_year for d in w)
    assert sample_leave.shift_month(sample_leave.date(2027, 1, 1), -1) == sample_leave.date(
        2026, 12, 1
    )
    # An application across two months shows in both (L-0103, 30 Oct – 1 Nov).
    rachel = [
        {
            a.id
            for w in sample_leave.leave_calendar("Rachel Yeo", sample_leave.date(2026, m, 1))
            for d in w
            if d["in_month"]
            for a, _ in d["leave"]
        }
        for m in (10, 11)
    ]
    assert "L-0103" in rachel[0] and "L-0103" in rachel[1]
    # The month links keep the cover filter.
    assert "?cover=waiting&amp;month=2026-11" in c.get(STAFF + "?cover=waiting").text


def test_the_precinct_page_counts_in_its_cards_and_lists_by_precinct_last() -> None:
    """Author, 2026-11-09: no count tiles; Away, Upcoming and pending, and
    Clashes carry their counts; By Precinct comes last; the period's dates
    sit under the select beside Show period."""
    page = client().get(STAFF + "precinct" + SAM).text
    assert 'class="tile' not in page
    order = [page.index(f'id="{h}"') for h in ("away-h", "upcoming-h", "clash-h", "team-h")]
    assert order == sorted(order)
    assert 'Upcoming and pending <span class="count">· 9</span>' in page
    rows = page.split('id="upcoming-h"')[1].split("</table>")[0].count("<tr><td")
    assert rows == 9  # the count is the table's rows
    assert 'Away, this week <span class="count">· 3</span>' in page
    assert 'Clashes <span class="count">· 1</span>' in page
    assert ">Precinct</a>" in client().get(STAFF + "?as=Priya%20Raman").text  # an RSLM
    assert (
        '<div class="period-row"><span id="period-dates"' in page
        and "Show period</button></div>" in page
    )


def test_the_leave_calendar_filters_by_status_and_for_the_unit_by_wing() -> None:
    """Author, 2026-11-10: on/off chips over the calendar, Approved and
    Pending for a viewer with one Precinct (or one Wing), and a chip a Wing
    besides for one who sees the whole Unit."""
    assert sample_leave.calendar_wings("Daniel Koh") == ()
    assert sample_leave.calendar_wings("Priya Raman") == ()  # one Wing
    assert sample_leave.calendar_wings("Sam Lee") == ("Cypress", "Maple", "Willow")
    assert sample_leave.calendar_wings("Rachel Yeo") == ("Cypress", "Maple", "Willow")
    # Only the viewer's own chips are read from `?hide=`.
    assert sample_leave.calendar_hidden("Daniel Koh", "Pending,Maple,x") == {"Pending"}
    assert sample_leave.calendar_hidden("Sam Lee", "Pending,Maple,x") == {"Pending", "Maple"}
    nov = sample_leave.date(2026, 11, 1)

    def names(viewer: str, hidden: frozenset[str] = frozenset()) -> set[tuple[str, bool]]:
        weeks = sample_leave.leave_calendar(viewer, nov, hidden)
        return {(a.ra, ok) for w in weeks for c in w for a, ok in c["leave"]}

    every = names("Sam Lee")
    assert ("Chloe Lim", False) in every
    assert all(ok for _, ok in names("Sam Lee", frozenset({"Pending"})))
    assert not any(ok for _, ok in names("Sam Lee", frozenset({"Approved"})))
    no_cypress = sample_leave.leave_calendar("Sam Lee", nov, frozenset({"Cypress"}))
    wing_of = {s.precinct: s.wing for s in sample_data.SLOTS}
    assert all(
        wing_of[a.precinct] != "Cypress" for w in no_cypress for c in w for a, _ in c["leave"]
    )
    assert ("Chloe Lim", False) not in names("Sam Lee", frozenset({"Cypress"}))

    c = client()
    page = c.get(STAFF + "?month=2026-11").text.split('id="cal-h"')[1]  # Daniel, an RF
    chips = page.split('class="col-chips cal-filters"')[1].split("</div>")[0]
    assert chips.count('class="col-chip on"') == 2 and "Cypress" not in chips
    # Each chip's link turns itself off and keeps the month.
    assert 'href="/ra-leave/staff/?hide=Pending&amp;month=2026-11#cal-h"' in chips
    off = c.get(STAFF + "?month=2026-11&hide=Pending").text.split('id="cal-h"')[1]
    assert ">Chloe<" not in off and 'class="col-chip" data-filter' in off
    # ...and the month links carry the filter.
    assert "hide=Pending&amp;month=2026-12#cal-h" in off
    # Turning it back on clears `hide`.
    assert 'href="/ra-leave/staff/?month=2026-11#cal-h"' in off

    sam = c.get(STAFF + SAM + "&month=2026-11").text.split('id="cal-h"')[1]
    sam_chips = sam.split('class="col-chips cal-filters"')[1].split("</div>")[0]
    for wing in ("Cypress", "Maple", "Willow"):
        assert f"{wing}<span" in sam_chips
    assert "hide=Maple&amp;month=2026-11" in sam_chips
    hidden_all = c.get(STAFF + SAM + "&month=2026-11&hide=Approved,Pending").text
    assert "No leave this month with these filters." in hidden_all
    # The cold read: two filters off write one form of `hide`, a month with
    # no leave says so whatever is off, and the cover filter keeps them.
    two = c.get(STAFF + SAM + "&month=2026-11&hide=Pending,Maple").text
    assert two.count("hide=Maple%2CPending&amp;month=2026-12#cal-h") == 1
    assert "hide=Maple%2CPending%2CWillow&amp;month=2026-11#cal-h" in two
    empty = c.get(STAFF + SAM + "&month=2027-03&hide=Pending").text
    assert "No leave this month." in empty and "with these filters" not in empty
    cover = (
        'href="/ra-leave/staff/?as=Sam%20Lee&amp;cover=waiting&amp;hide=Pending&amp;month=2026-11"'
    )
    assert cover in c.get(STAFF + SAM + "&month=2026-11&hide=Pending").text
    back = c.get(STAFF + SAM + "&cover=waiting&month=2026-11&hide=Pending").text
    assert (
        'href="/ra-leave/staff/?as=Sam%20Lee&amp;hide=Pending&amp;month=2026-11">Show everything'
        in back
    )


def test_a_senior_cancels_leave_under_way_and_the_admin_s_page_says_who_is_told() -> None:
    """Author, 2026-11-10: a senior or the Residential Admin cancels leave
    under way, the RA and their RF told; an RF approves an RA's request
    instead, so has no cancel of their own."""
    begun = sample_leave.by_id("L-0107")  # Olivia Ng, 28 Oct – 30 Oct
    later = sample_leave.by_id("L-0115")  # Hana Ito, 14 Dec
    assert begun and later
    assert sample_leave.under_way(begun) and not sample_leave.under_way(later)
    assert sample_leave.cancel_request_to(begun) == "Siti Rahman"
    assert sample_leave.cancels_under_way("Sam Lee", begun)
    assert not sample_leave.cancels_under_way("Sam Lee", later)
    assert not sample_leave.cancels_under_way("Siti Rahman", begun)  # her RF
    assert not sample_leave.cancels_under_way("Priya Raman", begun)  # Cypress, not Willow
    c = client()
    sam = c.get(STAFF + "decide/L-0107" + SAM).text
    assert "Olivia Ng and Siti Rahman, their RF, are told." in sam
    assert ">Cancel leave under way</button>" in sam
    assert ">Cancel leave under way</button>" not in c.get(STAFF + "decide/L-0115" + SAM).text
    admin = c.get("/ra-leave/admin/applications/L-0107").text
    assert "This leave is under way" in admin and "Siti Rahman, their RF," in admin
