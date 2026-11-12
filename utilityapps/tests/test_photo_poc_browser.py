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
from PIL import Image, ImageChops, ImageStat
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


def _choose_phone_photo(page: Page) -> None:
    page.goto(PAGE)
    phone: FilePayload = {"name": "phone.jpg", "mimeType": "image/jpeg", "buffer": _phone_photo()}
    page.set_input_files("#photo-file", files=[phone])
    page.wait_for_selector("#photo-save:enabled")


def _save_and_read(client: TestClient, page: Page, count: int) -> Image.Image:
    page.click("#photo-save")
    page.wait_for_function(f"document.querySelectorAll('#photo-tiles li').length === {count}")
    saved = _saved(client, page)
    assert saved.size == (480, 600)
    return saved


def test_a_photo_turned_right_is_saved_as_shown(client: TestClient, page: Page) -> None:
    """Seen blue on the left and red on the right; turned a quarter
    clockwise, blue is on top and red below, and so is the saved photo."""
    _choose_phone_photo(page)
    page.locator("#photo-rotate").fill("88")  # snaps to the waypoint
    assert page.locator("#photo-rotate").input_value() == "90"
    saved = _save_and_read(client, page, 1)
    assert _rgb(saved, 240, 60)[2] > 200 and _rgb(saved, 240, 540)[0] > 200
    page.locator("#photo-rotate").fill("-93")
    assert page.locator("#photo-rotate").input_value() == "-90"
    saved = _save_and_read(client, page, 2)
    assert _rgb(saved, 240, 60)[0] > 200 and _rgb(saved, 240, 540)[2] > 200


# Two touches on the window, as a touch screen sends them: the second
# moves out to twice the spread and turns 30 degrees about the first.
TWO_FINGERS = """([x, y]) => {
  const win = document.getElementById('photo-window');
  const send = (type, id, cx, cy) => win.dispatchEvent(new PointerEvent(type, {
    pointerId: id, pointerType: 'touch', isPrimary: id === 1,
    clientX: cx, clientY: cy, bubbles: true, cancelable: true }));
  send('pointerdown', 1, x - 40, y);
  send('pointerdown', 2, x + 40, y);
  const r = 160, turn = Math.PI / 6;
  for (let i = 1; i <= 5; i++) {
    const f = i / 5, d = 80 + (r - 80) * f, a = turn * f;
    send('pointermove', 2, x - 40 + d * Math.cos(a), y + d * Math.sin(a));
  }
  send('pointerup', 2, 0, 0);
  send('pointerup', 1, 0, 0);
}"""


def test_two_fingers_pinch_to_zoom_and_twist_to_rotate(client: TestClient, page: Page) -> None:
    _choose_phone_photo(page)
    window = page.locator("#photo-window").bounding_box()
    assert window is not None
    middle = [window["x"] + window["width"] / 2, window["y"] + window["height"] / 2]
    page.evaluate(TWO_FINGERS, middle)
    assert float(page.locator("#photo-zoom").input_value()) == pytest.approx(2, abs=0.01)
    assert float(page.locator("#photo-rotate").input_value()) == pytest.approx(30, abs=0.5)
    # The turned, zoomed window is inside the photo as the server checks it.
    _save_and_read(client, page, 1)


@pytest.mark.parametrize("turn", ["17.5", "-63", "90", "135", "180"])
def test_any_turn_at_the_smallest_zoom_is_accepted(
    client: TestClient, page: Page, turn: str
) -> None:
    """At zoom 1 the window's corners touch the photo's edges: the page's
    covering rule and the server's check agree there."""
    _choose_phone_photo(page)
    page.locator("#photo-rotate").fill(turn)
    _save_and_read(client, page, 1)


def _tiles_png() -> bytes:
    """900 by 1200 of distinct tiles, so a shift or a stretch shows."""
    image = Image.new("RGB", (900, 1200))
    for i in range(0, 900, 60):
        for j in range(0, 1200, 60):
            image.paste(((i * 7) % 256, (j * 3) % 256, ((i + j) * 5) % 256), (i, j, i + 60, j + 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("turn", ["23.5", "90", "-90"])
def test_the_saved_photo_is_what_the_window_shows(
    client: TestClient, page: Page, turn: str
) -> None:
    """The cold read: a quarter turn saved a stretched photo, which a
    two-colour test cannot see. A screenshot of the window, against the
    saved photo scaled to it, after a zoom, a turn and a drag."""
    page.goto(PAGE)
    tiles: FilePayload = {"name": "tiles.png", "mimeType": "image/png", "buffer": _tiles_png()}
    page.set_input_files("#photo-file", files=[tiles])
    page.wait_for_selector("#photo-save:enabled")
    page.locator("#photo-zoom").fill("1.6")
    page.locator("#photo-rotate").fill(turn)
    window = page.locator("#photo-window").bounding_box()
    assert window is not None
    page.mouse.move(window["x"] + 100, window["y"] + 100)
    page.mouse.down()
    page.mouse.move(window["x"] + 130, window["y"] + 70, steps=3)
    page.mouse.up()
    shot = Image.open(io.BytesIO(page.locator("#photo-window").screenshot())).convert("RGB")
    saved = _save_and_read(client, page, 1).resize(shot.size)
    diff = ImageStat.Stat(ImageChops.difference(shot, saved)).mean
    assert max(diff) < 8, diff


@pytest.mark.parametrize(
    ("moved_to", "shown"),
    [
        ("4", "0"),
        ("-3.5", "0"),
        ("86", "90"),
        ("94", "90"),
        ("-87", "-90"),
        ("85", "85"),
        ("95", "95"),
        ("45", "45"),
        ("180", "180"),
    ],
)
def test_the_rotate_bar_snaps_to_its_waypoints(page: Page, moved_to: str, shown: str) -> None:
    """Upright and the quarter turns catch the bar within 4 degrees;
    anywhere else it stays where it is put."""
    _choose_phone_photo(page)
    page.locator("#photo-rotate").fill(moved_to)
    assert float(page.locator("#photo-rotate").input_value()) == float(shown)


def test_the_bars_sit_right_of_and_below_the_window(page: Page) -> None:
    _choose_phone_photo(page)
    window = page.locator("#photo-window").bounding_box()
    zoom = page.locator("#photo-zoom").bounding_box()
    rotate = page.locator("#photo-rotate").bounding_box()
    assert window is not None and zoom is not None and rotate is not None
    assert zoom["x"] >= window["x"] + window["width"]  # right of it
    assert zoom["height"] > zoom["width"] * 3  # upright
    assert rotate["y"] >= window["y"] + window["height"]  # below it
    assert rotate["width"] > rotate["height"] * 3  # lying down
    # Zoom in is up: a click near the bar's top sets a high zoom.
    page.mouse.click(zoom["x"] + zoom["width"] / 2, zoom["y"] + 4)
    assert float(page.locator("#photo-zoom").input_value()) > 3.5
