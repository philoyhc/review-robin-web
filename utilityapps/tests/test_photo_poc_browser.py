"""The photo proof of concept in a real Chromium (segment U4, rung 5):
drop a rotated phone photo, zoom and drag it in the window, save, and read
the saved photo back upright. Pages, saves, reads and deletes go through a
``TestClient`` behind a routed origin, as Residential's browser tests do.
Without a Chromium build the test skips, saying why; ``RRW_REQUIRE_BROWSER=1``
(set by CI) turns that skip into a failure."""

from __future__ import annotations

import io
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from playwright.sync_api import Error, FilePayload, Page, Route, sync_playwright

from utilityapps.tests._host import host_with

ORIGIN = "http://utilities.test"
PAGE = f"{ORIGIN}/utilities/photo-poc/"


@pytest.fixture
def client(utility_db: None) -> TestClient:
    return TestClient(host_with(("utilities",))[0])


@pytest.fixture
def page(client: TestClient) -> Iterator[Page]:
    def serve(route: Route) -> None:
        request = route.request
        response = client.request(
            request.method,
            request.url.removeprefix(ORIGIN),
            content=request.post_data_buffer,
            headers=request.headers,
        )
        route.fulfill(
            status=response.status_code, body=response.content, headers=dict(response.headers)
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as exc:
            reason = f"Chromium could not launch: {exc.message.splitlines()[0]}"
            if os.environ.get("RRW_REQUIRE_BROWSER") == "1":
                pytest.fail(f"{reason}, and RRW_REQUIRE_BROWSER=1", pytrace=False)
            pytest.skip(reason)
        tab = browser.new_page(viewport={"width": 1000, "height": 900})
        errors: list[str] = []
        tab.on("pageerror", lambda exc: errors.append(str(exc)))
        tab.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def _phone_photo() -> bytes:
    """Stored 1000 wide by 800 high with EXIF orientation 6: seen 800 by
    1000, the stored top half (red) on the seen right."""
    stored = Image.new("RGB", (1000, 800), (0, 0, 255))
    stored.paste((255, 0, 0), (0, 0, 1000, 400))
    exif = Image.Exif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    stored.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _saved(client: TestClient, page: Page) -> Image.Image:
    src = page.locator("#photo-tiles img").first.get_attribute("src")
    assert src is not None
    reply = client.get(src)
    assert reply.status_code == 200
    return Image.open(io.BytesIO(reply.content)).convert("RGB")


def _rgb(image: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    pixel = image.getpixel((x, y))
    assert isinstance(pixel, tuple)
    return pixel[0], pixel[1], pixel[2]


def test_a_photo_is_framed_saved_read_back_and_deleted(client: TestClient, page: Page) -> None:
    page.goto(PAGE)
    phone: FilePayload = {"name": "phone.jpg", "mimeType": "image/jpeg", "buffer": _phone_photo()}
    page.set_input_files("#photo-file", files=[phone])
    page.wait_for_selector("#photo-save:enabled")

    # At zoom 1 the oriented photo fills the window exactly: all of it is kept.
    page.click("#photo-save")
    page.wait_for_selector("#photo-tiles li")
    whole = _saved(client, page)
    assert whole.size == (480, 600)
    assert _rgb(whole, 60, 300)[2] > 200 and _rgb(whole, 420, 300)[0] > 200  # blue | red

    # Zoom in and drag the photo left as far as it goes: the window shows
    # the seen right edge, the red half.
    page.locator("#photo-zoom").fill("2")
    window = page.locator("#photo-window").bounding_box()
    assert window is not None
    middle = (window["x"] + window["width"] / 2, window["y"] + window["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.mouse.move(middle[0] - 2 * window["width"], middle[1], steps=5)
    page.mouse.up()
    page.click("#photo-save")
    page.wait_for_function("document.querySelectorAll('#photo-tiles li').length === 2")
    right = _saved(client, page)
    assert right.size == (480, 600)
    assert all(_rgb(right, x, 300)[0] > 200 for x in (20, 240, 460))

    page.on("dialog", lambda dialog: dialog.accept())
    page.locator("#photo-tiles [data-delete]").first.click()
    page.wait_for_function("document.querySelectorAll('#photo-tiles li').length === 1")
    page.reload()
    assert page.locator("#photo-tiles li").count() == 1


def test_an_over_size_or_wrong_file_is_refused_in_the_browser(page: Page) -> None:
    page.goto(PAGE)
    page.set_input_files(
        "#photo-file", files=[{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"hello"}]
    )
    assert page.locator("#photo-message").text_content() == "Choose a JPEG, PNG or WebP photo."
    big = b"\xff\xd8" + b"\0" * (5 * 1024 * 1024)
    page.set_input_files(
        "#photo-file", files=[{"name": "big.jpg", "mimeType": "image/jpeg", "buffer": big}]
    )
    assert page.locator("#photo-message").text_content() == "The photo is larger than 5 MB."
    assert page.locator("#photo-save").is_disabled()
