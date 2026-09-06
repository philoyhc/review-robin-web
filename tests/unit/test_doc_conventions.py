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


# --- Colour tokens: base.html is the source, color_tokens.md the catalogue ---


def _root_blocks() -> tuple[str, str]:
    """The light and dark ``:root`` declaration blocks from ``base.html``.

    Brace-counted rather than regex-sliced: the blocks contain nested
    ``@media`` rules further down the stylesheet, and a lazy match to the
    first ``}`` would stop at the first comment-adjacent brace.
    """
    css = (REPO / "app/web/templates/base.html").read_text()

    def block(selector: str) -> str:
        start = css.index("{", css.index(selector))
        depth = 0
        for i in range(start, len(css)):
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if depth == 0:
                    return css[start:i]
        raise AssertionError(f"unclosed block for {selector}")

    return block(":root {"), block(''':root[data-theme="dark"]''')


def test_every_primitive_is_catalogued_with_its_shipped_value() -> None:
    """``spec/color_tokens.md`` is the palette's catalogue, and a Tier-1
    token that never reaches it is invisible to anyone reading the spec
    rather than the stylesheet. Values are compared too: a hex edited in
    one place and not the other is worse than a missing row, because the
    table still looks authoritative."""
    light, _ = _root_blocks()
    shipped = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})", light))

    # Tier-1 section only, and whole lines. The Tier-2 tables are five
    # columns wide (token | light prim | dark prim | light hex | dark hex),
    # and an unanchored two-column pattern happily matches the middle of
    # one — reading `--violet-soft | #5b21b6` out of the row that maps
    # `--status-super-fg`. That produced 39 phantom mismatches on a
    # correct spec the first time this test ran.
    spec = (REPO / "spec/color_tokens.md").read_text()
    tier1 = spec.split("## Tier 1", 1)[1].split("\n## ", 1)[0]
    catalogue = dict(
        re.findall(
            r"^\|\s*`(--[a-z0-9-]+)`\s*\|\s*`(#[0-9a-fA-F]{3,8})`\s*\|$",
            tier1,
            re.M,
        )
    )

    missing = sorted(n for n in shipped if n not in catalogue)
    assert not missing, f"primitives absent from spec/color_tokens.md: {missing}"

    wrong = sorted(
        f"{n}: base.html {v} vs spec {catalogue[n]}"
        for n, v in shipped.items()
        if catalogue[n].lower() != v.lower()
    )
    assert not wrong, f"catalogued value differs from the shipped one: {wrong}"


def test_the_token_count_line_matches_the_stylesheet() -> None:
    """The headline count in ``spec/color_tokens.md`` drifts silently —
    it read ``103 semantic tokens`` against 107 shipped when this test
    was written (2026-09-06), while every one of the 107 had a correct
    table row. A summary nobody can check is worse than none, so it is
    checked here."""
    light, _ = _root_blocks()
    primitives = len(re.findall(r"--[a-z0-9-]+:\s*#[0-9a-fA-F]{3,8}", light))
    semantic = len(re.findall(r"--[a-z0-9-]+:\s*var\(--[a-z0-9-]+\)", light))

    claim = re.search(
        r"\*\*(\d+) primitives · (\d+) semantic tokens",
        (REPO / "spec/color_tokens.md").read_text(),
    )
    assert claim, "spec/color_tokens.md lost its token-count line"

    assert (int(claim.group(1)), int(claim.group(2))) == (primitives, semantic), (
        f"spec claims {claim.group(1)} primitives / {claim.group(2)} semantic; "
        f"base.html declares {primitives} / {semantic}"
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
