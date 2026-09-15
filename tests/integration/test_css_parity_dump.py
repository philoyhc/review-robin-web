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

import json
import os
import pathlib

import pytest
from sqlalchemy import select

from app.db.models import ReviewSession

#: Derived, not hardcoded. A hardcoded list goes stale the moment an
#: eighth template gains a `.filter-row`: the sample would cover 7 of 8
#: and still report "0 differences" with nothing to say otherwise.
_TEMPLATES = pathlib.Path(__file__).resolve().parents[2] / "app/web/templates"


def _pages_carrying_the_strip() -> list[str]:
    return sorted(
        path.stem.removeprefix("session_")
        for path in (_TEMPLATES / "operator").rglob("session_*.html")
        if 'class="filter-row"' in path.read_text(
            encoding="utf-8", errors="replace"
        )
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
    # silently drops them while looking complete — which it did: the
    # first parity run dumped 6 of the 7 pages, and of those only 5
    # actually carried the strip.
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

    pages = _pages_carrying_the_strip()
    assert len(pages) >= 7, f"vacuity: only found {pages}"

    missing, no_strip = [], []
    for page in pages:
        response = client.get(f"{base}/{page}")
        if response.status_code != 200:
            missing.append(f"{page} -> {response.status_code}")
            continue
        (out / f"{page}.html").write_text(response.text, encoding="utf-8")
        # A 200 does not mean the shape was on the page. Several strips
        # are state-gated — Assignments' renders only once assignments
        # exist — so a page can render perfectly and contribute nothing
        # to the comparison. Not an error; recorded so the tool can say
        # which pages it actually covered rather than counting them all.
        if 'class="filter-row"' not in response.text:
            no_strip.append(page)

    assert not missing, (
        "a page that carries the filter strip did not render, so the "
        f"parity sample would be incomplete: {missing}"
    )
    (out / "not-covered.json").write_text(json.dumps(no_strip), "utf-8")
