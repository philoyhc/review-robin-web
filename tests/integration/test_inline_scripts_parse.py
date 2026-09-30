"""Every inline `<script>` the app serves is syntactically valid JS.

**Why this exists.** 19P.2 rung 5 shipped a stray `}` into
`session_observers.html` while restructuring a function. The page's
entire JavaScript was dead — no expander, no selection, no delete gate,
nothing — and the whole suite passed: 4,106 tests, `ruff` clean. Python
never parses this code, and the assertions that read it read it as
*text*, so a substring check on a builder is just as happy inside a file
the browser refused.

That is a structural hole, not a one-off slip. `base.html` alone carries
several thousand lines of inline JS and every operator page adds more,
all of it invisible to every other check in the repo.

`node --check` parses without executing, so browser globals and DOM
references are irrelevant — only syntax is in question, which is exactly
what was broken. Skipped where `node` is absent; `ubuntu-latest` has it,
so CI runs it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)

#: Session-scoped pages that carry hand-written JS. `base.html`'s own
#: scripts ride along on every one of them — verified, by breaking a
#: `base.html` script and watching 7 of 8 tests fail.
SESSION_PAGES = (
    "",               # Session Home
    "/reviewers",
    "/reviewees",
    "/relationships",
    "/observers",
    "/instruments",
    "/setup-invite",
    "/assignments",
    "/extract-data",
)

#: Pages outside a session that carry their own scripts. The lobby
#: matters most: `sessions_list.html` is the expander idiom this whole
#: segment copies, so it is the surface most likely to be edited next —
#: and the first draft of this file left it out while claiming "one page
#: per distinct script surface".
STANDALONE_PAGES = (
    "/operator/sessions",
    "/operator/sessions/archived",
    "/operator/sessions/new",
    "/operator/settings",
)

_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)


def _session(client: TestClient, db: Session) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": "JS", "code": "js-parse"},
        follow_redirects=False,
    )
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == "js-parse")
    ).scalar_one()
    s.relationships_enabled = True
    s.observers_enabled = True
    db.commit()
    db.refresh(s)
    return s


def _check(source: str) -> str | None:
    """`None` if it parses, else node's message."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(source)
        path = fh.name
    try:
        result = subprocess.run(
            ["node", "--check", path],
            capture_output=True, text=True, timeout=30,
        )
        return None if result.returncode == 0 else result.stderr.strip()
    finally:
        Path(path).unlink(missing_ok=True)


def _assert_parses(page: str, body: str) -> None:
    blocks = _SCRIPT.findall(body)
    # A page with no inline script would make this vacuous, and the
    # roster pages all have several — so the floor is asserted rather
    # than assumed.
    assert blocks, f"{page}: no inline scripts found; has the shape changed?"

    failures = [
        (i, err)
        for i, block in enumerate(blocks)
        if block.strip() and (err := _check(block)) is not None
    ]
    assert not failures, (
        f"{page}: inline script(s) do not parse — the page's JS is dead "
        f"in a browser and every other test would still pass:\n"
        + "\n\n".join(f"block {i}:\n{err}" for i, err in failures)
    )


@pytest.mark.parametrize("page", SESSION_PAGES)
def test_every_inline_script_on_a_session_page_parses(
    client: TestClient, db: Session, page: str
) -> None:
    review_session = _session(client, db)
    response = client.get(f"/operator/sessions/{review_session.id}{page}")
    assert response.status_code == 200, (page, response.status_code)
    _assert_parses(page, response.text)


@pytest.mark.parametrize("page", STANDALONE_PAGES)
def test_every_inline_script_outside_a_session_parses(
    client: TestClient, db: Session, page: str
) -> None:
    _session(client, db)  # so the lobby has a row to render
    response = client.get(page)
    assert response.status_code == 200, (page, response.status_code)
    _assert_parses(page, response.text)


def test_the_observers_expander_script_is_among_them(
    client: TestClient, db: Session
) -> None:
    """Pins the coverage this was written for. Without it, a refactor
    that moved the expander into a `src=`-loaded file or split the page
    would quietly drop the block that motivated the check."""
    review_session = _session(client, db)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text

    blocks = _SCRIPT.findall(body)
    assert any("observers-row-expander" in b for b in blocks), (
        "the expander builder is not in an inline script any more"
    )


# 19T Item 16 — the one script here that is run, not just parsed: the
# Band 2 preview's copy of ``views.numeric_column_ch_width``, which must
# give the surface's width. It lives in this node-gated module so the
# suite keeps a single tool-gated skip.

_WIDTH_CASES = (
    # (data_type, min, max, label, required)
    ("Integer", 1, 5, "Rating", True),
    ("Integer", -40, 120, "T", False),
    ("Integer", None, None, "Score", False),
    ("Decimal", 0, 2.5, "Hours", False),
    ("Decimal", 0, 12.345678, "S", False),
    ("Decimal", 0, 100000.5, "S", False),
    ("Decimal", 0, 999999.9, "S", False),
    ("Decimal", 0, 1234567, "S", False),
    ("Decimal", 0.00001, 1, "S", False),
    ("Decimal", -0.5, 99999.95, "S", False),
    ("Decimal", 0.0001, 10, "S", False),
)


def test_the_previews_number_width_matches_the_surfaces() -> None:
    import json
    from types import SimpleNamespace

    from app.web.views import numeric_column_ch_width

    template = (
        Path(__file__).resolve().parents[2]
        / "app/web/templates/operator/instruments_index.html"
    ).read_text()
    start = template.index("          function pyG(n) {")
    end = template.index("          // A response column's <col> style", start)
    cases = [
        {"label": label, "required": required,
         "shape": {"dataType": kind.lower(),
                   "min": "" if low is None else str(low),
                   "max": "" if high is None else str(high)}}
        for kind, low, high, label, required in _WIDTH_CASES
    ]
    script = (
        template[start:end]
        + "\nconsole.log(JSON.stringify(" + json.dumps(cases)
        + ".map(function (c) { return numericColumnCh(c.label, c.required, c.shape); })));"
    )
    out = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    ).stdout
    expected = [
        numeric_column_ch_width(
            SimpleNamespace(
                data_type=kind, label=label, required=required,
                validation={"min": low, "max": high},
            )
        )
        for kind, low, high, label, required in _WIDTH_CASES
    ]
    assert json.loads(out) == expected


# 19T Item 17 — the intro's split runs twice: the server estimates it with
# ``views.intro_split_index`` and the browser re-takes it on measured
# heights with ``rrwIntroSplitIndex`` (base.html). Same inputs, same k.

_SPLIT_CASES = (
    # (left_top, right_top, heights)
    (89, 154, [80, 60, 55]),
    (89, 154, []),
    (89, 154, [46]),
    (500, 154, [46, 46]),
    (None, 154, [46, 46]),
    (89, None, [46, 46]),
    (None, None, [46]),
    (100, 100, [50, 50]),
    (60, 150, [200, 30, 30, 30]),
    (65.5, 154.25, [46.5, 70.25, 46.5, 118, 46.5]),
    (None, None, [40, 10, 10, 10]),
    (None, 20, [10, 10, 10]),
    (75, 146, [62, 62]),
    (75, 146, [62, 62]),
    (96, 146, [62, 62]),
    (97, 146, [62, 62]),
    (80, 96, [70, 40, 50]),
    (80, 70, [46]),
)
# The gap each case runs with: most at the surface's 12px; two at 20 and
# 0, where the answer differs from 12's (2 not 1, 3 not 2), so a copy that
# hard-coded one gap would disagree.
_SPLIT_GAPS = (12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 20, 0, 12, 12, 12, 12, 12, 12)
# And the lean: the surface's 24px, except the gap cases (0, so only the
# gap decides) and the author's example run once without it, where the
# answer differs (1 not 2); 96 is the inclusive edge, exactly 24px.
_SPLIT_LEANS = (24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 0, 0, 0, 24, 24, 24, 24, 24)


def test_the_browsers_intro_split_matches_the_servers() -> None:
    import json

    from app.web.views import intro_split_index

    base = (
        Path(__file__).resolve().parents[2] / "app/web/templates/base.html"
    ).read_text()
    start = base.index("      function rrwIntroSplitIndex(")
    end = base.index("      function rrwIntroParts(", start)
    script = (
        base[start:end]
        + "\nconsole.log(JSON.stringify(" + json.dumps(_SPLIT_CASES)
        + ".map(function (c, i) { return rrwIntroSplitIndex(c[0], c[1], c[2], "
        + json.dumps(_SPLIT_GAPS) + "[i], " + json.dumps(_SPLIT_LEANS) + "[i]); })));"
    )
    out = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    ).stdout
    expected = [
        intro_split_index(left, right, list(heights), gap, lean)
        for (left, right, heights), gap, lean in zip(
            _SPLIT_CASES, _SPLIT_GAPS, _SPLIT_LEANS, strict=True
        )
    ]
    assert json.loads(out) == expected

