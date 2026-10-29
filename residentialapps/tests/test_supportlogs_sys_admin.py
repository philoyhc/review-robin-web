"""Support Logs' Sys admin on sample data, segment 1D item 1 rung 6: Access
over the Staff roster, the configured lists, the cluster list and the
administrative audit; no support content (functional spec §3.3, §3.4,
§11.3; roles rules 1, 6, 8, 9)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app

ROSTER = Path(__file__).resolve().parents[1] / "docs" / "sample_data" / "staff_roster.csv"
SYS_ADMIN_PAGES = ("/sys-admin/", "/sys-admin/configuration", "/sys-admin/clusters", "/sys-admin/audit")
RACHEL, SUPER = "?as=Rachel%20Yeo", "?as=Platform%20super-admin"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def test_access_lists_every_active_roster_member_once(client: TestClient) -> None:
    with ROSTER.open(newline="") as f:
        roster = [(row["Name"], row["Abbrev"]) for row in csv.DictReader(f) if not row["To"]]
    assert list(sample.STAFF_ROSTER) == roster
    table = section(client.get("/sys-admin/" + RACHEL).text, "access-h")
    names = re.findall(r'<td class="strong">([^<]+?)(?: <span|</td>)', table)
    assert names == [name for name, _ in roster]
    assert "Platform super-admin" not in names  # holds administration from the platform, never a row


def test_each_row_shows_the_grants_held(client: TestClient) -> None:
    table = section(client.get("/sys-admin/" + RACHEL).text, "access-h")
    for name, _ in sample.STAFF_ROSTER:
        for col in sample.ACCESS_COLUMNS:
            if col == "Other Staff view":
                continue
            box = re.search(rf'<input type="checkbox" aria-label="{re.escape(col)} for {name}"( checked)? disabled>', table)
            assert box and bool(box.group(1)) == (col in sample.grants_of(name)), (name, col)
    assert sample.view_scope("Siti Rahman") == "Identifiable" and sample.view_scope("Kenneth Lau") == "Aggregate"
    siti = table.split("Other Staff view for Siti Rahman")[1].split("</select>")[0]
    assert "<option selected>Identifiable</option>" in siti
    assert "<option selected>None</option>" in table.split("Other Staff view for Wei Jie Ong")[1].split("</select>")[0]


def test_lapsed_grants_head_the_page(client: TestClient) -> None:
    page = client.get("/sys-admin/" + RACHEL).text
    assert page.index('id="lapsed-h"') < page.index('id="access-h"')
    lapsed = section(page, "lapsed-h")
    assert "Jason Teo" in lapsed and 'aria-label="Revoke Jason Teo\'s lapsed grants">Revoke</button>' in lapsed
    assert all(name != "Jason Teo" for name, _ in sample.STAFF_ROSTER)


def test_sys_admin_is_the_super_admin_s_to_grant(client: TestClient) -> None:
    """The column and the viewer's own row are marked, so wiring (item 2)
    carries the rule: the Sys admin column is the super-admin's, and nobody
    acts on their own access (roles rules 1, 6)."""
    rachel = section(client.get("/sys-admin/" + RACHEL).text, "access-h")
    assert "you see it read-only" in rachel
    assert "You grant and revoke Sys admin." in client.get("/sys-admin/" + SUPER).text
    assert rachel.count("data-super-admin-only") == 1 + len(sample.STAFF_ROSTER)  # the header and every row's cell
    assert re.search(r'<th scope="col" data-super-admin-only>Sys admin</th>', rachel)
    own = re.findall(r"<tr data-own-row>(.*?)</tr>", rachel, re.S)
    assert len(own) == 1 and "Rachel Yeo" in own[0] and '<span class="chip chip-mute">You</span>' in own[0]
    assert "data-own-row" not in section(client.get("/sys-admin/" + SUPER).text, "access-h")  # no row of their own


def test_appointments_are_derived_pills_and_columns_sort_by_value(client: TestClient) -> None:
    table = section(client.get("/sys-admin/" + RACHEL).text, "access-h")
    assert '<td data-sort-value="RF"><span class="pill-derived">Residential Fellow (RF)</span></td>' in table
    assert '<span class="pill-derived">Master</span>' in table
    siti = table.split("Siti Rahman</td>")[1].split("</tr>")[0]
    assert 'data-sort-value="Identifiable"' in siti
    wei = table.split("Wei Jie Ong</td>")[1].split("</tr>")[0]
    assert 'data-sort-value=""' in wei and 'data-sort-value="Identifiable"' not in wei


def test_configuration_renders_the_seeded_lists(client: TestClient) -> None:
    page = client.get("/sys-admin/configuration" + RACHEL).text
    for key, values in (("durations-h", sample.DURATIONS), ("types-h", sample.ENCOUNTER_TYPES),
                        ("concerns-h", [c for c, _ in sample.CONCERN_AREAS]), ("modes-h", sample.MODES),
                        ("follow-h", sample.FOLLOW_UP_CADENCES), ("sources-h", sample.ASSIGNMENT_SOURCES),
                        ("cadences-h", sample.ASSIGNMENT_CADENCES), ("steps-h", sample.ESCALATION_STEPS),
                        ("outcomes-h", sample.CLOSURE_OUTCOMES)):
        assert re.findall(r"<li>([^<]+)</li>", section(page, key).replace("&#39;", "'")) == list(values), key
    assert all(reason in section(page, "rules-h") for reason, _ in sample.CONSULTATION_REASONS)


def test_clusters_list_names_only(client: TestClient) -> None:
    page = section(client.get("/sys-admin/clusters" + RACHEL).text, "cl-h")
    assert re.findall(r'<span class="strong">([^<]+)</span>', page) == list(sample.CLUSTERS)


def test_the_audit_log_is_administrative_only(client: TestClient) -> None:
    table = section(client.get("/sys-admin/audit" + RACHEL).text, "audit-h")
    kinds = re.findall(r'<td><span class="chip chip-mute">([^<]+)</span></td>', table)
    assert kinds == [a.kind for a in sample.ADMIN_AUDIT] and set(kinds) <= {"Access", "Configuration", "Clusters"}
    lapse = next(a for a in sample.ADMIN_AUDIT if "lapsed" in a.action)
    assert lapse.actor == "Support Logs" and lapse.reason.startswith("Residential Operations")  # a causal pair (§11.3)


def test_administration_sees_no_support_content(client: TestClient) -> None:
    for path in SYS_ADMIN_PAGES:
        for who in (RACHEL, SUPER):
            page = client.get(path + who).text
            for s in sample.STUDENTS:
                assert s.name not in page and s.email not in page, (path, who, s.name)
            assert "/students/" not in page and "/flags/" not in page and "/plans/P-" not in page, (path, who)


def test_only_administration_reaches_sys_admin(client: TestClient) -> None:
    for path in SYS_ADMIN_PAGES:
        for name in ("Daniel Koh", "Sam Lee", "Marcus Tan", "Siti Rahman", "Hui Min Goh"):
            assert client.get(f"{path}?as={name.replace(' ', '%20')}").status_code == 403, (path, name)
        assert client.get(path + SUPER).status_code == 200, path
