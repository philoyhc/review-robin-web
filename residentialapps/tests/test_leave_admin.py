"""RA Leave's sys admin pages (`/ra-leave/admin/`), segment 1C item 1:
placeholders on `sample_leave`, built first since the rest of RA Leave is
downstream of their configuration (author, 2026-10-28)."""

from __future__ import annotations

import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.main import create_app as ops_app
from residentialapps.residentialops.pages import LEAVE_ADMIN_TABS

ADMIN = "/ra-leave/admin/"
STAFF_ADMIN_APPEALS = "/ra-leave/staff/appeals?as=Rachel%20Yeo"  # the admin Appeals, retired


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


def _weeks(blackout: sample_leave.Blackout) -> tuple[date, date]:
    """A sample blackout's dates, which fall in the sample's term."""
    found = sample_leave.week_dates(blackout)
    assert found is not None, blackout
    return found


def client() -> TestClient:
    return TestClient(ops_app())


def test_every_admin_page_answers_with_its_tab_current() -> None:
    c = client()
    for tab in LEAVE_ADMIN_TABS:
        page = c.get(tab["path"])
        assert page.status_code == 200, tab
        assert "Sample data" in page.text
        assert f'href="{tab["path"]}" aria-current="page"' in page.text, tab
    home = c.get("/rosters/").text
    assert 'href="/ra-leave/admin/"' in home  # RA Leave is live in the switcher


def test_the_dashboard_counts_pending_by_stage_and_flags_what_needs_attention() -> None:
    """Cover is tracked beside the workflow, never a stage (spec §11): an
    unconfirmed cover waits at first approval and has its own tile."""
    page = client().get(ADMIN).text
    assert "Awaiting cover" not in page and "Awaiting cover" not in sample_leave.STAGES
    tiles = re.findall(
        r'href="([^"]*)">\s*<span class="tile-n">(\d+)</span>\s*<span class="tile-l">([^<]*)', page
    )
    assert [(n, label) for _, n, label in tiles] == [
        ("5", "Pending first approval"),
        ("1", "Pending final approval"),
        ("1", "Appeal to the Master"),
        ("4", "Cover not yet confirmed"),
    ]
    # Each tile opens Leave records over the whole term with only its rows
    # left on (author, 2026-11-10: Applications became Leave records).
    assert tiles[0][0].startswith("/ra-leave/admin/records?hide=") and tiles[0][0].endswith(
        "&amp;period=whole"
    )
    assert "Pending%20first%20approval" not in tiles[0][0]
    assert tiles[3][0] == "/ra-leave/admin/records?cover=unconfirmed&amp;period=whole"
    attention = page.split('id="attention-h"')[1].split("</section>")[0]
    assert re.findall(r">(L-\d+)</a>", attention) == ["L-0103", "L-0104", "L-0107", "L-0109"]
    assert "Pranav Iyer is away too" in attention and "Chloe Lim declined cover" in attention
    assert attention.count("Away on the same days in one Precinct") == 1
    assert '<td class="strong">Olivia Ng, Pranav Iyer</td>' in attention
    away = page.split('id="away-h"')[1].split("</section>")[0]
    assert re.findall(r'<td class="strong nowrap">([^<]*)', away) == [
        "Maya Seah",
        "Olivia Ng",
        "Pranav Iyer",
    ]
    assert "Maple 03-08</strong>: Grace Ho has not signed in yet" in page


def test_a_tile_opens_the_rows_it_counts() -> None:
    c = client()
    page = c.get(ADMIN).text
    links = re.findall(r'<a class="tile" href="([^"]*)"', page)
    first = c.get(links[0].replace("&amp;", "&")).text
    assert sorted(re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', first)) == [
        "L-0101",
        "L-0102",
        "L-0104",
        "L-0109",
        "L-0114",
    ]
    cover = c.get(links[-1].replace("&amp;", "&")).text
    assert sorted(re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', cover)) == [
        "L-0102",
        "L-0105",
        "L-0109",
        "L-0114",
    ]  # L-0105: the appeal's cover awaits (audit, 2026-10-29)
    assert 'Leave applications <span class="count">· 4</span>' in cover
    # The tile's count and its rows are one set: open stages, cover still
    # to confirm (the cold read).
    assert len(re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', cover)) == len(
        sample_leave.cover_unconfirmed()
    )
    # An old Applications link lands on Leave records, its query kept.
    # An old filtered Applications link keeps its filter (Codex).
    old = c.get(ADMIN + "applications?stage=x", follow_redirects=False)
    assert old.status_code == 303
    assert old.headers["location"] == "/ra-leave/admin/records?period=whole"
    staged = c.get(ADMIN + "applications?stage=Pending%20first%20approval").text
    assert sorted(re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', staged)) == sorted(
        re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', first)
    )
    unconfirmed = c.get(ADMIN + "applications?cover=unconfirmed").text
    assert 'Leave applications <span class="count">· 4</span>' in unconfirmed
    old = c.get(ADMIN + "applications/L-0101", follow_redirects=False)
    assert old.headers["location"] == "/ra-leave/admin/records/L-0101"
    back = c.get(ADMIN + "records/L-0101").text
    assert '<a class="back" href="/ra-leave/admin/records?period=whole">‹ Records</a>' in back
    # Its tab reads Records, as the staff's (author, 2026-11-10).
    tabs = c.get(ADMIN).text.split('class="tabs-in"')[1].split("</nav>")[0]
    assert '/ra-leave/admin/records">Records</a>' in tabs and "Leave records" not in tabs


def test_policy_sets_leave_types_with_their_own_entitlement_rules() -> None:
    """Points 1–2 (author, 2026-10-28): leave that needs an application,
    each type earned per term or per month served, with a cap per year or
    term."""
    page = client().get(ADMIN + "policy").text
    assert [lt.name for lt in sample_leave.LEAVE_TYPES] == ["Personal leave", "Official leave"]
    for n, lt in enumerate(sample_leave.LEAVE_TYPES, start=1):
        assert f'aria-label="Leave type {n}: name" value="{lt.name}"' in page
        earned = page.split(f'aria-label="Leave type {n}: how it is earned"')[1].split("</select>")[
            0
        ]
        assert re.findall(r"<option( selected)?>([^<]*)", earned) == [
            (" selected" if a == lt.accrual else "", a) for a in sample_leave.ACCRUALS
        ]
        assert f'aria-label="Leave type {n}: abbreviation" value="{lt.abbrev}"' in page
        assert f'aria-label="Leave type {n}: days earned" value="{lt.amount}"' in page
        assert f'aria-label="Leave type {n}: cap in days" value="{lt.cap}"' in page
        per = page.split(f'aria-label="Leave type {n}: cap per"')[1].split("</select>")[0]
        assert re.findall(r"<option selected>([^<]*)", per) == [lt.cap_per]
    assert "medical, compassionate" in page


def test_policy_blackouts_count_by_week_and_refuse_or_send_to_appeal() -> None:
    """Point 3: blackouts by week of a term, Sunday to Saturday, clipped to
    the term, so they carry across years; each either refuses leave or
    sends it to appeal."""
    page = client().get(ADMIN + "policy").text
    dates = [_weeks(b) for b in sample_leave.BLACKOUTS]
    assert [(d.isoformat(), e.isoformat()) for d, e in dates] == [
        ("2026-08-03", "2026-08-15"),
        ("2026-11-15", "2026-11-28"),
        ("2027-01-11", "2027-01-16"),
    ]  # week 1's Sundays (2 Aug, 10 Jan) fall in the previous term, so are clipped
    terms = {t.number: t for t in sample_data.TERMS if t.year == "AY2026-2027"}
    assert all(
        terms[b.term].start <= d <= e <= terms[b.term].end
        for b, (d, e) in zip(sample_leave.BLACKOUTS, dates)
    )
    B = sample_leave.Blackout
    assert sample_leave.week_dates(B(1, 30, 31, "Past the term", "Refused")) is None
    assert sample_leave.week_dates(B(1, 3, 2, "Backwards", "Refused")) is None
    last_week = sample_leave.week_dates(B(1, 23, 24, "Last week", "Refused"))
    assert last_week is not None
    assert last_week[1].isoformat() == "2027-01-10"  # a Sunday: clipped
    # Each blackout's dates sit under its What (author, 2026-11-10).
    rendered = re.findall(r'value="[^"]*" disabled><div class="subtle small">([^<]*)</div>', page)
    assert rendered == ["3 Aug – 15 Aug", "15 Nov – 28 Nov", "11 Jan – 16 Jan"]
    terms = page.split('aria-label="Blackout 1: term"')[1].split("</select>")[0]
    assert re.findall(r"<option[^>]*>([^<]*)", terms) == ["Term 1", "Term 2", "Term 3"]
    effects = re.findall(
        (
            r'aria-label="Blackout \d: leave is" disabled><option( selected)?>Refused</option>'
            r"<option( selected)?>Appeal only"
        ),
        page,
    )
    assert [("Refused" if r else "Appeal only") for r, _ in effects] == [
        b.effect for b in sample_leave.BLACKOUTS
    ]


def test_policy_appeals_cover_and_approvals() -> None:
    """Points 4–6: appeals beyond entitlement on stated terms, never banked
    in advance; cover required or not, named or confirmed, from a pool;
    first and final approval."""
    page = client().get(ADMIN + "policy").text
    for name, options, current in (
        (
            "cover",
            ("Required", "Not required"),
            "Required" if sample_leave.POLICY["cover_required"] else "Not required",
        ),
        ("cover-mode", sample_leave.COVER_MODES, sample_leave.POLICY["cover_mode"]),
        ("pool", sample_leave.COVER_POOLS, sample_leave.POLICY["cover_pool"]),
    ):
        radios = re.findall(
            rf'<input type="radio" id="{name}-\d" name="{name}" value="([^"]*)"( checked)?', page
        )
        assert [v for v, _ in radios] == list(options), name
        assert [v for v, c in radios if c] == [current], name
    on_off = re.findall(
        r'<input type="radio" id="appeals-\d" name="appeals" value="([^"]*)"( checked)?', page
    )
    assert on_off == [
        (m, " checked" if m == sample_leave.POLICY["appeals"] else "")
        for m in sample_leave.APPEAL_MODES
    ]
    assert "refused while appeals are off" in page  # system-wide switch (author, 2026-10-28)
    assert sample_leave.POLICY["appeal_terms"] in page
    # Cover and appeal wording (author, 2026-11-10): the override sentence,
    # the banking note and the Master-decides line go; appeals ask the college.
    assert "no built-in default" in page and "unless the Master overrides it" not in page
    assert "cannot be done in advance and banked" not in page
    assert "may ask the college for extra leave" in page and "spec §7.5" not in page
    assert "Whether an application or appeal must name a covering RA" in page
    assert "Cover for leave is" in page and "ordinary leave is" not in page
    # Cover sits left of Appeals; the Approvals card is gone; one
    # Leave days card holds counting, public holidays and blackouts.
    assert page.index('aria-labelledby="cover-h"') < page.index('aria-labelledby="appeals-h"')
    assert 'id="approvals-h"' not in page and 'id="perms-h"' in page
    days = page.split('aria-labelledby="days-h"')[1].split('aria-labelledby="cover-h"')[0]
    assert 'id="holidays-h"' in days and 'id="blackout-h"' in days and 'name="day-count"' in days
    assert 'aria-labelledby="count-h"' not in page
    # Who approves is Permissions' to say; the Approvals card that summed
    # it up is gone (author, 2026-11-10), and the Dashboard names who
    # decides appeals.
    assert 'aria-label="Final approval, Residential Admin" checked' in page
    assert "The Master (Sam Lee), personally" in client().get(ADMIN).text


def test_entitlements_follow_the_policy_rules() -> None:
    page = client().get(ADMIN + "entitlements").text
    rows = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    assert len(rows) == len(sample_data.RAS) * len(sample_leave.LEAVE_TYPES)
    pick = ("entitlement", "adjustment", "used", "pending", "available")
    # Personal leave: 5 for Term 1, available only within it.
    assert [rows["Gwen Ho", "Personal leave"][k] for k in pick] == [
        5,
        0,
        5,
        0,
        0,
    ]  # used up: hence her appeal
    assert [rows["Leon Chia", "Personal leave"][k] for k in pick] == [5, 2, 0, 5, 2]
    assert [rows["Chloe Lim", "Personal leave"][k] for k in pick] == [5, 0, 0, 3, 2]
    # Official leave: 1 a month served in the term; two whole months since
    # its 3 Aug start, and since Umairah Salleh's 17 Aug.
    assert [rows["Hana Ito", "Official leave"][k] for k in pick] == [2, 0, 0, 2, 0]
    assert rows["Umairah Salleh", "Official leave"]["entitlement"] == 2
    assert sample_leave.months_served(sample_leave.date(2026, 9, 1)) == 1
    assert (
        rows["Gwen Ho", "Personal leave"]["pending"] == 0
    )  # her appeal is extra leave, not charged (§7.5)
    assert (
        '+2<div class="subtle">Correction: days charged twice' in page
    )  # the reason, visible; never extra leave (§7.5, §21.3)
    assert "Email,Leave type,Adjustment,Reason" in page
    assert (
        f"<option selected>{sample_leave.TERM.label}</option>" in page
        and "do not carry over" in page
    )
    assert page.count(">Adjust</button>") == len(rows)


def test_the_approval_chain_is_derived_from_assignments_and_the_policy() -> None:
    page = client().get(ADMIN + "routing").text
    routes = sample_leave.routes()
    assert [r.precinct for r in routes] == list(
        dict.fromkeys(s.precinct for s in sample_data.SLOTS)
    )
    assert sum(r.ras for r in routes) == len(sample_data.SLOTS)
    for r in routes:
        assert r.first == ("Marcus Tan" if r.rf == "Grace Ho" else r.rf)
    assert page.count(">Delegate</span>") == 1 and "Grace Ho has not signed in yet" in page


def test_a_delegate_stands_in_for_a_person_between_dates() -> None:
    """Ruled 2026-10-28: a delegate acts for one person on all their slots,
    with optional dates; first approval only."""
    grace, daniel = sample_leave.DELEGATES
    assert grace.active() and grace.dates == "Until removed"
    assert (
        not daniel.active()
        and daniel.active(sample_leave.date(2026, 12, 7))
        and not daniel.active(sample_leave.date(2026, 12, 19))
    )
    assert daniel.dates == "7 Dec – 18 Dec"
    cypress = next(r for r in sample_leave.routes() if r.rf == "Daniel Koh")
    assert cypress.first == "Daniel Koh" and not cypress.delegate  # not yet
    page = client().get(ADMIN + "routing").text
    card = page.split('id="delegates-h"')[1].split("</section>")[0]
    assert (
        '<span class="chip chip-warn">Standing in</span>' in card
        and '<span class="chip chip-mute">7 Dec – 18 Dec</span>' in card
    )
    acting_for = card.split('aria-label="Delegate 1: acting for"')[1].split("</select>")[0]
    assert (
        "<option selected>Grace Ho</option>" in acting_for
        and "Sam Lee" not in acting_for
        and "Rachel Yeo" not in acting_for
    )
    assert (
        'aria-label="Delegate 2: from" value="2026-12-07"' in card
        and 'aria-label="Delegate 1: from" value=""' in card
    )
    assert "final approval and appeals are not delegable" in card
    assert "Set a delegate for" not in page  # by person now, not by Precinct
    assert "for AY2026-2027, Term 1 and the policy's first and final approvers (RF, Admin)" in page


def test_applications_list_every_one_and_open_to_their_timeline() -> None:
    c = client()
    page = c.get(ADMIN + "records?period=whole").text
    for a in sample_leave.APPLICATIONS:
        assert f'href="/ra-leave/admin/records/{a.id}">{a.id}</a>' in page
    detail = c.get(ADMIN + "records/L-0105").text
    assert "Gwen Ho" in detail and "family wedding" in detail
    assert "Sent to Sam Lee as an extra-leave appeal" in detail
    approved = c.get(ADMIN + "records/L-0106").text
    assert (
        "Final approval by Rachel Yeo" in approved and ">Cancel approved leave</button>" in approved
    )
    assert "Reassign" not in approved
    rejected = c.get(ADMIN + "records/L-0110").text
    assert (
        ">Correct the record</button>" in rejected
        and "Cancel" not in rejected
        and "Reassign" not in rejected
    )
    assert c.get(ADMIN + "records/L-9999").status_code == 404


def test_no_platform_only_date_format() -> None:
    """`%-d` and the like are glibc's: Windows' strftime raises on them, so
    the pages 500 on the author's machine while passing here."""
    from pathlib import Path

    package = Path(__file__).resolve().parents[1]
    for path in (*package.rglob("*.py"), *package.rglob("*.html")):
        if "tests" in path.parts:
            continue
        assert not re.search(r"strftime\([\"'][^\"']*%-", path.read_text(encoding="utf-8")), path
    assert sample_leave.short_date(sample_leave.TODAY) == "28 Oct"


def test_entitlement_rules_beyond_the_sample_types() -> None:
    """Leave days go with their term and are available only within it
    (author, 2026-10-28). A cap per term holds each term; a cap per year
    holds the terms together, earlier terms taking their share first.
    Months served count within the term, whole months only."""
    lt = sample_leave.LeaveType
    start = sample_leave.date(2026, 8, 1)
    terms = [t for t in sample_data.TERMS if t.year == sample_leave.PERIOD_LABEL]
    per_term = lt("X", "X", "Per term", 5, 4, "term")
    assert [sample_leave.entitlement(per_term, start, t) for t in terms] == [4, 4, 4]
    per_year = lt("X", "X", "Per term", 5, 12, "year")
    assert [sample_leave.entitlement(per_year, start, t) for t in terms] == [5, 5, 2]
    assert sample_leave.ACCRUALS == ("Per term", "Per month served")
    assert (
        sample_leave.months_served(sample_leave.date(2024, 8, 1)) == 2
    )  # a returning RA: this term only
    assert sample_leave.months_served(sample_leave.date(2026, 9, 29)) == 0  # TODAY is the 28th
    assert sample_leave.months_served(sample_leave.date(2026, 9, 28)) == 1
    assert sample_leave.months_served(start, terms[1]) == 0  # Term 2 has not begun
    monthly = lt("X", "X", "Per month served", 2, 6, "year")
    assert sample_leave.entitlement(monthly, start, terms[0]) == 4  # two months so far
    page = client().get(ADMIN + "policy").text
    assert "do not carry over" in page and "Per academic year" not in page


def test_used_and_pending_count_only_the_terms_own_days(monkeypatch) -> None:
    """Leave in another term never touches this term's figures; leave across
    a term's end is charged to each term for its own days."""
    before = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    App = sample_leave.Application
    extra = (
        App(
            "L-0901",
            "Chloe Lim",
            "Personal leave",
            sample_leave.date(2027, 2, 1),
            sample_leave.date(2027, 2, 3),
            "Ethan Wong",
            "Confirmed",
            "Approved",
            sample_leave.date(2026, 10, 20),
        ),
        App(
            "L-0902",
            "Leon Chia",
            "Personal leave",
            sample_leave.date(2027, 1, 8),
            sample_leave.date(2027, 1, 12),
            "Mira Sato",
            "Confirmed",
            "Pending first approval",
            sample_leave.date(2026, 10, 20),
        ),
    )
    monkeypatch.setattr(sample_leave, "APPLICATIONS", sample_leave.APPLICATIONS + extra)
    after = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    assert after["Chloe Lim", "Personal leave"] == before["Chloe Lim", "Personal leave"]
    assert (
        after["Leon Chia", "Personal leave"]["pending"]
        == before["Leon Chia", "Personal leave"]["pending"] + 3
    )  # 8–10 Jan
    assert (
        sample_leave.days_in_term(
            extra[1], [t for t in sample_data.TERMS if t.number == 2 and t.year == "AY2026-2027"][0]
        )
        == 2
    )


def test_appeals_switched_off_leave_no_appeal_route(monkeypatch) -> None:
    """Appeals beyond entitlement switch on or off for the whole system
    (author, 2026-10-28): off, no page offers or names an appeal route."""
    c = client()
    on = c.get(ADMIN).text.split('id="policy-h"')[1].split("</section>")[0]
    assert "<dt>Appeals</dt><dd>Open: The Master (Sam Lee), personally</dd>" in on
    assert ">Appeals final</th>" in c.get(ADMIN + "routing").text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    policy = c.get(ADMIN + "policy").text
    assert 'name="appeals" value="Off" checked' in policy
    assert (
        "Not available: an application beyond entitlement" in policy
        and "The Master (Sam Lee), personally" not in policy
    )
    assert "<dt>Appeals</dt><dd>Off</dd>" in c.get(ADMIN).text
    routing = c.get(ADMIN + "routing").text
    # L-0105, made before appeals were turned off, stands and is decided.
    assert (
        ">Appeals final</th>" in routing
        and "final approval and appeals are given only by those holding a place in the RA's slot"
        in routing
    )


def test_a_delegation_follows_its_person_and_the_policys_approver(monkeypatch) -> None:
    """A delegate stands in on every slot their person approves for, under
    whichever approver the policy names, and only on the delegation's days;
    the dashboard lists who stands in today."""
    D = sample_leave.Delegate
    in_dec = sample_leave.date(2026, 12, 10)
    cypress = next(r for r in sample_leave.routes(in_dec) if r.rf == "Daniel Koh")
    assert cypress.first == "Priya Raman" and cypress.note == "Daniel Koh is on leave"
    # The Master, in every slot, may stand in for an RSLM on all of theirs.
    monkeypatch.setattr(
        sample_leave, "DELEGATES", (D("Marcus Tan", "Sam Lee", None, None, "is on leave"),)
    )
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("RSLM",))
    maple = [r for r in sample_leave.routes() if r.wing == "Maple"]
    assert len(maple) == 3 and all(
        r.first == "Sam Lee" and r.delegate for r in maple
    )  # every slot Marcus approves
    assert all(not r.delegate for r in sample_leave.routes() if r.wing != "Maple")
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("RF", "RSLM"))
    assert (
        next(r for r in sample_leave.routes() if r.precinct == "Maple 03-08").first
        == "Grace Ho or Sam Lee"
    )
    page = client().get(ADMIN).text.split('id="gaps-h"')[1].split("</section>")[0]
    assert "A delegate stands in for 3 Precincts today." in page
    assert page.count("Marcus Tan is on leave; ") == 3


def test_approvals_choose_slot_and_unit_appointments_or_none_or_named(monkeypatch) -> None:
    """Ruled 2026-10-28: first approval by any of the appointments on the
    RAs' slots (several = whichever approves first), or none needed; final
    approval by any Unit-level appointment, or by named staff."""
    assert sample_leave.slot_appointments() == (
        ("Residential Fellow", "RF"),
        ("Residential Student Life Manager", "RSLM"),
    )
    assert sample_leave.unit_appointments() == (
        ("Master", "Master"),
        ("Residential Admin", "Admin"),
        ("Residential Executive", "Exec"),
    )
    page = client().get(ADMIN + "policy").text
    # The Approvals card is gone (author, 2026-11-10): no first-approval
    # radios; Permissions' First approval ticks say whether one is needed.
    assert 'name="first"' not in page and 'id="approvals-h"' not in page
    # Who approves, first or final, is Permissions' (author, 2026-11-10).
    ticks = dict(re.findall(r'aria-label="([^"]+)"( checked)? disabled>', page))
    assert ticks["First approval, Residential Fellow"] == " checked"
    assert ticks["First approval, Residential Student Life Manager"] == ""
    assert ticks["Final approval, Residential Admin"] == " checked"
    assert (
        ticks["Final approval, Master"] == ""
        and ticks["Final approval, Residential Executive"] == ""
    )
    assert 'list="staff-names"' in page and page.count('<option value="') >= len(sample_data.STAFF)

    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    monkeypatch.setitem(sample_leave.POLICY, "final", "named")
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ("Sam Lee", "Rachel Yeo"))
    assert {r.first for r in sample_leave.routes()} == {"None needed"}
    assert sample_leave.final_approvers() == ("Sam Lee", "Rachel Yeo")
    steps = [s for _, s, _ in sample_leave.timeline(_by_id("L-0106"))]
    assert (
        not any(s.startswith("First approval") for s in steps)
        and "Final approval by Sam Lee" in steps
    )
    named = client().get(ADMIN + "policy").text
    assert 'aria-label="Final approval, Sam Lee" checked' in named
    assert 'aria-label="Final approval, Rachel Yeo" checked' in named
    assert "<td>Sam Lee, Rachel Yeo</td>" in client().get(ADMIN + "routing").text
    dash = client().get(ADMIN).text
    assert (
        "No first approval, then Sam Lee or Rachel Yeo" in dash
        and "No first approval is needed" in dash
    )
    rejected = [s for _, s, _ in sample_leave.timeline(_by_id("L-0110"))]
    assert "Rejected by Sam Lee" in rejected
    assert client().get(ADMIN + "records/L-0106").status_code == 200
    routing = client().get(ADMIN + "routing").text.split('id="delegates-h"')[1]
    assert "Standing in" not in routing and routing.count(">No first approval</span>") == len(
        sample_leave.DELEGATES
    )


def test_approvals_edge_cases(monkeypatch) -> None:
    """Several Unit types: whichever approves first. No one named: the
    timeline still reads. A ticked type no slot holds: a flagged gap, not
    "None needed"."""
    monkeypatch.setitem(sample_leave.POLICY, "final_types", ("Master", "Admin"))
    assert sample_leave.final_approvers() == ("Sam Lee", "Rachel Yeo")
    assert "then the Master or Residential Admin (Admin)" in client().get(ADMIN).text
    monkeypatch.setitem(sample_leave.POLICY, "final", "named")
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ())
    assert "Final approval by the final approver" in [
        s for _, s, _ in sample_leave.timeline(_by_id("L-0106"))
    ]
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ())
    # No First approval tick: none is needed (author, 2026-11-10), no gap.
    routes = sample_leave.routes()
    assert sample_leave.POLICY["first"] == "none" and not any(r.gap for r in routes)
    # Only the final gap (no names set) remains on each row.
    assert client().get(ADMIN + "routing").text.count(">Gap</span>") == len(routes)


def test_the_sample_keeps_its_own_policy() -> None:
    """Every sample application could have been submitted under the sample's
    policy: cover from the pool, no Refused blackout, and an Appeal-only
    blackout only by appeal."""
    slot_of = {ra: s for s in sample_data.SLOTS for ra in s.ras}
    weeks = [
        (span, b.effect) for b in sample_leave.BLACKOUTS if (span := sample_leave.week_dates(b))
    ]
    assert sample_leave.POLICY["cover_pool"] == "Same Precinct"
    for a in sample_leave.APPLICATIONS:
        assert slot_of[a.cover].precinct == slot_of[a.ra].precinct, a.id
        for (first, last), effect in weeks:
            if a.start <= last and first <= a.end:
                assert effect == "Appeal only" and a.appeal, a.id


def test_the_admin_pages_follow_the_policy_switches(monkeypatch) -> None:
    """Appeals off: no appeal tile or stage filter. A ticked appointment no
    slot holds: the dashboard flags the gap. An appeal is never reassigned:
    the Master decides it personally."""
    c = client()
    assert ">Reassign the approval</button>" not in c.get(ADMIN + "records/L-0105").text
    assert ">Reassign the approval</button>" in c.get(ADMIN + "records/L-0101").text
    detail = c.get(ADMIN + "records/L-0101").text
    assert (
        '<span class="chip chip-mute">AY2026-2027</span>' in detail
        and "27 Oct</span> · Submitted by Chloe Lim" in detail
    )
    assert sample_leave.delegable() == [
        "Daniel Koh",
        "Mei Ling Tan",
        "Arjun Nair",
        "Grace Ho",
        "Benjamin Chua",
        "Farah Aziz",
        "Kenneth Lau",
        "Siti Rahman",
        "Wei Jie Ong",
    ]
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    # An appeal already made stands (author, 2026-10-28): L-0105 keeps its tile and filter.
    assert "Appeal to the Master" in sample_leave.stages(open_only=True)
    no_appeals = tuple(a for a in sample_leave.APPLICATIONS if a.stage != "Appeal to the Master")
    monkeypatch.setattr(sample_leave, "APPLICATIONS", no_appeals)
    dash = c.get(ADMIN).text
    assert "Appeal to the Master" not in dash
    chips = c.get(ADMIN + "records?period=whole").text.split('class="col-chips rec-filters"')[1]
    assert "Appeal to the Master" not in chips.split("</div>")[0]
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("Master",))  # held on no slot
    card = c.get(ADMIN).text.split('id="gaps-h"')[1].split("</section>")[0]
    assert "9 Precincts without a first approver." in card and card.count(">Gap</span>") == 9


def test_stage_names_and_titles_follow_the_policy(monkeypatch) -> None:
    c = client()
    assert (
        "<title>Leave dashboard" in c.get(ADMIN).text
        and "<h1>Leave dashboard</h1>" in c.get(ADMIN).text
    )
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert "Pending first approval" not in sample_leave.stages()
    assert sample_leave.delegable()[:2] == [
        "Priya Raman",
        "Marcus Tan",
    ]  # a kept delegation still reads
    card = c.get(ADMIN + "routing").text.split('id="delegates-h"')[1]
    assert (
        card.split('aria-label="Delegate 1: acting for"')[1]
        .split("</select>")[0]
        .count("<option selected>Grace Ho</option>")
        == 1
    )
    monkeypatch.setitem(sample_leave.POLICY, "first", "slot")
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("Master",))
    steps = [s for _, s, _ in sample_leave.timeline(_by_id("L-0103"))]
    assert "First approval by the first approver" in steps and not any("No one" in s for s in steps)


def test_appeals_by_invitation(monkeypatch) -> None:
    """Ruled 2026-10-29: appeals open, by invitation, or off. By invitation,
    an RA writes in, someone the policy lets open appeals agrees in
    principle and opens an appeal for them on Appeals; until then the RA is
    not offered one."""
    c = client()
    # Open, the staff Appeals opens none (audit, 2026-10-29); the admin
    # page that did the same is retired (2026-11-10).
    open_page = c.get(STAFF_ADMIN_APPEALS).text
    assert (
        'id="inv-ra"' not in open_page
        and "every RA may send one, so none is opened for them" in open_page
    )
    assert "Invitations take effect only while appeals are by invitation" in open_page
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "Off")
    off = c.get(STAFF_ADMIN_APPEALS).text
    assert 'id="inv-ra"' not in off and "Appeals are off: no new one can be opened" in off
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    # The admin Appeals tab is gone (author, 2026-11-10): its path goes to
    # the staff Appeals, as the Residential Admin sees it.
    went = c.get(ADMIN + "appeals", follow_redirects=False)
    assert went.status_code == 303
    assert went.headers["location"] == "/ra-leave/staff/appeals?as=Rachel%20Yeo"
    assert 'href="/ra-leave/admin/appeals"' not in c.get(ADMIN).text
    page = c.get(STAFF_ADMIN_APPEALS).text
    assert 'href="/ra-leave/staff/appeals?as=Rachel%20Yeo" aria-current="page"' in page
    rows = re.findall(
        r'<td class="strong nowrap">([^<]*)</td>\s*<td class="nowrap">([^<]*)</td>', page
    )
    assert rows[:2] == [("Gwen Ho", "Sam Lee"), ("Kai Ng", "Rachel Yeo")]
    by = page.split('id="inv-by"')[1].split("</select>")[0]
    assert 'href="/ra-leave/staff/applications/L-0105?as=Rachel%20Yeo">Sent: L-0105</a>' in page
    # On the staff page the viewer, the Admin, opens appeals as herself.
    assert "<option selected>Rachel Yeo</option>" in by and by.count("<option") == 1
    assert ">Sent: L-0105</a>" in page and 'aria-label="Withdraw Kai Ng\'s invitation"' in page
    assert (
        '<span class="chip chip-mute">Lapsed</span>' in page and "Withdraw Nathan Yeo" not in page
    )
    policy = c.get(ADMIN + "policy").text
    assert "someone with permission can open an appeal for that RA" in policy
    # Who approves an invited appeal: the usual approvers, or the usual
    # first approver then the Master (author, 2026-11-10); the sample's is
    # the Master, as routing does.
    approvers = re.findall(r'name="appeal-approval" value="(\w+)"( checked)?', policy)
    assert approvers == [("usual", ""), ("master", " checked")]
    assert "the normal first approver, and the Master" in policy
    assert 'aria-label="Open appeals, Master" checked' in policy
    assert 'aria-label="Open appeals, Residential Admin" checked' in policy
    assert 'aria-label="Open appeals, Residential Executive" disabled' in policy
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    assert sample_leave.appeals_on()
    assert sample_leave.can_appeal("Kai Ng") and not sample_leave.can_appeal(
        "Gwen Ho"
    )  # hers is used
    assert not sample_leave.can_appeal("Chloe Lim")
    assert not sample_leave.invitation_for("Kai Ng", sample_leave.date(2026, 11, 11))  # lapsed
    assert "Invitations take effect" not in c.get(STAFF_ADMIN_APPEALS).text
    assert 'name="appeals" value="By invitation" checked' in c.get(ADMIN + "policy").text
    routing = c.get(ADMIN + "routing").text
    assert (
        ">Appeals final</th>" in routing
        and "final approval and appeals are not delegable" in routing
    )
    assert "Extra leave the Master grants on appeal" in c.get(ADMIN + "entitlements").text
    future = sample_leave.Invitation(
        "Mira Sato",
        "Sam Lee",
        sample_leave.date(2026, 11, 2),
        sample_leave.date(2026, 11, 9),
        "From next week",
    )
    assert sample_leave.invitation_status(
        future
    ) == "From 2 Nov" and not sample_leave.invitation_for("Mira Sato")
    assert (
        "<dd>By invitation: The usual first approver, then the Master (Sam Lee), personally</dd>"
        in c.get(ADMIN).text
    )
    assert "Appeal to the Master" in c.get(ADMIN).text  # appeals exist: the tile stays


def test_leave_days_count_as_the_policy_says(monkeypatch) -> None:
    """Ruled 2026-10-29: every day by default (RAs work weekends and public
    holidays); optionally weekdays only, or working days."""
    d = sample_leave.date
    assert sample_leave.leave_days(d(2026, 11, 6), d(2026, 11, 9)) == 4  # Fri to Mon
    page = client().get(ADMIN + "policy").text
    assert re.findall(r'name="day-count" value="([^"]*)"( checked)?', page) == [
        ("Every day", " checked"),
        ("Weekdays", ""),
        ("Working days", ""),
    ]
    assert 'aria-label="Public holiday 2: date" value="2026-11-09"' in page
    assert "<dt>Days counted</dt><dd>Every day</dd>" in client().get(ADMIN).text
    monkeypatch.setitem(sample_leave.POLICY, "day_count", "Weekdays")
    assert sample_leave.leave_days(d(2026, 11, 6), d(2026, 11, 9)) == 2
    assert _by_id("L-0101").days == 1  # Chloe Lim, Fri 6 to Sun 8 Nov
    assert sample_leave.days_in_term(_by_id("L-0101")) == 1
    weekdays = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    assert "<dt>Days counted</dt><dd>Weekdays</dd>" in client().get(ADMIN).text
    monkeypatch.setitem(sample_leave.POLICY, "day_count", "Working days")
    assert (
        sample_leave.leave_days(d(2026, 12, 24), d(2027, 1, 1)) == 5
    )  # less Christmas and New Year
    assert (
        sample_leave.leave_days(d(2026, 11, 6), d(2026, 11, 9)) == 1
    )  # less Deepavali, observed Mon
    monkeypatch.setitem(sample_leave.POLICY, "day_count", "Every day")
    every = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    chloe = ("Chloe Lim", _by_id("L-0101").leave_type)
    # L-0101 charges 3 days rather than 1, so Chloe Lim's balance follows the setting.
    assert every[chloe]["available"] == weekdays[chloe]["available"] - 2


def test_review_fixes_on_the_admin_side(monkeypatch) -> None:
    """The 2026-10-29 review: gaps in final approval are flagged, a delegate
    for someone no longer approving says so, copy follows the setting, and
    a phone-width table keeps its hidden header inside its scroll box."""
    c = client()
    assert ".table-wrap { position: relative;" in c.get(ADMIN).text
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ("RSLM",))
    routing = c.get(ADMIN + "routing").text
    assert "<option selected>Grace Ho</option>" in routing and "Not a first approver" in routing
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert 'value="RSLM" checked' not in c.get(ADMIN + "policy").text
    assert "Pending first approval" not in c.get(ADMIN + "records?period=whole").text
    monkeypatch.setitem(sample_leave.POLICY, "final", "named")
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ())
    dashboard = c.get(ADMIN).text
    assert (
        "No one may give final approval" in dashboard
        and "then no one: no final approver is set" in dashboard
    )
    monkeypatch.setitem(sample_leave.POLICY, "cover_mode", "Named only")
    assert "declined cover" not in c.get(ADMIN).text
    assert "every RA may send one, so none is opened for them" in c.get(STAFF_ADMIN_APPEALS).text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_types", ())
    assert "Leave policy names no one to open appeals." in c.get(STAFF_ADMIN_APPEALS).text
    monkeypatch.setitem(sample_leave.POLICY, "first", "slot")
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ())
    assert "No first approval" in c.get(ADMIN).text  # no tick, none needed
    assert (
        "Kai Ng" in c.get(STAFF_ADMIN_APPEALS).text
        and "agreed by email" not in c.get(STAFF_ADMIN_APPEALS).text
    )
    detail = c.get(ADMIN + "records/L-0105").text
    assert (
        "Personal leave · extra leave" in detail
        and 'href="/ra-leave/admin/records" aria-current="true"' in detail
    )


def test_cancelled_leave_and_decision_records(monkeypatch) -> None:
    """The 2026-10-29 review: approved leave cancelled by an admin has its
    own stage and releases its cover (spec §30); each decision shows its
    date and remarks (spec §14, §15, §19)."""
    c = client()
    cancelled = _by_id("L-0116")
    assert cancelled.stage == "Cancelled" and cancelled.cover_status == "Cancelled"
    assert ">Cancelled<span" in c.get(ADMIN + "records?period=whole").text  # its chip
    steps = sample_leave.timeline(cancelled)
    assert steps[-1] == (
        "20 Oct",
        "Cancelled by Rachel Yeo, Residential Admin",
        sample_leave.DECISIONS["L-0116"]["cancelled"][1],
    )
    assert _by_id("L-0111").cover_status == "Cancelled"  # withdrawn
    kai = next(
        r
        for r in sample_leave.entitlement_rows()
        if r["ra"] == "Kai Ng" and r["type"] == "Personal leave"
    )
    assert kai["used"] == 0  # cancelled leave is not charged
    # The final approver sees the first approver's date and remarks (§14).
    decide = c.get("/ra-leave/staff/applications/L-0103?as=Rachel%20Yeo").text
    assert (
        "24 Oct</span> · First approval by" in decide and "the Precinct is fully staffed" in decide
    )
    # The Master sees the staff remarks on an appeal (§15).
    assert (
        "Remarks from Benjamin Chua, RF"
        in c.get("/ra-leave/staff/applications/L-0105?as=Sam%20Lee").text
    )


def test_dashboard_reports_and_export(monkeypatch) -> None:
    """The 2026-10-29 review, spec §25 and §4.6: upcoming leave, extra
    leave granted by term, entitlement anomalies and recent corrections on
    the dashboard; Applications exports what it shows."""
    c = client()
    dashboard = c.get(ADMIN).text
    for heading in (
        "Upcoming leave",
        "Extra leave granted",
        "Entitlement anomalies",
        "Recent administrative corrections",
    ):
        assert f">{heading}" in dashboard, heading
    assert "<dt>AY2026-2027, Term 1</dt><dd>3 days, 1 appeal</dd>" in dashboard
    assert (
        "Cancelled approved leave for Kai Ng" in dashboard
        and "no RA is over entitlement" in dashboard
    )
    assert [a.id for a in sample_leave.upcoming()] == ["L-0115"]
    # Lucas Teo's appeal goes beyond a balance his earlier leave used.
    lucas = next(
        r
        for r in sample_leave.entitlement_rows()
        if r["ra"] == "Lucas Teo" and r["type"] == "Personal leave"
    )
    assert (
        lucas["available"] == 0
        and "Beyond entitlement</dt><dd>3 days"
        in c.get("/ra-leave/staff/applications/L-0118?as=Sam%20Lee").text
    )
    assert "Export CSV" in c.get(ADMIN + "records?period=whole").text
    monkeypatch.setitem(sample_leave.ADJUSTMENTS, ("Chloe Lim", "Personal leave"), (-9, ""))
    assert (
        "<strong>Chloe Lim</strong>, Personal leave: Over entitlement by 7 days, pending included."
        in c.get(ADMIN).text
    )


def test_an_application_counting_no_days_is_not_submitted(monkeypatch) -> None:
    """Ruled 2026-10-29: under weekdays or working days, dates counting no
    day cannot be submitted, and Apply says so."""
    assert sample_leave.zero_day_rule() == ""
    monkeypatch.setitem(sample_leave.POLICY, "day_count", "Weekdays")
    assert (
        "only on a weekend count no days, and cannot be submitted"
        in client().get("/ra-leave/apply").text
    )
    monkeypatch.setitem(sample_leave.POLICY, "day_count", "Working days")
    assert "weekends or public holidays count no days" in client().get("/ra-leave/apply").text


def test_roles_outside_the_slots_show_as_gaps(monkeypatch) -> None:
    """The cold read of the slot rule: inviters, the Master's appeals and a
    delegate outside the slots each show as a gap, and say why."""
    c = client()
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Hui Min Goh",))
    assert sample_leave.inviter_gaps() == sample_leave.precincts()
    assert (
        "names Hui Min Goh, but none holds a place in any RA's slot"
        in c.get(STAFF_ADMIN_APPEALS).text
    )
    routing = c.get(ADMIN + "routing").text
    assert ">Opens appeals</th>" in routing
    assert "9 Precincts where no one may open an appeal" in c.get(ADMIN).text
    monkeypatch.setitem(
        sample_leave.sample_data.EVERY_SLOT,
        sample_leave.TERM.key,
        {"appointments": ("Admin",), "names": ()},
    )
    assert "9 Precincts whose appeals the Master cannot decide" in c.get(ADMIN).text
    assert (
        'those in every slot on <a href="/rosters/assignments">Assignments</a> '
        "(Rachel Yeo) hold one in each" in c.get(ADMIN + "routing").text
    )
    D = sample_leave.Delegate
    monkeypatch.setattr(
        sample_leave,
        "DELEGATES",
        (D("Grace Ho", "Benjamin Chua", None, None, "has not signed in yet"),),
    )
    assert "Delegate not in slots" in c.get(ADMIN + "routing").text
    assert "1 Precinct with a delegate outside its slots" in c.get(ADMIN).text


def test_failed_emails_stay_visible_and_can_be_resent() -> None:
    """Spec §17.2 (author, 2026-10-29): a failed send stays in the outbox,
    listed on the Leave dashboard and its application, and the actor or a
    Leave admin resends it; nothing retries on its own."""
    c = TestClient(ops_app())
    failed = sample_leave.failed_emails()
    assert {e.application for e in failed} == {"L-0101", "L-0115", "L-0116"}
    board = c.get("/ra-leave/admin/").text.split('id="unsent-h"')[1].split("</section>")[0]
    assert re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', board) == [
        e.application for e in failed
    ]
    assert board.count(">Resend</button>") == len(failed)
    assert 'disabled aria-label="Resend L-0116 approved leave cancelled to Kai Ng">' in board
    # The admin sees every email on the application, sent or not.
    page = (
        c.get("/ra-leave/admin/records/L-0116")
        .text.split('id="emails-h"')[1]
        .split("</section>")[0]
    )
    assert page.count('<span class="chip chip-ok">Sent</span>') == 1  # Cover released
    assert page.count('<span class="chip chip-warn">Not sent</span>') == 1
    assert ">Resend to Kai Ng</button>" in page and "no mailbox for the address" in page
    # An admin's resend goes from their own account, naming the original
    # sender (ruled 2026-10-29).
    assert (
        "it goes from the admin's account, naming its original sender"
        in c.get("/ra-leave/admin/records/L-0116").text
    )
    assert "from your own account, naming its original sender" in c.get("/ra-leave/admin/").text
    assert 'id="emails-h"' not in c.get("/ra-leave/admin/records/L-0102").text  # no emails, no card


def test_the_audit_s_consistency_fixes() -> None:
    """The 1C.1 audit (2026-10-29): extra leave is marked in Applications; a
    delegate is chosen among those holding a place in the slots; the admin
    pages' switcher reaches the staff side; final approvers read as Policy
    names them."""
    c = client()
    apps = c.get(ADMIN + "records?period=whole").text
    row = apps.split('href="/ra-leave/admin/records/L-0118"')[1].split("</tr>")[0]
    assert (
        '<span class="chip chip-accent" title="Extra leave, granted on appeal">Extra</span>' in row
    )
    assert "Hui Min Goh" not in sample_leave.delegate_choices("Daniel Koh")  # in no slot
    assert all(
        sample_leave.delegate_fits(sample_leave.Delegate("Daniel Koh", p, None, None, ""))
        for p in sample_leave.delegate_choices("Daniel Koh")
    )
    routing = c.get(ADMIN + "routing").text
    assert ">Hui Min Goh</option>" not in routing
    board = c.get(ADMIN).text
    assert 'href="/ra-leave/staff/?as=Rachel%20Yeo">RA Leave</a>' in board
    assert ">Rosters and setup</a>" in board


def test_the_cover_tile_opens_the_set_it_counts_under_any_policy(monkeypatch) -> None:
    """Codex, 2026-11-10: with ordinary leave's cover not to be confirmed,
    the tile counts only the appeal (L-0105); its link shows that set, not
    every application whose cover is awaiting."""
    monkeypatch.setitem(sample_leave.POLICY, "cover_required", False)
    c = client()
    counted = {a.id for a in sample_leave.cover_unconfirmed()}
    page = c.get(ADMIN + "records?cover=unconfirmed&period=whole").text
    assert set(re.findall(r'href="/ra-leave/admin/records/(L-\d+)"', page)) == counted
    assert "Show all</a>" in page and "Cover not yet confirmed</span>" in page
    # A chip and the period form keep the filter.
    chips = page.split('class="col-chips rec-filters"')[1]
    assert "?cover=unconfirmed&amp;" in chips.split("</div>")[0]
    assert '<input type="hidden" name="cover" value="unconfirmed">' in page


def test_policy_permissions_say_who_does_what_over_which_ras(monkeypatch) -> None:
    """Author, 2026-11-10: one Permissions table on Policy saying who; a
    role's scope is its slots (or every slot), a named person's is chosen,
    overlaps resolved. Approvals keeps how, and sums up who; the Appeals
    card's who-may-open moves here too."""
    rows = {r["who"]: r for r in sample_leave.permission_rows()}
    assert rows["Residential Fellow"]["scope"] == ("RAs assigned to staff's slots",)
    assert rows["Master"]["scope"] == ("RAs in every slot",)
    assert rows["Residential Fellow"]["perms"] == {"first", "view"}
    assert rows["Residential Admin"]["perms"] == {"final", "open", "view", "admin"}
    assert rows["Master"]["perms"] == {"open", "view", "admin"}
    # RSLMs need no RA Leave (author, 2026-11-09): no tick, no access.
    assert rows["Residential Student Life Manager"]["perms"] == frozenset()
    assert rows["Residential Executive"]["perms"] == frozenset()
    assert rows["Hui Min Goh"]["kind"] == "named"
    assert rows["Hui Min Goh"]["scope"] == ("Cypress", "Maple 03-08")
    # Scope overlaps resolve: a choice inside one already there is not
    # added; a broader one replaces the narrower ones it holds.
    add = sample_leave.add_scope
    assert add(("All RAs",), "Maple 03-08") == ("All RAs",)
    assert add(("Cypress",), "Cypress A 04-12") == ("Cypress",)
    assert add(("Cypress A 04-05-06", "Maple 03-08"), "Cypress") == ("Maple 03-08", "Cypress")
    assert add(("Cypress", "Maple"), "All RAs") == ("All RAs",)
    assert add(("Cypress",), "Nowhere") == ("Cypress",)
    assert sample_leave.resolve_scope(["Willow A 04-05-06", "Willow A 04-12"]) == (
        "Willow A 04-12",
    )
    levels = sample_leave.scope_levels()
    assert levels["Willow A 04-05-06"] == ("All RAs", "Willow", "Willow A 04-12")

    page = client().get(ADMIN + "policy").text
    table = page.split('id="perms-h"')[1].split("</table>")[0]
    assert [h for h in re.findall(r'<th scope="col"[^>]*>([^<]+)</th>', table)] == [
        "Role or person",
        "Scope",
        "First approval",
        "Final approval",
        "Open appeals",
        "View records",
        "Admin pages",
    ]
    assert '<span class="subtle">RAs in every slot</span>' in table
    assert 'aria-label="Scope for Hui Min Goh"' in table
    assert '<span class="token">Cypress<button' in table
    assert 'aria-label="View records, Hui Min Goh" checked' in table
    assert '<option value="All RAs">' in page and '<option value="Willow A 04-05-06">' in page
    # The old who-fieldsets and the Approvals card are gone.
    assert 'name="first-types"' not in page and 'name="final-types"' not in page
    assert 'name="inviters"' not in page
    assert 'id="approvals-h"' not in page  # the summary went with the card
    # Named final approvers appear as named rows.
    monkeypatch.setitem(sample_leave.POLICY, "final", "named")
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ("Sam Lee",))
    named = {r["who"]: r for r in sample_leave.permission_rows()}
    assert "final" in named["Sam Lee"]["perms"] and named["Sam Lee"]["kind"] == "named"
    assert "final" not in named["Residential Admin"]["perms"]
    # A chosen grant keeps its row and scope beside a routing one (Codex).
    monkeypatch.setitem(sample_leave.POLICY, "final_names", ("Hui Min Goh",))
    goh = [r for r in sample_leave.permission_rows() if r["who"] == "Hui Min Goh"]
    assert sorted((sorted(r["perms"]), r["scope"]) for r in goh) == [
        (["final"], ("RAs assigned to staff's slots",)),
        (["view"], ("Cypress", "Maple 03-08")),
    ]


@pytest.mark.parametrize(
    "policy",
    [
        {},
        {"final": "named", "final_names": ("Sam Lee", "Priya Raman")},
        {"inviters": "named", "inviter_names": ("Daniel Koh",)},
        {"inviters": "slot", "inviter_types": ("RF",)},
        {"appeals": "Off"},
        {"first": "none"},
    ],
)
def test_permissions_agree_with_routing(monkeypatch, policy) -> None:
    """Review of 2026-11-10: each tick in Permissions is what routing grants,
    under every Policy setting, so the table and the app cannot disagree."""
    for key, value in policy.items():
        monkeypatch.setitem(sample_leave.POLICY, key, value)
    rows = sample_leave.permission_rows()
    roles = {r["note"]: r["perms"] for r in rows if r["kind"] == "role"}
    named = {r["who"]: r["perms"] for r in rows if r["kind"] == "named"}
    sys_admins = {n for n, *_ in sample_data.SYS_ADMINS}
    inviters = {n for p in sample_leave.precincts() for n in sample_leave.inviters_in(p)}
    for person in sample_data.STAFF:
        name = person.name
        perms = roles.get(person.abbrev, frozenset()) | named.get(name, frozenset())
        # Access follows the table (author, 2026-11-10): any tick but Admin
        # pages, over some RA, opens the staff pages.
        # A delegate standing in has RA Leave without a tick (cold read).
        if not (perms - {"admin"}) and not sample_leave._standing_in(name):  # noqa: SLF001
            assert sample_leave.scope(name) == (), name
        assert ("final" in perms) == (name in sample_leave.final_approvers()), name
        viewer = person.abbrev in sample_leave.POLICY["viewer_types"] or any(
            g.name == name and "view" in g.perms for g in sample_leave.NAMED_GRANTS
        )
        assert ("view" in perms) == viewer, name
        assert ("admin" in perms) == (name in sys_admins), name
        if name in inviters:
            assert "open" in perms, name


def test_no_decide_column_the_master_keeps_ra_leave_while_deciding(monkeypatch) -> None:
    """Author, 2026-11-10: who decides an appeal is the Appeals card's, so
    Permissions has no Decide appeals column; the Master keeps RA Leave
    while deciding appeals, with or without a tick."""
    labels = [label for _, label in sample_leave.PERMISSIONS]
    assert "Decide appeals" not in labels
    assert "Decide appeals" not in client().get(ADMIN + "policy").text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    monkeypatch.setitem(sample_leave.POLICY, "viewer_types", ("RF", "Admin"))
    monkeypatch.setitem(sample_leave.POLICY, "inviter_types", ("Admin",))
    monkeypatch.setattr(sample_data, "SYS_ADMINS", ())
    assert sample_leave.appeals_decided() and len(sample_leave.scope("Sam Lee")) == 9
    monkeypatch.setitem(sample_leave.POLICY, "appeal_approval", "usual")
    assert not sample_leave.appeals_decided() and sample_leave.scope("Sam Lee") == ()


def test_approval_chain_names_each_approver_with_their_role(monkeypatch) -> None:
    """Author, 2026-11-10: the Precincts table is Wing, Precinct, RAs, First
    approval, Final, Opens appeals, Appeals final; a name chosen by role
    carries its Staff-roster abbreviation, several comma separated."""
    monkeypatch.setitem(sample_leave.POLICY, "appeals", "By invitation")
    page = client().get(ADMIN + "routing").text
    table = page.split('id="chain-h"')[1].split("</table>")[0]
    heads = re.findall(r'<th scope="col"[^>]*>([^<]+)</th>', table)
    assert heads == [
        "Wing",
        "Precinct",
        "RAs",
        "First approval",
        "Final",
        "Opens appeals",
        "Appeals final",
    ]
    assert "<td>Daniel Koh (RF)" in table
    assert "<td>Rachel Yeo (Admin)</td>" in table
    assert "<td>Sam Lee (Master), Rachel Yeo (Admin)</td>" in table
    assert "<td>Sam Lee (Master)</td>" in table
    assert ">RSLM</th>" not in table and ">RF</th>" not in table
    # A delegate stands in by name, not role (cold read): Marcus Tan.
    assert "<td>Marcus Tan <span" in table
    assert sample_leave.with_roles(["Sam Lee", "Sam Lee"]) == "Sam Lee (Master)"
    monkeypatch.setitem(sample_leave.POLICY, "inviters", "named")
    monkeypatch.setitem(sample_leave.POLICY, "inviter_names", ("Sam Lee",))
    named = client().get(ADMIN + "routing").text.split('id="chain-h"')[1]
    assert "<td>Sam Lee</td>" in named.split("</table>")[0]


def test_first_approval_is_needed_while_someone_is_ticked(monkeypatch) -> None:
    """Author, 2026-11-10: the Approvals card is gone; Permissions' First
    approval ticks say whether a first approval is needed, so no tick
    means none, and a "needed but no one ticked" gap cannot arise."""
    assert sample_leave.POLICY["first"] == "slot"  # RF ticked
    page = client().get(ADMIN + "policy").text
    assert 'id="approvals-h"' not in page and "go straight to final approval" in page
    monkeypatch.setitem(sample_leave.POLICY, "first_types", ())
    assert sample_leave.POLICY["first"] == "none"
    assert not any(r.gap for r in sample_leave.routes())
    waiting = sample_leave.by_id("L-0101")
    assert waiting is not None and waiting.stage == "Pending final approval"
