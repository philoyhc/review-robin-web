"""The bundle a gate would be sent to Review Robin with (segment AD1M
rung 3, `applydesk/handoff.py`). Review Robin's own handoff route takes
these files in `tests/integration/test_handoffs.py`
(`test_an_apply_desk_gate_s_bundle_arrives_set_up`)."""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from applydesk import handoff, sample_data, stages
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
