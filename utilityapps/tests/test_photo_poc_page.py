"""The photo proof of concept's page (segment U4, rung 4): the scaffold,
its controls inert and its list on sample tiles, behind the super-admin
gate."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from cordware.settings import identity_settings
from utilityapps.photo_poc.routes import SAMPLE_TILES
from utilityapps.tests._host import host_with

PAGE = "/utilities/photo-poc/"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def test_the_page_shows_the_drop_box_window_zoom_and_save(client: TestClient) -> None:
    page = client.get(PAGE)
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "<h1>Photo proof of concept</h1>" in page.text
    assert "4:5, 480 × 600 px" in page.text
    assert "JPEG, PNG or WebP, 5 MB at most" in page.text
    assert 'accept="image/jpeg,image/png,image/webp"' in page.text
    assert 'id="photo-window" style="--ratio: 4 / 5;"' in page.text


def test_every_control_is_inert(client: TestClient) -> None:
    text = client.get(PAGE).text
    for control in ('id="photo-file"', 'id="photo-zoom"', 'id="photo-save"'):
        tag = text[text.rindex("<", 0, text.index(control)) : text.index(">", text.index(control))]
        assert "disabled" in tag, control
    assert "<script" not in text.split("<main", 1)[-1].split("</main>", 1)[0]


def test_the_list_shows_sample_tiles(client: TestClient) -> None:
    text = client.get(PAGE).text
    assert "Sample tiles" in text
    assert len(re.findall(r'<li class="tile">', text)) == len(SAMPLE_TILES)
    delete = '<button class="btn destructive" type="button" disabled>Delete</button>'
    assert text.count(delete) == len(SAMPLE_TILES)


def test_the_index_does_not_list_it(client: TestClient) -> None:
    assert "/photo-poc/" not in client.get("/utilities/").text


def test_someone_not_super_admin_gets_a_plain_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    page = client.get(PAGE)
    assert page.status_code == 403 and "<h1>Not available</h1>" in page.text


def test_nobody_signed_in_gets_a_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    assert client.get(PAGE).status_code == 401
