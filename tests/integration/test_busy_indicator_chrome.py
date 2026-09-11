"""The navigation busy indicator ships in the chrome — Segment 19J.4.

``tests/unit/test_busy_indicator.py`` pins the script's four rules at
the source level. These two check the other half: that the markup
actually reaches the browser, on operator and reviewer pages alike,
and that it is inert until a navigation arms it.

Nothing here can click a link — the behaviour itself is verified on the
dev slot, which the item's PR says plainly rather than implying the
suite covers it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_operator_page_carries_the_bar_hidden_and_the_status_region(
    client: TestClient,
) -> None:
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    # Hidden until armed: a page that renders with the bar showing
    # would claim to be loading forever.
    assert (
        '<div class="rrw-busy" data-rrw-busy-bar hidden>'
        '<div class="rrw-busy-fill"></div></div>'
    ) in body
    # The live region is present from first paint — one created and
    # populated in the same tick is not reliably announced.
    assert '<span class="visually-hidden" role="status" data-rrw-busy-status>' in body


def test_the_indicator_reaches_reviewer_facing_pages_too(
    client: TestClient,
) -> None:
    """The reviewer chrome overrides ``top_bar``, not the body — so the
    indicator rides along rather than needing a second copy."""
    response = client.get("/me")
    assert response.status_code == 200
    assert "data-rrw-busy-bar" in response.text
