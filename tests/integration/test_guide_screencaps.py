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
# The screencaps arrive at two scales: six 1x shots at ~830px and six 2x
# shots at ~1680px. Left to fill the prose column they read at two
# different apparent scales, so each family gets a fixed display width —
# 1200px for the wide six, 600px for the narrow six, which carry
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
