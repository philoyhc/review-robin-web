"""The Guide's screencaps — the app's first static assets.

Every image is referenced by an absolute `/static/guide/...` path in
`guide.html` and served by the single `StaticFiles` mount in `app.main`.
Two ways this breaks silently, both covered here: a `<img>` whose file
was never committed (a 404 the page renders as a broken icon), and a
committed file no template points at (dead weight in the deploy
artefact, which carries `app/` wholesale).

Neither shows up in a page-renders-200 check, which is why this file
exists rather than trusting the markup.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient

STATIC_GUIDE = (
    pathlib.Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "guide"
)
GUIDE_TEMPLATE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "app"
    / "web"
    / "templates"
    / "guide.html"
)
BASE_TEMPLATE = GUIDE_TEMPLATE.with_name("base.html")

REFERENCED = sorted(
    set(re.findall(r'src="/static/guide/([^"]+)"', GUIDE_TEMPLATE.read_text()))
)


def test_the_guide_references_its_screencaps() -> None:
    """Guards the test itself: if the paths are ever templated rather than
    literal, the regex silently finds nothing and every case below passes
    vacuously."""
    assert len(REFERENCED) >= 12


@pytest.mark.parametrize("name", REFERENCED)
def test_every_referenced_screencap_is_served(
    client: TestClient, name: str
) -> None:
    response = client.get(f"/static/guide/{name}")

    assert response.status_code == 200, name
    assert response.headers["content-type"] == "image/png"


def test_no_committed_screencap_is_unreferenced() -> None:
    """The deploy artefact ships `app/` wholesale, so an orphaned capture is
    shipped forever with nothing pointing at it."""
    committed = {p.name for p in STATIC_GUIDE.iterdir() if p.is_file()}

    assert committed == set(REFERENCED)


@pytest.mark.parametrize("name", REFERENCED)
def test_every_screencap_carries_alt_text(name: str) -> None:
    """A screenshot with no alt text is invisible to anyone not looking at
    it, and these carry the page's only account of some UI states."""
    markup = " ".join(GUIDE_TEMPLATE.read_text().split())
    figure = markup.split(f'src="/static/guide/{name}"', 1)[1]
    figure = figure[: figure.index(">")]

    assert 'alt="' in figure, name
    alt = figure.split('alt="', 1)[1].split('"')[0]
    assert len(alt.strip()) > 20, f"{name}: alt text is too thin to be useful"


def test_the_guide_links_the_setup_templates_download(client: TestClient) -> None:
    """The author's draft said the templates "can be downloaded here" with no
    target; the link resolves to the route that serves the zip."""
    body = client.get("/guide").text

    assert 'href="/templates/starter.zip">template CSV files with mock data' in body
    assert client.get("/templates/starter.zip").status_code == 200


# ── Two capture families (2026-09-07) ──────────────────────────────────
#
# The screencaps arrive at two scales: six 1x shots at ~830px and ten 2x
# shots at ~1680px. (Six and six when this was written on 2026-09-07;
# the four `instrument-card-*` captures added the next day are all wide,
# and the sentence went stale until 19H.3's spec pass measured it.)
# Left to fill the prose column they read at two different apparent
# scales, so each family gets a fixed display width — 1200px for the
# wide ten, 600px for the narrow six, which carry
# `.guide-figure-narrow`. Both numbers are the author's, set from the
# rendered page; this file asserts only which family an image is in, not
# the widths themselves, which are presentation and will move again.
#
# The split is by the file's actual pixel width, not by a hand-kept list,
# so a capture retaken at the other scale fails here rather than quietly
# rendering at the wrong size.
NARROW_MAX_WIDTH = 1000


def _png_width(path: pathlib.Path) -> int:
    with path.open("rb") as handle:
        handle.read(16)
        return int.from_bytes(handle.read(4), "big")


@pytest.mark.parametrize("name", REFERENCED)
def test_narrow_captures_carry_the_narrow_figure_class(name: str) -> None:
    markup = " ".join(GUIDE_TEMPLATE.read_text().split())
    figure = markup.rsplit(f'src="/static/guide/{name}"', 1)[0]
    figure = figure[figure.rindex("<figure") :]

    is_narrow = _png_width(STATIC_GUIDE / name) < NARROW_MAX_WIDTH

    assert ("guide-figure-narrow" in figure) is is_narrow, (
        f"{name} is {_png_width(STATIC_GUIDE / name)}px wide; "
        f"{'expected' if is_narrow else 'did not expect'} .guide-figure-narrow"
    )


def test_both_capture_families_are_present() -> None:
    """Guards the rule above: if every capture were re-taken at one scale
    the parametrised test would pass while asserting nothing about the
    split it exists to protect."""
    widths = [_png_width(STATIC_GUIDE / name) for name in REFERENCED]

    assert any(w < NARROW_MAX_WIDTH for w in widths)
    assert any(w >= NARROW_MAX_WIDTH for w in widths)


# ── Light / dark pairs (Segment 19H Item 3) ────────────────────────────
#
# Every capture ships twice: `x.png` and `x-dark.png`, and the figure
# renders both, letting `data-theme` pick one. A capture with no twin
# renders an empty figure in one theme and nothing warns — the page
# still returns 200 and every other check above still passes, because
# each of them asks about one file at a time.
DARK_SUFFIX = "-dark.png"


def _stem(name: str) -> str:
    return name[: -len(DARK_SUFFIX)] if name.endswith(DARK_SUFFIX) else name[: -len(".png")]


def test_every_capture_ships_as_a_light_dark_pair() -> None:
    light = {_stem(n) for n in REFERENCED if not n.endswith(DARK_SUFFIX)}
    dark = {_stem(n) for n in REFERENCED if n.endswith(DARK_SUFFIX)}

    assert light == dark, (
        f"missing dark twin: {sorted(light - dark)}; "
        f"dark with no light original: {sorted(dark - light)}"
    )
    assert light, "no captures found — the naming convention has moved"


@pytest.mark.parametrize("name", [n for n in REFERENCED if not n.endswith(DARK_SUFFIX)])
def test_both_halves_of_a_pair_render_in_the_same_figure(name: str) -> None:
    """The pair is a theme swap, so both copies belong to one <figure> and
    carry the same alt text. Two figures would stack them in a theme that
    ever failed to hide one; two alt texts would describe one picture two
    ways to whoever hears only the visible half."""
    markup = " ".join(GUIDE_TEMPLATE.read_text().split())
    figure = markup.split(f'src="/static/guide/{name}"', 1)[1]
    figure = figure[: figure.index("</figure>")]

    assert f'src="/static/guide/{_stem(name)}{DARK_SUFFIX}"' in figure, name
    light_alt = markup.split(f'src="/static/guide/{name}"', 1)[1]
    light_alt = light_alt[: light_alt.index(">")].split('alt="', 1)[1].split('"')[0]
    dark_alt = markup.split(f'src="/static/guide/{_stem(name)}{DARK_SUFFIX}"', 1)[1]
    dark_alt = dark_alt[: dark_alt.index(">")].split('alt="', 1)[1].split('"')[0]

    assert light_alt == dark_alt, name


@pytest.mark.parametrize("name", [n for n in REFERENCED if not n.endswith(DARK_SUFFIX)])
def test_a_pair_is_shot_at_one_scale(name: str) -> None:
    """The figure's fixed display width is chosen per capture family, so a
    twin shot at the other scale would render at a different apparent size
    depending on the theme. `test_narrow_captures_carry_the_narrow_figure_class`
    checks each file against the markup; this checks the two against each
    other, which is what the markup cannot say."""
    light_narrow = _png_width(STATIC_GUIDE / name) < NARROW_MAX_WIDTH
    dark_narrow = (
        _png_width(STATIC_GUIDE / f"{_stem(name)}{DARK_SUFFIX}") < NARROW_MAX_WIDTH
    )

    assert light_narrow == dark_narrow, name


def test_the_theme_swap_is_keyed_on_the_attribute_not_the_os() -> None:
    """The swap must read `data-theme`, which the toggle writes, and not
    `prefers-color-scheme`, which reads the OS. This app is two-state with
    no OS-follow (`spec/settings_inventory.md`), so a media query here
    would serve light captures to a reader sitting in Dark — the defect
    with extra machinery. Rendering is browser-only; pin the selectors.
    """
    css = " ".join(BASE_TEMPLATE.read_text().split())

    assert '.guide-figure img[data-theme-variant="dark"] { display: none; }' in css
    assert (
        ':root[data-theme="dark"] body.ui-v2 .guide-figure '
        'img[data-theme-variant="light"] { display: none; }'
    ) in css
    assert (
        ':root[data-theme="dark"] body.ui-v2 .guide-figure '
        'img[data-theme-variant="dark"] { display: block; }'
    ) in css
    # And no media query decides any of it. Matched as a media query
    # rather than as a bare mention: two comments in `base.html` name
    # `prefers-color-scheme` precisely to say the app does not use it,
    # and an assertion that fails on prose explaining a rule is an
    # assertion that gets deleted.
    assert not re.search(r"@media[^{]*prefers-color-scheme", css)
