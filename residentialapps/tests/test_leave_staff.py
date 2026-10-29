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
    assert ids(c.get(STAFF + "decided" + SAM).text, "dec-h") == ["L-0120", "L-0118"]  # the appeals the Master refused and granted


def test_whatever_a_viewer_may_decide_opens(monkeypatch) -> None:
    """Every row in a viewer's queue or Decided list opens Decide, under
    each approval setting, a delegate's and a named approver's included."""
    import itertools

    c = client()
    people = ("Daniel Koh", "Rachel Yeo", "Sam Lee", "Benjamin Chua", "Grace Ho", "Marcus Tan", "Mei Ling Tan", "Priya Raman")
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
    assert sample_leave.can_open("Marcus Tan", sample_leave.by_id("L-0103"))  # standing in for Grace Ho


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
    assert '/ra-leave/staff/appeals' in c.get(STAFF + RACHEL).text.split('class="tabs-in"')[1].split("</nav>")[0]
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ())
    assert sample_leave.inviter_label() == "" and sample_leave.all_inviters() == ()
    assert "Leave policy names no one to open appeals." in c.get(STAFF + "appeals" + SAM).text
    assert "Leave policy names no one to open appeals." in c.get("/ra-leave/admin/appeals").text  # as the staff page
    assert 'id="inv-ra"' not in c.get("/ra-leave/admin/appeals").text
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
    # Named, he still opens appeals only for RAs in his slots (ruled 2026-10-29).
    assert "Gwen Ho" not in page and sample_leave.invitable_ras("Daniel Koh") == ("Chloe Lim", "Ethan Wong", "Hana Ito")
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
    # Untick the admin: Rachel Yeo holds no slot, so she sees no RA and
    # her final approval leaves every Precinct with a gap (ruled 2026-10-29).
    monkeypatch.setitem(sample_leave.sample_data.EVERY_SLOT, sample_leave.TERM.key, {"appointments": ("Master",), "names": ()})
    assert sample_leave.overseers() == ("Sam Lee",) and sample_leave.scope("Rachel Yeo") == ()
    assert sample_leave.final_gaps() == sample_leave.precincts()
    # Tick the Executive: Hui Min Goh oversees every RA, deciding nothing.
    monkeypatch.setitem(sample_leave.sample_data.EVERY_SLOT, sample_leave.TERM.key, {"appointments": ("Master", "Admin", "Exec"), "names": ()})
    assert len(sample_leave.scope("Hui Min Goh")) == 9
    assert "Nothing awaits you." in c.get(STAFF + "decide?as=Hui%20Min%20Goh").text


def test_oversight_follows_the_policy_setting(monkeypatch) -> None:
    """Ruled 2026-10-29: staff approve, first or final, decide or open
    appeals only for RAs in whose slots they hold a place; the overseers
    hold one in every slot. A role given elsewhere is a gap, never a view."""
    c = client()
    monkeypatch.setitem(sample_leave.sample_data.EVERY_SLOT, sample_leave.TERM.key, {"appointments": (), "names": ()})
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    assert sample_leave.scope("Rachel Yeo") == () and sample_leave.all_inviters() == ()
    assert "the fix is in Assignments" in c.get(STAFF + RACHEL).text
    assert all(not sample_leave.decides_appeals(p) for p in sample_leave.precincts())
    routing = c.get("/ra-leave/admin/routing").text
    assert routing.count("none named holds a place in its slots") == len(sample_leave.precincts())
    # A named final approver approves only in their own slots.
    monkeypatch.setitem(sample_leave.sample_data.EVERY_SLOT, sample_leave.TERM.key, {"appointments": ("Master", "Admin"), "names": ()})
    monkeypatch.setitem(sample_leave.POLICY, "final", "named")
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ("Daniel Koh",))
    assert sample_leave.final_for("Cypress A 04-12") == ("Daniel Koh",) and sample_leave.final_for("Maple 03-08") == ()
    assert len(sample_leave.final_gaps()) == len(sample_leave.precincts()) - 1
    # A delegate outside the slots they would stand in for does not stand in.
    D = sample_leave.Delegate
    monkeypatch.setattr(sample_leave, "DELEGATES", (D("Grace Ho", "Benjamin Chua", None, None, "has not signed in yet"),))
    maple = next(r for r in sample_leave.routes() if r.precinct == "Maple 03-08")
    assert maple.first == "Grace Ho" and "Benjamin Chua is not in these slots" in maple.note
    assert "Not in their slots" in c.get("/ra-leave/admin/routing").text
    monkeypatch.setitem(sample_leave.POLICY, "final", "unit")
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    # Under Open, a non-inviter's Appeals page says no one opens appeals.
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Open")
    assert "every RA may send one, so none is opened for them" in c.get(STAFF + "appeals").text
    # An appeal opened from Appeals goes back there, inviter or not.
    monkeypatch.setitem(sample_leave.sample_data.EVERY_SLOT, sample_leave.TERM.key, {"appointments": ("Master", "Admin", "Exec"), "names": ()})
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
    assert "Olivia Ng and Pranav Iyer" in week and "Olivia Ng and Pranav Iyer" not in nxt  # clashes follow
    _, _, start, end = sample_leave.period("next")
    assert sample_leave.clashes(start, end) == () and sample_leave.clashes()  # none next week, some in all
    # The Precinct counts follow the period too, counting RAs.
    def counts(key: str) -> dict[str, int]:
        _, _, start, end = sample_leave.period(key)
        return {r["precinct"]: r["away"] for r in sample_leave.by_precinct("Sam Lee", start, end)}
    assert sum(counts("week").values()) == 3 and sum(counts("next").values()) == 0
    assert sum(counts("term").values()) == 4
    four = sample_leave.period("four")
    assert (four[1], four[2], four[3].toordinal() - four[2].toordinal()) == ("These four weeks", sample_leave.TODAY, 27)
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
    lucas = sample_leave.by_id("L-0118")
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
    assert "<dt>From entitlement</dt><dd>0 days of Personal leave</dd><dt>Extra leave</dt><dd>4 days" in sam
    assert "<dt>Blackout</dt><dd>Examinations, 15 Nov – 28 Nov: appeal only</dd>" in sam
    refused = sample_leave.by_id("L-0120")
    assert refused.appeal and refused.stage == "Rejected"
    assert ("18 Sep", "Rejected by Sam Lee", "The Precinct is short that week; apply within next term's days.") in sample_leave.timeline(refused)
    assert "From entitlement" not in c.get(STAFF + "decide/L-0120" + SAM).text  # refused: nothing to split
