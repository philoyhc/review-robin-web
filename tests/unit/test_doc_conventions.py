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
from app.services.visibility_policies import (
    MODE_LABELS,
    _PER_CELL_VALID_MODES,
)

REPO = Path(__file__).resolve().parents[2]

# Live prose only — archived docs are a historical record, not a contract.
LIVE_DOCS = sorted(
    p
    for p in list((REPO / "spec").rglob("*.md")) + list((REPO / "docs").rglob("*.md"))
    if "archive" not in p.parts
)

# Retired user-facing vocabulary that no code constant derives, so nothing
# else can catch it going stale. Two groups:
#   - the pre-19B button names, superseded by the canonical .btn roles in
#     spec/ui_elements.md section 6 (see CLAUDE.md "Project conventions");
#   - "Search card", the Sessions lobby's filter card before 19O Item 7
#     entry 15 renamed it. The control is a client-side filter and never
#     was a search; the rename swept the templates and one spec and left
#     two others behind, which is entry 16. Note the term is the *card*,
#     not the word: seven operator tables still carry a real `Search:`
#     input and a `Search` submit button, and those are correct.
RETIRED_TERMS = (
    "Primary Outline",
    "Alert Outline",
    "Danger Outline",
    "Search card",
)
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
    """Retired user-facing names must not be prescribed anywhere live.

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
        "retired user-facing terminology (the .btn roles are canonical in "
        "spec/ui_elements.md section 6; see RETIRED_TERMS for the rest):\n  "
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



# --- Visibility grid: the constant is the source, spec 3.1 the transcript ---
#
# Segment 19G Item 1, class A. `spec/visibility_policy.md` 3.1 transcribes
# `_PER_CELL_VALID_MODES` into a table, and on 2026-09-08 the Reviewee row
# had said "All three are valid" — the opposite of the rule — for long
# enough to survive a whole-folder sweep. A constant exists, so Article II
# says derive it rather than watch it.
#
# Everything below is read from the constant: the audiences and windows
# from its keys, the mode vocabulary from MODE_LABELS. The only things
# hardcoded are where the table lives and how a markdown row is shaped.

VISIBILITY_SPEC = REPO / "spec" / "visibility_policy.md"

#: The heading whose table transcribes the constant.
GRID_HEADING = "### 3.1 Per-cell valid modes"

#: `None` is spelled out in prose; the three real modes come from the
#: label map, so a fourth mode added there fails here until documented.
GRID_VOCABULARY = frozenset(MODE_LABELS) | {"None"}


def _grid_rows() -> list[list[str]]:
    """The cells of 3.1's table: the header row first, then one row per
    audience. Empty when the table is not where or how it is expected."""
    lines = VISIBILITY_SPEC.read_text().splitlines()
    try:
        start = lines.index(GRID_HEADING)
    except ValueError:
        return []
    rows: list[list[str]] = []
    for line in lines[start + 1 :]:
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):  # the |---|---| separator
            continue
        rows.append(cells)
    return rows


def _documented_grid() -> dict[tuple[str, str], frozenset[str | None]]:
    """3.1's table as a grid, keyed like the constant.

    Windows come from the header rather than from column order, so a
    swapped pair of columns reads as swapped values rather than passing.
    Each cell's modes are its backticked tokens filtered to the
    vocabulary, which is what lets the cells carry prose as well.
    """
    rows = _grid_rows()
    if len(rows) < 2:
        return {}
    windows = [w.strip("`*") for w in rows[0][1:]]
    grid: dict[tuple[str, str], frozenset[str | None]] = {}
    for cells in rows[1:]:
        audience = cells[0].strip("`*")
        for window, cell in zip(windows, cells[1:]):
            modes = {t for t in re.findall(r"`([A-Za-z_]+)`", cell) if t in GRID_VOCABULARY}
            grid[(audience, window)] = frozenset(
                None if m == "None" else m for m in modes
            )
    return grid


def test_the_visibility_grid_table_is_still_a_grid() -> None:
    """Parseability first, and separately, so a restructured table says
    "the table moved" rather than "every cell drifted" — the difference
    between a message that points at the edit and one that buries it.
    """
    documented = _documented_grid()
    expected = set(_PER_CELL_VALID_MODES)
    assert documented, (
        f"{GRID_HEADING!r} in spec/visibility_policy.md no longer yields a "
        "table of `audience` rows against `window` columns. It transcribes "
        "_PER_CELL_VALID_MODES in app/services/visibility_policies.py; keep "
        "the shape or update this parser alongside the rewrite."
    )
    assert set(documented) == expected, (
        "the grid's cells do not match the constant's:\n"
        f"  documented only: {sorted(map(str, set(documented) - expected))}\n"
        f"  constant only:   {sorted(map(str, expected - set(documented)))}"
    )


def test_every_documented_cell_matches_the_constant() -> None:
    """The failure this exists for: a cell stating the opposite of the
    rule it documents, in a table that reads perfectly well."""
    documented = _documented_grid()
    wrong = [
        f"  ({audience}, {window}): documented "
        f"{sorted(str(m) for m in documented[(audience, window)])}, "
        f"constant says {sorted(str(m) for m in modes)}"
        for (audience, window), modes in sorted(_PER_CELL_VALID_MODES.items())
        if documented.get((audience, window)) != modes
    ]
    assert not wrong, (
        "spec/visibility_policy.md 3.1 disagrees with "
        "_PER_CELL_VALID_MODES:\n"
        + "\n".join(wrong)
        + "\nThe constant in app/services/visibility_policies.py is the "
        "source — both writers read it. Correct the table, unless the "
        "constant itself is what changed."
    )


def test_every_semantic_token_is_catalogued_with_its_shipped_mapping() -> None:
    """The Tier-2 half of the catalogue, which nothing checked until 19K.7.

    ``test_every_primitive_is_catalogued_with_its_shipped_value`` covers
    Tier 1 and caught `--slate` moving. Tier 2 had no equivalent, so four
    rows survived a repoint with their old primitives and hex intact —
    `--lifecycle-ready-fg` still reading `--green-strong` / `#059669`
    after it shipped as `--green-deep` / `#166534`. A reader designing
    from the catalogue would have designed against values that had not
    shipped for a day, and the table would have looked authoritative
    while doing it.

    Rows are matched whole, for the reason the Tier-1 test records: an
    unanchored pattern reads the middle of a five-column row as if it
    were a two-column one.
    """
    light, dark = _root_blocks()
    prims = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})", light))
    sem_light = dict(re.findall(r"(--[a-z0-9-]+):\s*var\((--[a-z0-9-]+)\)", light))
    sem_dark = {**sem_light, **dict(re.findall(r"(--[a-z0-9-]+):\s*var\((--[a-z0-9-]+)\)", dark))}

    spec = (REPO / "spec/color_tokens.md").read_text()
    rows = re.findall(
        r"^\|\s*`(--[a-z0-9-]+)`\s*\|\s*`(--[a-z0-9-]+)`\s*\|\s*`(--[a-z0-9-]+)`\s*"
        r"\|\s*`(#[0-9a-fA-F]{3,8})`\s*\|\s*`(#[0-9a-fA-F]{3,8})`\s*\|$",
        spec,
        re.M,
    )
    # A floor, because a pattern that matches nothing makes every claim
    # below vacuously true. The catalogue carried 95 five-column rows
    # when this was written.
    assert len(rows) >= 90, f"only {len(rows)} Tier-2 rows parsed from the catalogue"

    wrong = []
    for token, lp, dp, lhex, dhex in rows:
        for theme, prim, hexv, mapping in (
            ("light", lp, lhex, sem_light),
            ("dark", dp, dhex, sem_dark),
        ):
            shipped_prim = mapping.get(token)
            if shipped_prim is None:
                continue  # retirements are covered by the path/term checks
            if shipped_prim != prim:
                wrong.append(f"{token} ({theme}): base.html {shipped_prim} vs spec {prim}")
            elif prims.get(shipped_prim, "").lower() != hexv.lower():
                wrong.append(
                    f"{token} ({theme}): {shipped_prim} is "
                    f"{prims.get(shipped_prim)} vs spec {hexv}"
                )

    assert not wrong, "catalogued Tier-2 mapping differs from the shipped one:\n  " + "\n  ".join(wrong)
