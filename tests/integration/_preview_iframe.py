"""Helpers for asserting against the segment 11F PR C iframe surface.

Segment 11F PR C retired the standalone ``/preview`` route in favor
of an iframe-embedded surface card on the previews hub. The iframe's
``srcdoc`` attribute carries the HTML-attribute-encoded reviewer-
surface page, so raw substring assertions on the outer body would
miss most of the rendered HTML. Tests that previously asserted
against the rendered surface body now go through
:func:`get_surface_preview_html` to fetch the previews page and
return the unescaped iframe inner HTML.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote

from fastapi.testclient import TestClient


def get_surface_preview_html(
    client: TestClient, session_id: int, reviewer_email: str
) -> str:
    """Fetch the previews page for ``session_id`` with
    ``?reviewer_email=`` and return the unescaped iframe srcdoc body.

    The browser would parse this same HTML when rendering the
    iframe; tests assert against it as if it were the response
    body of the retired ``/preview`` route.
    """
    response = client.get(
        f"/operator/sessions/{session_id}/previews"
        f"?reviewer_email={quote(reviewer_email)}"
    )
    assert response.status_code == 200, response.text
    match = re.search(
        r'<iframe[^>]*\bclass="surface-preview-iframe"[^>]*\bsrcdoc="([^"]*)"',
        response.text,
    )
    assert match is not None, "surface preview iframe not found in body"
    return html.unescape(match.group(1))
