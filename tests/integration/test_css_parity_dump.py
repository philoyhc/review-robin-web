"""Render every page carrying the filter strip, for `tools/css_parity_check.py`.

Skipped unless `RRW_PARITY_DUMP` names a directory. It is a test only so
that it can use the real fixtures — the pages it writes are the actual
template output against a seeded session, which is the whole point: a
hand-built approximation would not prove anything about the app.

See the tool's docstring for why this exists. Short version: the suite
has no layout engine, so which CSS rule *wins* on which element is
invisible to it, and 19P lost two declarations that way.
"""
from __future__ import annotations

import os
import pathlib

import pytest
from sqlalchemy import select

from app.db.models import ReviewSession

#: Every page that renders a `.filter-row`.
PAGES = (
    "reviewers", "reviewees", "relationships", "observers",
    "assignments", "invitations", "responses",
)

_ROWS = b"".join(f"P{n},p{n}@example.com\n".encode() for n in range(1, 4))


@pytest.mark.skipif(
    not os.environ.get("RRW_PARITY_DUMP"),
    reason="set RRW_PARITY_DUMP=<dir> to dump pages for a CSS parity check",
)
def test_dump_filter_strip_pages(client, db) -> None:
    out = pathlib.Path(os.environ["RRW_PARITY_DUMP"])
    out.mkdir(parents=True, exist_ok=True)

    client.post("/operator/sessions",
                data={"name": "Parity", "code": "parity"},
                follow_redirects=False)
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "parity")
    ).scalar_one()

    # Relationships and Observers are route-gated on their per-session
    # toggles and 404 until those are on. Miss this and the sample
    # silently covers five of seven pages while looking complete.
    for flag in ("relationships_enabled", "observers_enabled"):
        assert hasattr(review_session, flag), f"no {flag} on ReviewSession"
        setattr(review_session, flag, True)
    db.commit()

    base = f"/operator/sessions/{review_session.id}"
    for role, header in (("reviewers", b"ReviewerName,ReviewerEmail\n"),
                         ("reviewees", b"RevieweeName,RevieweeEmail\n")):
        client.post(f"{base}/{role}/import",
                    files={"file": ("r.csv", header + _ROWS, "text/csv")},
                    follow_redirects=False)

    missing = []
    for page in PAGES:
        response = client.get(f"{base}/{page}")
        if response.status_code == 200:
            (out / f"{page}.html").write_text(response.text, encoding="utf-8")
        else:
            missing.append(f"{page} -> {response.status_code}")
    assert not missing, (
        "a page that carries the filter strip did not render, so the "
        f"parity sample would be incomplete: {missing}"
    )
