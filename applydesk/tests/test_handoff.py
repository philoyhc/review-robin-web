"""The bundle a gate would be sent to Review Robin with (segment AD1M
rung 3, `applydesk/handoff.py`). Review Robin's own handoff route takes
these files in `tests/integration/test_handoffs.py`
(`test_an_apply_desk_gate_s_bundle_arrives_set_up`)."""

from __future__ import annotations

import csv
import io
import re

import pytest
from fastapi.testclient import TestClient

from applydesk import handoff, sample_data, stages, workflow
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"
BASE = f"/applydesk/operator/exercises/{EX}/evaluations"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _gate(exercise_id: str, number: int) -> tuple[sample_data.Exercise, stages.Gate]:
    exercise = next(e for e in sample_data.EXERCISES if e.public_id == exercise_id)
    gate = stages.gate_numbered(stages.plan_of(exercise_id), number)
    assert gate is not None
    return exercise, gate


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _bundle(exercise_id: str, number: int) -> handoff.Bundle:
    exercise, gate = _gate(exercise_id, number)
    return handoff.bundle(exercise, gate, lambda app: f"https://ad.invalid/d/{app.dossier_id}")


def test_the_files_carry_review_robin_s_columns() -> None:
    sent = _bundle(EX, 3)
    assert list(_rows(sent.files["reviewers"])[0]) == ["ReviewerName", "ReviewerEmail"]
    assert list(_rows(sent.files["reviewees"])[0]) == [
        "RevieweeName",
        "RevieweeEmail",
        "ProfileLink",
    ]
    assert list(_rows(sent.files["relationships"])[0]) == [
        "ReviewerEmail",
        "RevieweeEmail",
        "PairContextTag1.Apply-Desk-Link",
    ]
    assert sent.files["settings"].startswith("field,value,data_type\r\n")
    assert (sent.name, sent.code) == (
        "Recruitment and Selection of Residential Assistants — Staff interview",
        f"{EX}-g3",
    )


def test_each_pair_and_person_is_the_gate_s() -> None:
    _, gate = _gate(EX, 3)
    rows, _ = stages.assignments(EX, gate)
    pairs = [p for p in stages.pairs_of(rows) if p.email]
    sent = _bundle(EX, 3)
    reviewers = _rows(sent.files["reviewers"])
    assert len(reviewers) == len({p.email for p in pairs})  # each evaluator once
    links = _rows(sent.files["relationships"])
    assert [(r["ReviewerEmail"], r["RevieweeEmail"]) for r in links] == [
        (p.email, p.of.application.public_id) for p in pairs
    ]
    assert all(r["PairContextTag1.Apply-Desk-Link"] == p.source for r, p in zip(links, pairs))
    reviewees = _rows(sent.files["reviewees"])
    assert [r["RevieweeEmail"] for r in reviewees] == [a.application.public_id for a in rows]
    assert reviewees[0]["ProfileLink"] == f"https://ad.invalid/d/{rows[0].application.dossier_id}"
    assert reviewees[0]["RevieweeName"] == rows[0].application.applicant


@pytest.mark.parametrize(("exercise_id", "number"), [(EX, 2), ("k7mfr3pq8z", 1)])
def test_a_confidential_gate_sends_no_name_or_application_id(exercise_id: str, number: int) -> None:
    """Rulings 42 and 43: the Dossier ID as the key, the name redacted,
    on a confidential gate (wa9's Gate 2) and a blind exercise (k7)."""
    exercise, gate = _gate(exercise_id, number)
    assert handoff.confidential(exercise, gate)
    rows, _ = stages.assignments(exercise_id, gate)
    sent = _bundle(exercise_id, number)
    every = "".join(sent.files.values())
    for a in rows:
        assert a.application.public_id not in every
        assert a.application.applicant not in every
    reviewees = _rows(sent.files["reviewees"])
    assert {r["RevieweeName"] for r in reviewees} == {handoff.REDACTED}
    assert [r["RevieweeEmail"] for r in reviewees] == [a.application.dossier_id for a in rows]


def test_the_settings_carry_the_gate_s_card() -> None:
    exercise, gate = _gate(EX, 3)
    settings = {r["field"]: r["value"] for r in _rows(_bundle(EX, 3).files["settings"])}
    assert settings["session.description"] == gate.description
    assert settings["session.help_contact"] == sample_data.help_contact(exercise)
    assert settings["session.display_timezone"] == "Asia/Singapore"
    assert settings["session.scheduled_activate_at"].endswith("+08:00")
    assert settings["session.deadline"].endswith("+08:00")
    assert settings["session_tags[1].tag"] == "applydesk"
    assert settings["instruments[1].name"] == gate.label
    for m, f in enumerate(stages.fields_of(gate), start=1):
        at = f"instruments[1].response_fields[{m}]"
        assert settings[f"{at}.field_key"] == f.key
        assert settings[f"{at}.required"] == ("true" if f.required else "false")
    # Never observers, release, rules or layouts.
    assert not any(
        k.startswith(("observers", "rule_sets", "session.responses_release")) for k in settings
    )


def test_a_gate_listing_no_fields_sends_one_per_result() -> None:
    """Codex on #4018: the blind exercise's Gate 1 lists no response
    fields and reads one per result, as Process shows; its instrument
    must carry that Score field, not none."""
    _, gate = _gate("k7mfr3pq8z", 1)
    assert not gate.fields
    sent = _bundle("k7mfr3pq8z", 1)
    settings = {r["field"]: r["value"] for r in _rows(sent.files["settings"])}
    assert settings["instruments[1].response_fields[1].label"] == "Score"
    assert settings["instruments[1].response_fields[1].data_type"] == "Integer"
    assert (
        settings["instruments[1].response_fields[1].min"],
        settings["instruments[1].response_fields[1].max"],
    ) == ("1", "5")
    assert sent.fields == 1


def test_a_tag_never_holds_a_comma() -> None:
    _, gate = _gate(EX, 3)
    rows, _ = stages.assignments(EX, gate)
    pair = stages.Pair(rows[0], "Ann", "ann@example.edu", "Panel, A")
    text = handoff.relationships_csv((pair,), False)
    assert _rows(text)[0]["PairContextTag1.Apply-Desk-Link"] == "Panel A"


def test_the_digest_follows_the_files() -> None:
    sent = _bundle(EX, 3)
    assert sent.digest() == _bundle(EX, 3).digest()
    changed = handoff.Bundle(sent.name, sent.code, {**sent.files, "settings": ""})
    assert changed.digest() != sent.digest()


def test_each_file_downloads_under_its_code(client: TestClient) -> None:
    reply = client.get(f"{BASE}/gate_3/relationships.csv")
    assert reply.status_code == 200
    assert reply.headers["content-type"].startswith("text/csv")
    assert f'filename="{EX}-g3_relationships.csv"' in reply.headers["content-disposition"]
    reviewees = _rows(client.get(f"{BASE}/gate_3/reviewees.csv").text)
    assert reviewees[0]["ProfileLink"].startswith("http://testserver/applydesk/me/exercises/")
    assert client.get(f"{BASE}/gate_3/observers.csv").status_code == 404
    assert client.get(f"{BASE}/gate_9/reviewers.csv").status_code == 404


def test_the_card_counts_and_offers_each_file(client: TestClient) -> None:
    page = client.get(f"{BASE}/gate_3").text
    card = page.split('id="ev-rr"')[1].split("</section>")[0]
    sent = _bundle(EX, 3)
    assert f"{sent.rows('reviewers')} evaluators, by name and email" in card
    assert f"{sent.rows('reviewees')} dossiers, each with its" in card
    assert f"{sent.rows('relationships')} pairs, each tagged" in card
    for kind in handoff.KINDS:
        assert f'href="{BASE}/gate_3/{kind}.csv" download data-rr-file="{kind}"' in card


def test_the_sample_shows_each_later_link_state(client: TestClient) -> None:
    """The second exercise's gates (author, 2026-11-19): one under way,
    one closed in Review Robin but not pulled (ruling 57), one detached."""
    base = "/applydesk/operator/exercises/k7mfr3pq8z/evaluations"
    table = client.get(base).text
    states = re.findall(r"data-gate-state>([^<]+)<", table)
    assert states == ["Sent", "Closed", "Detached"]
    lines = {
        2: "Linked; its session has closed, its results not yet pulled",
        3: "Detached: unlinked in Review Robin, so neither re-sent nor pulled",
    }
    for n, line in lines.items():
        card = client.get(f"{base}/gate_{n}").text.split('id="ev-rr"')[1]
        assert f"<dd data-rr-link>{line}</dd>" in card
    # Both opened: their pairs are Review Robin's, as an open session's.
    assert workflow.gate_opened("Closed", "") and workflow.gate_opened("Detached", "")
    assert workflow.gate_sent("k7mfr3pq8z", "g2")[0] == "Closed"


def test_progress_follows_the_gate_s_line() -> None:
    people = (("Ann", "ann@x", 4), ("Ben", "ben@x", 2))
    assert workflow.progress_of("Sent", "3 of 4 reviewed", people) == (
        ("Ann", "ann@x", 4, 3),
        ("Ben", "ben@x", 2, 2),
    )
    assert [p[3] for p in workflow.progress_of("Closed", "", people)] == [4, 2]
    assert [p[3] for p in workflow.progress_of("Results in", "", people)] == [4, 2]
    assert [p[3] for p in workflow.progress_of("Ready", "", people)] == [0, 0]
    assert [p[3] for p in workflow.progress_of("Sent", "", people)] == [0, 0]


def test_the_card_s_data_links_review_robin_s_me(client: TestClient) -> None:
    page = client.get("/applydesk/operator/exercises/k7mfr3pq8z/evaluations/gate_1").text
    data = page.split('<script type="application/json" id="rr-data">')[1].split("</script>")[0]
    assert '"rrMe": "http://testserver/reviewrobin/me"' in data
    assert '"opened": true' in data and '"state": "Sent"' in data


def test_every_gate_page_has_its_card(client: TestClient) -> None:
    """The plan's Definition of done: the card on every gate page."""
    for exercise in sample_data.EXERCISES:
        if exercise.state == "Draft":
            continue
        for gate in stages.plan_of(exercise.public_id).columns:
            if not isinstance(gate, stages.Gate):
                continue
            path = (
                f"/applydesk/operator/exercises/{exercise.public_id}/evaluations/gate_{gate.number}"
            )
            page = client.get(path).text
            card = page.split('id="ev-rr"')[1].split("</section>")[0]
            for part in (
                "data-rr-name",
                "data-rr-code",
                "data-rr-link",
                "data-rr-last",
                "data-rr-files",
            ):
                assert part in card, (path, part)
            for act in ("send", "resend", "pull", "invite", "remind"):
                assert f'data-rr-act="{act}"' in card, (path, act)


def test_process_shows_a_closed_gate_as_under_way(client: TestClient) -> None:
    page = client.get("/applydesk/operator/exercises/k7mfr3pq8z/process").text
    assert '<span class="chip chip-info" data-pi-state>Closed</span>' in page
    assert '<span class="chip chip-warn" data-pi-state>Detached</span>' in page


def test_the_emails_side_card_lists_only_tags_an_email_takes() -> None:
    """The cold read: a tag no email on the page can take is not offered."""
    owed = workflow.emails("wa9juxbc2t")
    receipt_only = tuple(e for e in owed if e.kind == "receipt")
    rows = workflow.tag_rows(receipt_only)
    assert [r[0] for r in rows] == list(workflow.EMAIL_FIELDS["receipt"])
    assert all(r[2] == ("Receipt",) for r in rows)
    assert {r[0] for r in workflow.tag_rows(owed)} == set(workflow.TAG_HELP)
