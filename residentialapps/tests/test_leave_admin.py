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


def test_policy_makes_the_period_first_approver_and_cover_pool_configurable() -> None:
    """Configurable, not fixed (author, 2026-10-28), each a radio group with
    the sample's choice checked; inert until item 2."""
    page = client().get(ADMIN + "policy").text
    for name, options, current in (
        ("period", sample_leave.PERIODS, sample_leave.POLICY["period"]),
        ("first", sample_leave.FIRST_APPROVERS, sample_leave.POLICY["first_approver"]),
        ("pool", sample_leave.COVER_POOLS, sample_leave.POLICY["cover_pool"]),
        ("confirm", ("Cover must be confirmed", "Cover is named only"), "Cover must be confirmed"),
    ):
        radios = re.findall(rf'<input type="radio" id="{name}-\d" name="{name}" value="([^"]*)"( checked)?', page)
        assert [v for v, _ in radios] == list(options), name
        assert [v for v, c in radios if c] == [current], name
    for n, (leave_type, abbrev, days) in enumerate(sample_leave.LEAVE_TYPES, start=1):
        assert f'aria-label="Leave type {n}: name" value="{leave_type}"' in page
        assert f'aria-label="Leave type {n}: usual days" value="{days}"' in page
    assert "The Residential Admin (Rachel Yeo)" in page and "The Master (Sam Lee), personally" in page


def test_entitlements_show_available_after_used_pending_and_adjustments() -> None:
    page = client().get(ADMIN + "entitlements").text
    rows = {(r["ra"], r["type"]): r for r in sample_leave.entitlement_rows()}
    assert len(rows) == len(sample_data.RAS) * len(sample_leave.LEAVE_TYPES)
    pick = ("entitlement", "adjustment", "used", "pending", "available")
    assert [rows["Gwen Ho", "Annual leave"][k] for k in pick] == [14, 0, 14, 0, 0]  # used up: hence her appeal
    assert [rows["Leon Chia", "Annual leave"][k] for k in pick] == [14, 2, 0, 5, 11]
    assert [rows["Chloe Lim", "Annual leave"][k] for k in pick] == [14, 0, 0, 3, 11]
    assert [rows["Bella Koh", "Compassionate leave"][k] for k in pick] == [3, 0, 0, 3, 0]
    assert rows["Gwen Ho", "Annual leave"]["pending"] == 0  # her appeal is extra leave, not charged (§7.5)
    assert "+2<div class=\"subtle\">Carried over by the Master" in page  # the reason, visible
    assert "Email,Leave type,Days" in page
    assert page.count(">Adjust</button>") == len(rows)


def test_the_approval_chain_is_derived_from_assignments_and_the_policy() -> None:
    page = client().get(ADMIN + "routing").text
    routes = sample_leave.routes()
    assert [r.precinct for r in routes] == list(dict.fromkeys(s.precinct for s in sample_data.SLOTS))
    assert sum(r.ras for r in routes) == len(sample_data.SLOTS)
    for r in routes:
        assert r.first == (sample_leave.DELEGATES[r.precinct][0] if r.delegate else r.rf)
        assert f'aria-label="Set a delegate for {r.precinct}"' in page
    assert page.count(">Delegate</span>") == 1 and "Grace Ho has not signed in yet" in page
    assert "for AY2026-2027, Term 1 and the policy's first approver (RF)" in page


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
