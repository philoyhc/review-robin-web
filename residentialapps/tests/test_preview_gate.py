"""The preview gate (`residentialapps/web/pages.py`): deployed, the
placeholder screens answer the platform super-admin and the accounts a
preview list names, by mail, sign-in name or address, and 404 everyone
else; locally they answer anyone, and health always answers."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cordware.identity import Identity
from cordware.settings import IdentitySettings
from residentialapps.residentialops.main import create_app as ops_app
from residentialapps.supportlogs.main import create_app as support_app
from residentialapps.web import pages as web_pages

LIST = """# Residential preview

Who may open the placeholder screens. One address per list item.

- `rf.one@example.edu` (RF, Tower A)
* RA.Two@Example.edu
- not an address, a note
- staff.three@example.edu, trailing prose
  - `nested@example.edu`

Prose naming prose@example.edu is not a list item.
"""


@pytest.fixture
def preview_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "residential_preview.md"
    path.write_text(LIST, encoding="utf-8")
    monkeypatch.setattr(web_pages, "PREVIEW_FILE", path)
    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    web_pages.preview_addresses.cache_clear()
    yield path
    web_pages.preview_addresses.cache_clear()


def signed_in(monkeypatch: pytest.MonkeyPatch, identity: Identity | None) -> None:
    monkeypatch.setattr(web_pages, "current_identity", lambda request: identity)


def person(*, mail: str | None = None, upn: str | None = None, email: str | None = None) -> Identity:
    return Identity(
        principal_id="p", email=email or mail or upn, name="Someone", mail=mail, upn=upn,
        resolved_with=IdentitySettings(super_admin_emails=["boss@example.edu"]),
    )


def test_the_list_reads_list_items_whose_first_word_is_an_address(preview_file: Path) -> None:
    assert web_pages.preview_addresses(preview_file) == frozenset(
        {"rf.one@example.edu", "ra.two@example.edu", "staff.three@example.edu", "nested@example.edu"}
    )


def test_no_file_names_nobody(tmp_path: Path) -> None:
    assert web_pages.preview_addresses(tmp_path / "absent.md") == frozenset()


@pytest.mark.parametrize(
    "identity",
    [
        person(mail="rf.one@example.edu"),
        person(mail="RA.two@EXAMPLE.edu"),
        person(upn="nested@example.edu", mail="someone.else@example.edu"),
        person(mail="staff.three@example.edu"),
        person(email="boss@example.edu"),  # the platform super-admin, unlisted
    ],
)
def test_a_previewer_reaches_both_applications(
    preview_file: Path, monkeypatch: pytest.MonkeyPatch, identity: Identity
) -> None:
    signed_in(monkeypatch, identity)
    assert TestClient(ops_app()).get("/").status_code == 200
    assert TestClient(ops_app()).get("/ra-leave/").status_code == 200
    assert TestClient(support_app()).get("/").status_code == 200


@pytest.mark.parametrize(
    "identity",
    [None, person(mail="prose@example.edu"), person(mail="rf.one@example.edu.sg"), person()],
)
def test_anyone_else_gets_404_and_health_still_answers(
    preview_file: Path, monkeypatch: pytest.MonkeyPatch, identity: Identity | None
) -> None:
    signed_in(monkeypatch, identity)
    for app in (ops_app(), support_app()):
        client = TestClient(app)
        assert client.get("/").status_code == 404
        assert client.get("/health").status_code == 200


def test_a_local_run_answers_anyone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_pages, "is_local", lambda: True)
    signed_in(monkeypatch, None)
    assert TestClient(ops_app()).get("/").status_code == 200
    assert TestClient(support_app()).get("/").status_code == 200
