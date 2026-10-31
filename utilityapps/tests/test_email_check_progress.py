"""The check from the page, in batches, counting down (segment U2): the
lookup endpoint, `/check` with the outcomes the page collected, and the
preview's script."""

from __future__ import annotations

import base64
import csv
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cordware.graph import DirectoryUser, GraphError
from cordware.settings import identity_settings
from utilityapps.email_check import check, csvio, routes
from utilityapps.tests._host import host_with

LOOKUP = "/utilities/email-check/lookup"
CHECK = "/utilities/email-check/check"
PREVIEW = "/utilities/email-check/preview"

JANE = DirectoryUser("id-jane", "Jane Tan", "jane.tan@example.edu", "e0123456@example.edu")
LAB = DirectoryUser("id-lab", "Lab", None, "lab01@example.edu")
TABLE: dict[str, list[DirectoryUser] | Exception] = {
    "jane.tan@example.edu": [JANE],
    "e0123456@example.edu": [JANE],
    "lab01@example.edu": [LAB],
}
DATA = (
    b"Name,email\r\n"
    b"Jane,Jane.Tan@example.edu\r\n"
    b"Jane again,e0123456@example.edu\r\n"
    b"Blank,\r\n"
    b"Lab,lab01@example.edu\r\n"
    b"Repeat,jane.tan@example.edu\r\n"
    b"Nobody,nobody@example.edu\r\n"
)


class Recording:
    def __init__(self, table: dict[str, list[DirectoryUser] | Exception]) -> None:
        self.table = table
        self.asked: list[str] = []

    def find_users(self, address: str) -> list[DirectoryUser]:
        self.asked.append(address)
        answer = self.table.get(address, [])
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> Recording:
    recording = Recording(TABLE)
    monkeypatch.setattr(routes, "directory_for", lambda request: recording)
    return recording


def _form(**extra: str) -> dict[str, str]:
    return {"content": base64.b64encode(DATA).decode(), "filename": "list.csv", "column": "1", **extra}


def _keys() -> list[str]:
    return list(csvio.preview(csvio.parse(DATA), 1).keys)


def _lookup(client: TestClient, keys: object, **kwargs):
    return client.post(LOOKUP, content=json.dumps({"keys": keys}), headers={"content-type": "application/json"}, **kwargs)


def _download(page_text: str) -> list[dict[str, str]]:
    encoded = re.search(r'href="data:text/csv;charset=utf-8;base64,([^"]+)"', page_text).group(1)
    text = base64.b64decode(encoded).decode("utf-8").lstrip("﻿")
    return list(csv.DictReader(io.StringIO(text)))


def _collect(client: TestClient) -> dict:
    """What the page's script collects: one key per request."""
    outcomes = {}
    for key in _keys():
        response = _lookup(client, [key])
        assert response.status_code == 200
        outcomes.update(response.json()["outcomes"])
    return outcomes


# --- /lookup ---


def test_lookup_answers_each_key_once(client: TestClient, directory: Recording) -> None:
    response = _lookup(client, ["jane.tan@example.edu", "nobody@example.edu"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    outcomes = response.json()["outcomes"]
    assert outcomes["jane.tan@example.edu"]["status"] == "OK"
    assert outcomes["jane.tan@example.edu"]["user"]["id"] == "id-jane"
    assert outcomes["nobody@example.edu"] == {
        "status": "NOT_FOUND", "match_type": "NONE", "note": "No user-directory match", "error_kind": "", "user": None,
    }
    assert sorted(directory.asked) == ["jane.tan@example.edu", "nobody@example.edu"]


@pytest.mark.parametrize(
    "keys",
    [[], ["a@x.edu"] * (check.BATCH_MAX + 1), ["Jane.Tan@example.edu"], ["not an address"], [3], "a@x.edu"],
)
def test_lookup_refuses_a_batch_that_is_not_lookup_keys(client: TestClient, directory: Recording, keys: object) -> None:
    assert _lookup(client, keys).status_code == 400
    assert directory.asked == []


def test_lookup_takes_json_only(client: TestClient, directory: Recording) -> None:
    form = client.post(LOOKUP, data={"keys": "a@x.edu"})
    assert form.status_code == 415
    big = client.post(LOOKUP, content=b"{" + b" " * (20 * 1024) + b"}", headers={"content-type": "application/json"})
    assert big.status_code == 413
    bad = client.post(LOOKUP, content=b"{", headers={"content-type": "application/json"})
    assert bad.status_code == 400
    assert directory.asked == []


def test_lookup_is_the_super_admins_alone(client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: Recording) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    assert _lookup(client, ["a@x.edu"]).status_code == 403
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    assert _lookup(client, ["a@x.edu"]).status_code == 401
    assert directory.asked == []


def test_lookup_without_a_token_is_a_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_token(request):
        raise GraphError("no_token")

    monkeypatch.setattr(routes, "directory_for", no_token)
    response = _lookup(client, ["a@x.edu"])
    assert response.status_code == 503 and response.json() == {"error": "no_graph"}


# --- /check with the page's outcomes ---


def test_the_page_path_gives_the_same_download_as_the_plain_post(client: TestClient, directory: Recording) -> None:
    plain = client.post(CHECK, data=_form())
    asked_by_plain = len(directory.asked)
    collected = _collect(client)
    directory.asked.clear()
    batched = client.post(CHECK, data=_form(outcomes=json.dumps(collected)))
    assert batched.status_code == 200
    assert directory.asked == []  # nothing looked up twice
    assert _download(batched.text) == _download(plain.text)
    assert asked_by_plain == len(_keys())


def test_keys_the_page_did_not_send_are_error_incomplete(client: TestClient, directory: Recording) -> None:
    collected = _collect(client)
    del collected["nobody@example.edu"]
    rows = _download(client.post(CHECK, data=_form(outcomes=json.dumps(collected))).text)
    nobody = next(r for r in rows if r["Name"] == "Nobody")
    assert nobody["status"] == "ERROR" and nobody["notes"].startswith("Not looked up: the check stopped first")


def test_a_carried_error_with_a_known_kind_is_kept(client: TestClient, directory: Recording) -> None:
    collected = _collect(client)
    collected["nobody@example.edu"] = {
        "status": "ERROR", "match_type": "NONE", "note": "Lookup incomplete (throttled); try again later",
        "error_kind": "throttled", "user": None,
    }
    rows = _download(client.post(CHECK, data=_form(outcomes=json.dumps(collected))).text)
    assert next(r for r in rows if r["Name"] == "Nobody")["status"] == "ERROR"


def test_the_script_holds_back_for_an_unpreviewed_column(client: TestClient) -> None:
    text = client.post(PREVIEW, data=_form()).text
    assert "column.value !== previewed" in text
    assert 'body.error === "no_graph"' in text
    assert "end(stopped)" in text and 'end("")' not in text
    # The column is fixed for the run, and the previewed one is posted (Codex, #3421).
    assert "column.disabled = true" in text
    # Every submit re-enables it: the outcomes post and the no_graph fallback (Codex, #3421).
    assert text.count("column.disabled = false; column.value = previewed;") == 3


def test_a_refused_sign_in_marks_the_rest_with_its_kind(client: TestClient, directory: Recording) -> None:
    collected = {k: v for k, v in _collect(client).items() if k == "jane.tan@example.edu"}
    rows = _download(client.post(CHECK, data=_form(outcomes=json.dumps(collected), stopped="unauthorized")).text)
    assert rows[0]["status"] == "OK"
    lab = next(r for r in rows if r["Name"] == "Lab")
    assert lab["status"] == "ERROR" and "unauthorized" in lab["notes"] and "sign out" in lab["notes"]


@pytest.mark.parametrize(
    "outcomes",
    [
        "[]",
        "{",
        json.dumps({"stranger@example.edu": {"status": "NOT_FOUND", "match_type": "NONE"}}),
        json.dumps({"nobody@example.edu": {"status": "INVALID_INPUT", "match_type": "NONE"}}),
        json.dumps({"nobody@example.edu": {"status": "MADE_UP", "match_type": "NONE"}}),
        json.dumps({"nobody@example.edu": {"status": "OK", "match_type": "PRIMARY_MAIL", "user": None}}),
        json.dumps({"nobody@example.edu": {"status": "NOT_FOUND", "match_type": "NONE", "note": "x" * 600}}),
        json.dumps({"nobody@example.edu": {"status": "ERROR", "match_type": "NONE", "error_kind": "someone@x.edu"}}),
        json.dumps({"nobody@example.edu": {"status": "ERROR", "match_type": "NONE"}}),
        json.dumps({"nobody@example.edu": {"status": "NOT_FOUND", "match_type": "NONE", "error_kind": "timeout"}}),
    ],
)
def test_outcomes_that_do_not_fit_the_file_are_refused(client: TestClient, directory: Recording, outcomes: str) -> None:
    page = client.post(CHECK, data=_form(outcomes=outcomes))
    assert page.status_code == 400
    assert "could not be read" in page.text
    assert directory.asked == []


# --- the preview's script ---


def test_the_preview_carries_the_keys_and_the_script(client: TestClient) -> None:
    text = client.post(PREVIEW, data=_form()).text
    assert re.search(r'id="to-check">4<', text)
    keys = json.loads(re.search(r'<script type="application/json" id="check-keys">(.*?)</script>', text, re.S).group(1))
    assert keys == _keys()
    assert '"/utilities/email-check/lookup"' in text
    assert 'name="outcomes" id="check-outcomes" disabled' in text


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_preview_script_parses(client: TestClient) -> None:
    text = client.post(PREVIEW, data=_form()).text
    scripts = re.findall(r"<script>(.*?)</script>", text, re.S)
    assert scripts
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "preview.js"
        path.write_text("\n".join(scripts))
        result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
