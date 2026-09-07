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
