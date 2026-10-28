"""RA Leave's sys admin pages (`/ra-leave/admin/`), segment 1C item 1:
placeholders on `sample_leave`, built first since the rest of RA Leave is
downstream of their configuration (author, 2026-10-28)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_data, sample_leave
from residentialapps.residentialops.main import create_app as ops_app
from residentialapps.residentialops.pages import LEAVE_ADMIN_TABS

ADMIN = "/ra-leave/admin/"


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
    tiles = re.findall(r'href="([^"]*)">\s*<span class="tile-n">(\d+)</span>\s*<span class="tile-l">([^<]*)', page)
    assert [(n, label) for _, n, label in tiles] == [
        ("4", "Pending first approval"), ("1", "Pending final approval"), ("1", "Appeal to the Master"),
        ("2", "Cover not yet confirmed"),
    ]
    assert tiles[0][0] == "/ra-leave/admin/applications?stage=Pending%20first%20approval"
    assert tiles[3][0] == "/ra-leave/admin/applications?cover=unconfirmed"
    attention = page.split('id="attention-h"')[1].split("</section>")[0]
    assert re.findall(r">(L-\d+)</a>", attention) == ["L-0103", "L-0104", "L-0107", "L-0109"]
    assert "Pranav Iyer is away too" in attention and "Chloe Lim declined cover" in attention
    assert attention.count("Away on the same days in one Precinct") == 1
    assert "<td class=\"strong\">Olivia Ng, Pranav Iyer</td>" in attention
    away = page.split('id="away-h"')[1].split("</section>")[0]
    assert re.findall(r'<td class="strong nowrap">([^<]*)', away) == ["Maya Seah", "Olivia Ng", "Pranav Iyer"]
    assert "Maple 03-08</strong>: Grace Ho has not signed in yet" in page


def test_a_tile_opens_the_rows_it_counts() -> None:
    c = client()
    first = c.get(ADMIN + "applications", params={"stage": "Pending first approval"}).text
    assert re.findall(r'href="/ra-leave/admin/applications/(L-\d+)"', first) == ["L-0101", "L-0102", "L-0109", "L-0104"]
    assert "<option selected>Pending first approval</option>" in first
    cover = c.get(ADMIN + "applications?cover=unconfirmed").text
    assert sorted(re.findall(r'href="/ra-leave/admin/applications/(L-\d+)"', cover)) == ["L-0102", "L-0109"]
    assert "· 2 of 13" in cover


def test_policy_sets_leave_types_with_their_own_entitlement_rules() -> None:
    """Points 1–2 (author, 2026-10-28): leave that needs an application,
    each type earned per term or per month served, with a cap per year or
    term."""
    page = client().get(ADMIN + "policy").text
    assert [lt.name for lt in sample_leave.LEAVE_TYPES] == ["Personal leave", "Official leave"]
    for n, lt in enumerate(sample_leave.LEAVE_TYPES, start=1):
        assert f'aria-label="Leave type {n}: name" value="{lt.name}"' in page
        earned = page.split(f'aria-label="Leave type {n}: how it is earned"')[1].split("</select>")[0]
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
    """Point 3: blackouts by week of a term, Sunday to Saturday, so they
    carry across years; each either refuses leave or sends it to appeal."""
    page = client().get(ADMIN + "policy").text
    dates = [sample_leave.week_dates(b) for b in sample_leave.BLACKOUTS]
    assert [(d.isoformat(), e.isoformat()) for d, e in dates] == [
        ("2026-08-02", "2026-08-15"), ("2026-11-15", "2026-11-28"), ("2027-01-10", "2027-01-16"),
    ]
    assert all(d.isoweekday() == 7 and e.isoweekday() == 6 for d, e in dates)  # Sunday to Saturday
    rendered = re.findall(r'<td class="nowrap subtle">([^<]*)</td>', page)
    assert rendered == ["2 Aug – 15 Aug", "15 Nov – 28 Nov", "10 Jan – 16 Jan"]
    terms = page.split('aria-label="Blackout 1: term"')[1].split("</select>")[0]
    assert re.findall(r"<option[^>]*>([^<]*)", terms) == ["Term 1", "Term 2", "Term 3"]
    effects = re.findall(r'aria-label="Blackout \d: leave is" disabled><option( selected)?>Refused</option><option( selected)?>Appeal only', page)
    assert [("Refused" if r else "Appeal only") for r, _ in effects] == [b.effect for b in sample_leave.BLACKOUTS]


def test_policy_appeals_cover_and_approvals() -> None:
    """Points 4–6: appeals beyond entitlement on stated terms, never banked
    in advance; cover required or not, named or confirmed, from a pool;
    first and final approval."""
    page = client().get(ADMIN + "policy").text
    for name, options, current in (
        ("cover", ("Required", "Not required"), "Required" if sample_leave.POLICY["cover_required"] else "Not required"),
        ("cover-mode", sample_leave.COVER_MODES, sample_leave.POLICY["cover_mode"]),
        ("pool", sample_leave.COVER_POOLS, sample_leave.POLICY["cover_pool"]),
        ("first", sample_leave.FIRST_APPROVERS, sample_leave.POLICY["first_approver"]),
        ("final", sample_leave.FINAL_APPROVERS, sample_leave.POLICY["final_approver"]),
    ):
        radios = re.findall(rf'<input type="radio" id="{name}-\d" name="{name}" value="([^"]*)"( checked)?', page)
        assert [v for v, _ in radios] == list(options), name
        assert [v for v, c in radios if c] == [current], name
    on_off = re.findall(r'<input type="radio" id="appeals-\d" name="appeals" value="([^"]*)"( checked)?', page)
    assert on_off == [("On", " checked" if sample_leave.POLICY["appeals"] else ""), ("Off", "" if sample_leave.POLICY["appeals"] else " checked")]
    assert "refused while appeals are off" in page  # system-wide switch (author, 2026-10-28)
    assert sample_leave.POLICY["appeal_terms"] in page
    assert "unless the Master overrides it" in page and "no built-in default" in page
    assert "cannot be done in advance and banked" in page
    assert "The Residential Admin (Rachel Yeo)" in page and "The Master (Sam Lee), personally" in page
    assert "<dt>Final approval</dt>" not in page  # a choice now, not fixed (author, 2026-10-28)


def test_entitlements_follow_the_policy_rules() -> None:
    page = client().get(ADMIN + "entitlements").text
    rows = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    assert len(rows) == len(sample_data.RAS) * len(sample_leave.LEAVE_TYPES)
    pick = ("entitlement", "adjustment", "used", "pending", "available")
    # Personal leave: 5 for Term 1, available only within it.
    assert [rows["Gwen Ho", "Personal leave"][k] for k in pick] == [5, 0, 5, 0, 0]  # used up: hence her appeal
    assert [rows["Leon Chia", "Personal leave"][k] for k in pick] == [5, 2, 0, 5, 2]
    assert [rows["Chloe Lim", "Personal leave"][k] for k in pick] == [5, 0, 0, 3, 2]
    # Official leave: 1 a month served in the term; two whole months since
    # its 3 Aug start, and since Umairah Salleh's 17 Aug.
    assert [rows["Hana Ito", "Official leave"][k] for k in pick] == [2, 0, 0, 2, 0]
    assert rows["Umairah Salleh", "Official leave"]["entitlement"] == 2
    assert sample_leave.months_served(sample_leave.date(2026, 9, 1)) == 1
    assert rows["Gwen Ho", "Personal leave"]["pending"] == 0  # her appeal is extra leave, not charged (§7.5)
    assert "+2<div class=\"subtle\">Granted by the Master" in page  # the reason, visible
    assert "Email,Leave type,Adjustment,Reason" in page
    assert f"<option selected>{sample_leave.TERM.label}</option>" in page and "do not carry over" in page
    assert page.count(">Adjust</button>") == len(rows)


def test_the_approval_chain_is_derived_from_assignments_and_the_policy() -> None:
    page = client().get(ADMIN + "routing").text
    routes = sample_leave.routes()
    assert [r.precinct for r in routes] == list(dict.fromkeys(s.precinct for s in sample_data.SLOTS))
    assert sum(r.ras for r in routes) == len(sample_data.SLOTS)
    for r in routes:
        assert r.first == ("Benjamin Chua" if r.rf == "Grace Ho" else r.rf)
    assert page.count(">Delegate</span>") == 1 and "Grace Ho has not signed in yet" in page


def test_a_delegate_stands_in_for_a_person_between_dates() -> None:
    """Ruled 2026-10-28: a delegate acts for one person on all their slots,
    with optional dates; first approval only."""
    grace, daniel = sample_leave.DELEGATES
    assert grace.active() and grace.dates == "Until removed"
    assert not daniel.active() and daniel.active(sample_leave.date(2026, 12, 7)) and not daniel.active(sample_leave.date(2026, 12, 19))
    assert daniel.dates == "7 Dec – 18 Dec"
    cypress = next(r for r in sample_leave.routes() if r.rf == "Daniel Koh")
    assert cypress.first == "Daniel Koh" and not cypress.delegate  # not yet
    page = client().get(ADMIN + "routing").text
    card = page.split('id="delegates-h"')[1].split("</section>")[0]
    assert "<span class=\"chip chip-warn\">Standing in</span>" in card and "<span class=\"chip chip-mute\">7 Dec – 18 Dec</span>" in card
    acting_for = card.split('aria-label="Delegate 1: acting for"')[1].split("</select>")[0]
    assert "<option selected>Grace Ho</option>" in acting_for and "Sam Lee" not in acting_for and "Rachel Yeo" not in acting_for
    assert 'aria-label="Delegate 2: from" value="2026-12-07"' in card and 'aria-label="Delegate 1: from" value=""' in card
    assert "final approval and appeals are not delegable" in card
    assert "Set a delegate for" not in page  # by person now, not by Precinct
    assert "for AY2026-2027, Term 1 and the policy's first and final approvers (RF, Admin)" in page


def test_applications_list_every_one_and_open_to_their_timeline() -> None:
    c = client()
    page = c.get(ADMIN + "applications").text
    for a in sample_leave.APPLICATIONS:
        assert f'href="/ra-leave/admin/applications/{a.id}">{a.id}</a>' in page
    detail = c.get(ADMIN + "applications/L-0105").text
    assert "Gwen Ho" in detail and "family wedding" in detail
    assert "Sent to Sam Lee as an extra-leave appeal" in detail
    approved = c.get(ADMIN + "applications/L-0106").text
    assert "Final approval by Rachel Yeo" in approved and ">Cancel approved leave</button>" in approved
    assert "Reassign" not in approved
    rejected = c.get(ADMIN + "applications/L-0110").text
    assert ">Correct the record</button>" in rejected and "Cancel" not in rejected and "Reassign" not in rejected
    assert c.get(ADMIN + "applications/L-9999").status_code == 404


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
    assert sample_leave.months_served(sample_leave.date(2024, 8, 1)) == 2  # a returning RA: this term only
    assert sample_leave.months_served(sample_leave.date(2026, 9, 29)) == 0  # TODAY is the 28th
    assert sample_leave.months_served(sample_leave.date(2026, 9, 28)) == 1
    assert sample_leave.months_served(start, terms[1]) == 0  # Term 2 has not begun
    monthly = lt("X", "X", "Per month served", 2, 6, "year")
    assert sample_leave.entitlement(monthly, start, terms[0]) == 4  # two months so far
    page = client().get(ADMIN + "policy").text
    assert "do not carry to the next" in page and "Per academic year" not in page


def test_used_and_pending_count_only_the_terms_own_days(monkeypatch) -> None:
    """Leave in another term never touches this term's figures; leave across
    a term's end is charged to each term for its own days."""
    before = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    App = sample_leave.Application
    extra = (
        App("L-0901", "Chloe Lim", "Personal leave", sample_leave.date(2027, 2, 1), sample_leave.date(2027, 2, 3),
            "Ethan Wong", "Confirmed", "Approved", sample_leave.date(2026, 10, 20)),
        App("L-0902", "Leon Chia", "Personal leave", sample_leave.date(2027, 1, 8), sample_leave.date(2027, 1, 12),
            "Mira Sato", "Confirmed", "Pending first approval", sample_leave.date(2026, 10, 20)),
    )
    monkeypatch.setattr(sample_leave, "APPLICATIONS", sample_leave.APPLICATIONS + extra)
    after = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    assert after["Chloe Lim", "Personal leave"] == before["Chloe Lim", "Personal leave"]
    assert after["Leon Chia", "Personal leave"]["pending"] == before["Leon Chia", "Personal leave"]["pending"] + 3  # 8–10 Jan
    assert sample_leave.days_in_term(extra[1], [t for t in sample_data.TERMS if t.number == 2 and t.year == "AY2026-2027"][0]) == 2


def test_appeals_switched_off_leave_no_appeal_route(monkeypatch) -> None:
    """Appeals beyond entitlement switch on or off for the whole system
    (author, 2026-10-28): off, no page offers or names an appeal route."""
    c = client()
    on = c.get(ADMIN).text.split('id="policy-h"')[1].split("</section>")[0]
    assert "<dt>Appeals</dt><dd>On, to the Master</dd>" in on
    assert ">Appeals</th>" in c.get(ADMIN + "routing").text
    monkeypatch.setitem(sample_leave.POLICY, "appeals", False)
    policy = c.get(ADMIN + "policy").text
    assert 'name="appeals" value="Off" checked' in policy
    assert "Not offered anywhere" in policy and "The Master (Sam Lee), personally" not in policy
    assert "<dt>Appeals</dt><dd>Off</dd>" in c.get(ADMIN).text
    routing = c.get(ADMIN + "routing").text
    assert ">Appeals</th>" not in routing and "final approval is the same for the whole Unit" in routing
