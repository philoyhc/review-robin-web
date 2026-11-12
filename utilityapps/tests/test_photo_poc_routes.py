"""The photo proof of concept's routes (segment U4, rung 5): the page,
saving, reading back and deleting, behind the super-admin gate. The
service's own rules are `test_photo_poc_service.py`'s."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from cordware.settings import identity_settings
from utilityapps.photo_poc.routes import WRITE_HEADER
from utilityapps.tests._host import host_with

PAGE = "/utilities/photo-poc/"
SAVE = "/utilities/photo-poc/photos"
WRITE = {WRITE_HEADER: "1"}
CROP = {"x": "100", "y": "0", "width": "800", "height": "1000"}


@pytest.fixture
def client(utility_db: None) -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def _photo() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1000, 1000), (40, 120, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _save(client: TestClient, data: bytes | None = None, **fields: str) -> dict[str, str]:
    reply = client.post(
        SAVE,
        files={"photo": ("p.jpg", _photo() if data is None else data, "image/jpeg")},
        data={**CROP, **fields},
        headers=WRITE,
    )
    assert reply.status_code == 201, reply.text
    return reply.json()


def test_the_page_offers_the_drop_box_window_zoom_and_save(client: TestClient) -> None:
    page = client.get(PAGE)
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "<h1>Photo proof of concept</h1>" in page.text
    assert "4:5, 480 × 600 px" in page.text
    assert "JPEG, PNG or WebP, 5 MB at most" in page.text
    assert 'id="photo-window" style="--ratio: 4 / 5;"' in page.text
    # A photo is chosen first: zoom and Save wait for one.
    accept = 'accept="image/jpeg,image/png,image/webp">'
    assert f'<input type="file" id="photo-file" {accept}' in page.text
    assert 'value="1" disabled>' in page.text and 'id="photo-save" disabled>' in page.text
    assert '"/utilities/photo-poc/photos"' in page.text  # url(), under the mount
    assert '<p class="note" id="photo-none">No photos saved yet.</p>' in page.text


def test_a_saved_photo_is_listed_and_served_back(client: TestClient) -> None:
    tile = _save(client)
    assert tile["uploaded_by"] == "admin@example.edu"
    assert tile["src"] == f"/utilities/photo-poc/photos/{tile['id']}.jpg"
    page = client.get(PAGE).text
    assert f'data-id="{tile["id"]}"' in page and 'id="photo-none" hidden' in page

    image = client.get(tile["src"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "private, no-store"
    assert Image.open(io.BytesIO(image.content)).size == (480, 600)
    again = client.get(tile["src"], headers={"If-None-Match": image.headers["etag"]})
    assert again.status_code == 304 and again.content == b""


def test_photos_are_listed_newest_first(client: TestClient) -> None:
    first, second = _save(client), _save(client)
    page = client.get(PAGE).text
    assert page.index(f'data-id="{second["id"]}"') < page.index(f'data-id="{first["id"]}"')


@pytest.mark.parametrize(
    ("data", "fields", "status", "message"),
    [
        (b"not a photo", {}, 400, "The file is not a photo this tool can read."),
        (None, {"x": "500"}, 400, "The crop is outside the photo."),
        (None, {"height": "900"}, 400, "The crop is not the window's shape."),
        (None, {"width": "eight"}, 400, "The crop is outside the photo."),
        (b"\xff" * (5 * 1024 * 1024 + 1), {}, 413, "The photo is larger than 5 MB."),
    ],
)
def test_a_refusal_says_why_and_keeps_nothing(
    client: TestClient, data: bytes | None, fields: dict[str, str], status: int, message: str
) -> None:
    reply = client.post(
        SAVE,
        files={"photo": ("p.jpg", _photo() if data is None else data, "image/jpeg")},
        data={**CROP, **fields},
        headers=WRITE,
    )
    assert (reply.status_code, reply.json()) == (status, {"error": message})
    after = client.get(PAGE).text
    assert "No photos saved yet." in after and "data-id=" not in after


def test_no_photo_is_refused(client: TestClient) -> None:
    reply = client.post(SAVE, data=CROP, headers=WRITE)
    assert (reply.status_code, reply.json()) == (400, {"error": "Choose a photo first."})


def test_a_write_without_the_page_s_header_is_refused(client: TestClient) -> None:
    files = {"photo": ("p.jpg", _photo(), "image/jpeg")}
    assert client.post(SAVE, files=files, data=CROP).status_code == 403
    tile = _save(client)
    assert client.delete(f"{SAVE}/{tile['id']}").status_code == 403
    assert client.get(tile["src"]).status_code == 200


def test_a_deleted_photo_is_gone(client: TestClient) -> None:
    tile = _save(client)
    assert client.delete(f"{SAVE}/{tile['id']}", headers=WRITE).status_code == 204
    assert client.get(tile["src"]).status_code == 404
    assert client.delete(f"{SAVE}/{tile['id']}", headers=WRITE).status_code == 404


@pytest.mark.parametrize("name", ["short", "ABCDEFGHJK", "0000000000", "zzzzzzzzzz"])
def test_a_malformed_or_unknown_id_is_a_404(client: TestClient, name: str) -> None:
    assert client.get(f"{SAVE}/{name}.jpg").status_code == 404


def test_someone_not_super_admin_gets_a_403_on_every_route(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    tile = _save(client)
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    page = client.get(PAGE)
    assert page.status_code == 403 and "<h1>Not available</h1>" in page.text
    assert client.get(tile["src"]).status_code == 403
    files = {"photo": ("p.jpg", _photo(), "image/jpeg")}
    assert client.post(SAVE, files=files, data=CROP, headers=WRITE).status_code == 403
    assert client.delete(f"{SAVE}/{tile['id']}", headers=WRITE).status_code == 403


def test_nobody_signed_in_gets_a_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    assert client.get(PAGE).status_code == 401
    assert client.get(f"{SAVE}/2345678923.jpg").status_code == 401


def test_the_index_does_not_list_it(client: TestClient) -> None:
    assert "/photo-poc/" not in client.get("/utilities/").text
