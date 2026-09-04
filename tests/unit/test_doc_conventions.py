"""Guard the documentation conventions that only prose enforces.

Same idea as the ``EVENT_SCHEMAS`` strict-mode gate in
``app/services/audit.py``: the rule lives in code, so drift fails a test
rather than waiting for someone to notice it. Added by the 2026-09-04
practice audit (``docs/practice-audit-2026-09-04.md``), which found the
``expired -> "Closed"`` mapping contradicted by three live specs three
months after it landed — drift that survived a deliberate whole-folder
documentation sweep.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.lifecycle_display import DISPLAY_LABELS

REPO = Path(__file__).resolve().parents[2]

# Live prose only — archived docs are a historical record, not a contract.
LIVE_DOCS = sorted(
    p
    for p in list((REPO / "spec").rglob("*.md")) + list((REPO / "docs").rglob("*.md"))
    if "archive" not in p.parts
)

# The pre-19B button vocabulary, superseded by the canonical .btn roles in
# spec/ui_elements.md section 6 (see CLAUDE.md "Project conventions").
RETIRED_TERMS = ("Primary Outline", "Alert Outline", "Danger Outline")
# Deliberate historical references carry this marker on the same line.
TERM_ESCAPE = "<!-- retired-term-ok -->"
# A whole document that is a historical record rather than a live contract
# (a dated audit or assessment snapshot, which quotes the old vocabulary by
# the paragraph) opts out with this marker anywhere in the file.
FILE_ESCAPE = "<!-- retired-term-ok: file -->"

# A `| `enum` | Label |` row in a lifecycle table.
LIFECYCLE_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*\*{0,2}([A-Za-z]+)\*{0,2}\s*\|")


def test_lifecycle_tables_match_the_display_label_mapping() -> None:
    """Every live spec table must agree with ``DISPLAY_LABELS``.

    The expected labels are read from the mapping itself, so this check
    cannot go stale when the mapping changes — it only fails when the
    prose and the code disagree.
    """
    wrong: list[str] = []
    for doc in LIVE_DOCS:
        for number, line in enumerate(doc.read_text().splitlines(), 1):
            match = LIFECYCLE_ROW.match(line)
            if not match:
                continue
            enum, label = match.group(1), match.group(2)
            if enum not in DISPLAY_LABELS:
                continue
            if label != DISPLAY_LABELS[enum]:
                rel = doc.relative_to(REPO)
                wrong.append(
                    f"{rel}:{number}: `{enum}` documented as {label!r}, "
                    f"mapping says {DISPLAY_LABELS[enum]!r}"
                )
    assert not wrong, (
        "lifecycle display-label drift:\n  "
        + "\n  ".join(wrong)
        + "\nDISPLAY_LABELS in app/services/lifecycle_display.py is the source "
        "of truth; correct the prose, not the mapping — unless the mapping "
        "itself is what changed."
    )


def test_retired_button_terminology_is_absent_from_live_docs() -> None:
    """The pre-19B button names must not be prescribed anywhere live.

    A deliberate historical reference ("renamed from X in PR #N") is fine
    — mark that line with ``TERM_ESCAPE``, or the whole document with
    ``FILE_ESCAPE`` when it is a historical record throughout.
    """
    hits: list[str] = []
    for doc in LIVE_DOCS:
        rel = doc.relative_to(REPO)
        text = doc.read_text()
        if FILE_ESCAPE in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if TERM_ESCAPE in line:
                continue
            for term in RETIRED_TERMS:
                if term in line:
                    hits.append(f"{rel}:{number}: {term!r}")
    assert not hits, (
        "retired button terminology (superseded by the canonical .btn roles "
        "in spec/ui_elements.md section 6):\n  "
        + "\n  ".join(hits)
        + f"\nIf a hit is a deliberate historical reference rather than a live "
        f"prescription, mark that line with {TERM_ESCAPE!r} — or, for a document "
        f"that is a historical record throughout, put {FILE_ESCAPE!r} anywhere "
        f"in it. Otherwise use the canonical role name."
    )


def test_agent_instruction_twins_are_identical() -> None:
    """CLAUDE.md and AGENTS.md are byte-identical by convention.

    They carried a note saying no automation enforced it; this is that
    automation. Both files are loaded into every agent session, so a
    divergence means two agents working from different rules.
    """
    claude = (REPO / "CLAUDE.md").read_bytes()
    agents = (REPO / "AGENTS.md").read_bytes()
    assert claude == agents, (
        "CLAUDE.md and AGENTS.md have diverged — copy one over the other "
        "(`cp CLAUDE.md AGENTS.md`) before committing."
    )
