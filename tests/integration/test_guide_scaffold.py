"""The `/guide` page scaffold — Segment 19E rung 1.

Scaffold-only coverage: the route exists, every section heading the rung
commits to is present, the chrome link behaves like `/about`'s, and the
return-to-origin affordance resolves. Content assertions belong to rung 2,
which moves `docs/quickstart.md` in; this file deliberately asserts
headings rather than prose so it does not have to churn when that lands.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

# The section headings rung 1 commits to. Rung 2 may add sections; it must
# not silently drop one, which is what pinning the list here catches.
SECTIONS = (
    "What Review Robin Web does",
    "Before you start",
    "Create and set up a session",
    "Prepare and launch",
    "Give reviewers access",
    "Watch progress",
    "Close, release, and share results",
    "Tips and troubleshooting",
    "For reviewers",
    "For observers",
    "For reviewees",
    "Getting help",
)


def test_guide_renders(client: TestClient) -> None:
    response = client.get("/guide")
    assert response.status_code == 200
    assert "<h1>Guide</h1>" in response.text


def test_guide_renders_every_committed_section(client: TestClient) -> None:
    body = client.get("/guide").text
    missing = [s for s in SECTIONS if f"<h2>{s}</h2>" not in body]
    assert not missing, f"missing Guide sections: {missing}"


def test_guide_back_link_defaults_to_the_lobby(client: TestClient) -> None:
    body = client.get("/guide").text
    assert 'class="back-link"' in body
    assert 'href="/operator/sessions"' in body
    assert "Back to Sessions" in body


def test_guide_back_link_honours_a_valid_return_to(client: TestClient) -> None:
    body = client.get("/guide?return_to=%2Fme").text
    assert 'href="/me"' in body


def test_guide_back_link_rejects_an_off_allowlist_return_to(
    client: TestClient,
) -> None:
    """Same allowlist `/about` uses — an unknown path falls back, never echoes."""
    body = client.get("/guide?return_to=https%3A%2F%2Fevil.example.edu").text
    assert "evil.example.edu" not in body
    assert 'href="/operator/sessions"' in body


def test_chrome_offers_the_guide_link_from_another_page(client: TestClient) -> None:
    """Jinja's ``urlencode`` leaves ``/`` unescaped, as the existing Settings
    and About links in the same row already do — asserted as rendered, not as
    assumed."""
    body = client.get("/about").text
    assert 'href="/guide?return_to=/about"' in body


def test_chrome_omits_the_guide_link_on_the_guide_itself(client: TestClient) -> None:
    body = client.get("/guide").text
    assert 'class="chrome-link" href="/guide' not in body
    # /about's own link still shows — the two pages are siblings, not one
    # page absorbing the other.
    assert 'class="chrome-link" href="/about' in body
