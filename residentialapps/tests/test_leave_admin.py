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
    page = client().get(ADMIN).text
    for stage, count in sample_leave.pending_by_stage():
        assert f'<span class="tile-n">{count}</span>\n        <span class="tile-l">{stage}</span>' in page
    attention = page.split('id="attention-h"')[1].split("</section>")[0]
    for a in sample_leave.APPLICATIONS:
        assert (f">{a.id}</a>" in attention) == (
            a.overdue or (a.stage in sample_leave.OPEN_STAGES and a.cover_status == "Declined")
            or a in sample_leave.cover_while_away()
        ), a.id
    assert "Pranav Iyer is away too" in attention and "Chloe Lim declined cover" in attention
    assert "Away on the same days in one Precinct" in attention
    away = page.split('id="away-h"')[1].split("</section>")[0]
    assert [n for n in ("Maya Seah", "Olivia Ng", "Pranav Iyer") if n in away] == ["Maya Seah", "Olivia Ng", "Pranav Iyer"]
    assert "Maple 03-08</strong>: Grace Ho has not signed in yet" in page


def test_policy_makes_the_period_first_approver_and_cover_pool_configurable() -> None:
    """Configurable, not fixed (author, 2026-10-28), each a radio group with
    the sample's choice checked; inert until item 2."""
    page = client().get(ADMIN + "policy").text
    for name, options, current in (
        ("period", sample_leave.PERIODS, sample_leave.POLICY["period"]),
        ("first", sample_leave.FIRST_APPROVERS, sample_leave.POLICY["first_approver"]),
        ("pool", sample_leave.COVER_POOLS, sample_leave.POLICY["cover_pool"]),
    ):
        radios = re.findall(rf'<input type="radio" id="{name}-\d" name="{name}" value="([^"]*)"( checked)?', page)
        assert [v for v, _ in radios] == list(options), name
        assert [v for v, c in radios if c] == [current], name
    for n, (leave_type, abbrev, days) in enumerate(sample_leave.LEAVE_TYPES, start=1):
        assert f'aria-label="Leave type {n}: name" value="{leave_type}"' in page
        assert f'aria-label="Leave type {n}: days per period" value="{days}"' in page
    assert "The Residential Admin (Rachel Yeo)" in page and "The Master (Sam Lee), personally" in page


def test_entitlements_show_available_after_used_pending_and_adjustments() -> None:
    page = client().get(ADMIN + "entitlements").text
    rows = sample_leave.entitlement_rows()
    assert len(rows) == len(sample_data.RAS) * len(sample_leave.LEAVE_TYPES)
    for row in rows:
        assert row["available"] == row["entitlement"] + row["adjustment"] - row["used"] - row["pending"]
    gwen = next(r for r in rows if r["ra"] == "Gwen Ho" and r["type"] == "Annual leave")
    assert gwen["available"] == 0  # hence her appeal to the Master
    assert '<span title="Carried over by the Master' in page and ">+2</span>" in page
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
    assert page.count("chip-warn") >= 1 and "Grace Ho has not signed in yet" in page
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
    assert c.get(ADMIN + "applications/L-9999").status_code == 404
