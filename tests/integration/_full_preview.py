"""Helper for fetching the operator-side full reviewer-surface
preview body.

Through Segment 11F PR C the operator preview lived inside an
iframe srcdoc on the Previews hub; this helper used to extract that
srcdoc and HTML-unescape it. In the Segment 18Q follow-on the
iframe-embedded surface card was retired in favor of a dedicated
operator-side preview route (`_preview_surface.py`), so the helper
now just GETs that route directly and returns the response body.

Tests that previously asserted against ``get_surface_preview_html``
(its pre-retirement name) hit the same surface template — modulo the
inert action row + real assignments + ``accepting=True`` forcing that
the new full-preview path applies — and most assertions carry over.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient


def get_full_preview_html(
    client: TestClient, session_id: int, reviewer_email: str
) -> str:
    """Fetch the operator-side full reviewer-surface preview body
    for ``session_id`` with the given ``reviewer_email`` selected and
    return the rendered HTML.
    """
    response = client.get(
        f"/operator/sessions/{session_id}/preview-surface/1"
        f"?reviewer_email={quote(reviewer_email)}"
    )
    assert response.status_code == 200, response.text
    return response.text
