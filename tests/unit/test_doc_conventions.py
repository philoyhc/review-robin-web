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


# --- Path references: a backticked repo path in live prose must resolve ---
#
# Segment 19G Item 1, class E. The filesystem and git history are the
# constants, so this needs no registry of its own and cannot go stale
# independently of the tree it reads (constitution.md Article II).
#
# Its own corpus rather than LIVE_DOCS above, for two reasons: it reaches
# `guide/` and the root-level documents (`constitution.md`,
# `rrw_sdd_in_practice.md`, `CLAUDE.md`) that nothing else checks, and it
# excludes dated records by filename rather than by an in-file marker,
# because a plan or a snapshot names files that did not exist on its date
# or do not exist yet, and both are correct.

#: A document whose *filename* marks it as a record of a date rather than
#: a live claim: a snapshot, a sweep, a practice audit, a segment plan.
#: Excluded wholesale — a reference that was right when it was written is
#: not a defect now, and a plan legitimately names files not yet built.
DATED_DOC = re.compile(r"(codebase_assessment_|sweep_|practice-audit-|segment_)")

#: Live prose: top-level `.md` in the three doc folders plus the root.
#: `archive/` is excluded by not recursing; there are no other nested
#: documentation directories (checked 2026-09-08).
LIVE_PROSE = sorted(
    p
    for d in (REPO, REPO / "spec", REPO / "docs", REPO / "guide")
    for p in d.glob("*.md")
    if not DATED_DOC.search(p.name)
)

#: A backticked repo-relative path. Anchored on a known top-level
#: directory: a bare `` `architecture.md` `` is shorthand whose directory
#: the reader supplies, and resolving those would need a guess per hit —
#: the kind of growing ambiguity Article VI says not to mechanise.
PATH_REF = re.compile(r"`((?:spec|docs|guide|app|tests|tools)/[A-Za-z0-9_./-]+)`")

#: One line's reference is deliberate: a forward reference to something
#: planned, or a historical statement ("retired X", "formerly X").
PATH_ESCAPE = "<!-- path-ref-ok -->"

#: A whole `##` section is a dated register inside an otherwise-live file
#: — `docs/status.md`'s timeline, `guide/todo_master.md`'s Done. Placed on
#: the first non-blank line under the heading, and covers to the next
#: `##`. Section rather than file, so the live half of those documents
#: stays checked; section rather than 36 inline markers, so it is not noise.
PATH_SECTION_ESCAPE = "<!-- path-ref-ok: section -->"


def _dated_register_lines(lines: list[str]) -> set[int]:
    """1-based line numbers inside a section that has opted out.

    The marker is only honoured as the first non-blank line under a `##`
    heading. Anywhere else it is ignored, so a marker cannot be dropped
    mid-section to silence one inconvenient line.
    """
    opted: set[int] = set()
    heading: int | None = None
    seen_body = False
    covering = False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            heading, seen_body, covering = number, False, False
            continue
        if heading is not None and not seen_body and line.strip():
            seen_body = True
            covering = line.strip() == PATH_SECTION_ESCAPE
        if covering:
            opted.add(number)
    return opted


def _unresolved_path_refs() -> list[tuple[str, int, str, str]]:
    """Every non-resolving path reference in live prose, with how it is
    covered: ``""`` (not covered), ``"inline"`` or ``"section"``."""
    found: list[tuple[str, int, str, str]] = []
    for doc in LIVE_PROSE:
        rel = str(doc.relative_to(REPO))
        lines = doc.read_text().splitlines()
        opted = _dated_register_lines(lines)
        for number, line in enumerate(lines, 1):
            for match in PATH_REF.finditer(line):
                target = match.group(1)
                if (REPO / target).exists():
                    continue
                cover = (
                    "inline"
                    if PATH_ESCAPE in line
                    else "section"
                    if number in opted
                    else ""
                )
                found.append((rel, number, target, cover))
    return found


def test_every_path_reference_in_live_prose_resolves() -> None:
    """A pointer a reader is meant to follow must lead somewhere.

    84 of these were live at `5ab5e2f8`, the oldest four months old and
    every one found by hand — including five references to a document
    that a documentation *sweep* had retired while running.
    """
    dangling = [
        f"{rel}:{number}: `{target}`"
        for rel, number, target, cover in _unresolved_path_refs()
        if not cover
    ]
    assert not dangling, (
        "path references naming nothing:\n  "
        + "\n  ".join(dangling)
        + "\nRepoint it if it is a pointer a reader follows ('Plan: X', "
        f"'spec: X'). If it is a record of what was true on its date "
        f"('retired X', 'formerly X', 'split X into a package'), or a "
        f"forward reference to something planned, leave the words alone "
        f"and mark the line with {PATH_ESCAPE!r} — repointing a log "
        f"falsifies it."
    )


def test_no_inline_path_marker_outlives_the_reference_it_covers() -> None:
    """A marker whose reference now resolves is stale in the same way a
    dangling reference is, and this is the direction nobody would notice:
    the suite stays green while the escape quietly covers nothing. Same
    both-directions rule as ``test_spec_coverage.py``'s registry.

    Section markers are deliberately exempt: they describe what a section
    *is*, so one covering no broken reference today is still correct.
    """
    covered = {(rel, number) for rel, number, _, c in _unresolved_path_refs() if c == "inline"}
    stale = [
        f"{doc.relative_to(REPO)}:{number}"
        for doc in LIVE_PROSE
        for number, line in enumerate(doc.read_text().splitlines(), 1)
        if PATH_ESCAPE in line and (str(doc.relative_to(REPO)), number) not in covered
    ]
    assert not stale, (
        f"{PATH_ESCAPE!r} on a line whose path references all resolve:\n  "
        + "\n  ".join(stale)
        + "\nThe marker has outlived its reason — drop it."
    )


# --- Section references: `§N` must name a section the target carries ---

#: A `§N` pointer into another document's numbered sections. The
#: whitespace before `§` may include a **newline**: 7 of the 132 live
#: references wrap, and a line-local scan misses every one of them —
#: which is how the 19G.5 measurement came to certify 125 of 132 clean
#: and leave a broken reference standing in `docs/unenforced_conventions.md`.
SECTION_REF = re.compile(
    r"`((?:spec|docs|guide|app|tests|tools)/[A-Za-z0-9_./-]+\.md)`"
    r"\s*§\s*([0-9]+(?:\.[0-9]+)*[a-z]?)"
)

#: The four ways a live document numbers a section, measured over the 26
#: files these references point into (2026-09-08): 123 plain `## 3. X`
#: or `### 1.1 X`, 3 bold-paragraph `**8.2.7 X**`, 3 `## §5.6 X`, and one
#: `## Section 10 — X`. All four are load-bearing; a fifth form would be
#: dead code, which is the line `constitution.md` Article VI draws.
SECTION_HEADINGS = (
    re.compile(r"^#{1,6}\s+([0-9]+(?:\.[0-9]+)*[a-z]?)\.?\s"),
    re.compile(r"^#{1,6}\s+Section\s+([0-9]+(?:\.[0-9]+)*[a-z]?)\b"),
    re.compile(r"^#{1,6}\s+§\s*([0-9]+(?:\.[0-9]+)*[a-z]?)\b"),
    re.compile(r"^\*\*§?\s*([0-9]+(?:\.[0-9]+)*[a-z]?)[.\s]"),
)

#: Inline only, and **deliberately without a section-scoped twin**. The
#: path check needs one because 36 of its references sit in dated
#: registers; here the section form would excuse 31 of 132 references to
#: cover the single historical citation that needs it — 30 working
#: pointers going unchecked to save one marker. An escape hatch is sized
#: to what it must excuse.
SECTION_ESCAPE = "<!-- section-ref-ok -->"


def _numbered_sections(doc: Path) -> set[str]:
    """Every section number `doc` carries, in any of the four forms."""
    numbers: set[str] = set()
    for line in doc.read_text().splitlines():
        for form in SECTION_HEADINGS:
            match = form.match(line)
            if match:
                numbers.add(match.group(1))
                break
    return numbers


def _unresolved_section_refs() -> list[tuple[str, int, str, str, bool]]:
    """Every `§N` naming a section its target does not carry.

    Returns `(file, line, target, number, marked)`. The scan is over the
    whole text rather than line by line, so a wrapped reference is seen;
    the line reported is where the reference *starts*, and the marker is
    honoured on any line it spans.
    """
    found: list[tuple[str, int, str, str, bool]] = []
    catalogue: dict[str, set[str]] = {}
    for doc in LIVE_PROSE:
        rel = str(doc.relative_to(REPO))
        text = doc.read_text()
        lines = text.splitlines()
        for match in SECTION_REF.finditer(text):
            target, number = match.group(1), match.group(2)
            if not (REPO / target).is_file():
                continue  # the path check owns a target that does not exist
            if target not in catalogue:
                catalogue[target] = _numbered_sections(REPO / target)
            if number in catalogue[target]:
                continue
            start = text[: match.start()].count("\n") + 1
            spanned = lines[start - 1 : start + match.group(0).count("\n")]
            found.append(
                (rel, start, target, number, any(SECTION_ESCAPE in ln for ln in spanned))
            )
    return found


def test_every_section_reference_names_a_section_that_exists() -> None:
    """`§N` is class C — a pointer into another document's numbering,
    which nothing else reaches. Six were broken at `629a5eb0` and a
    seventh survived the fix by wrapping across a line break.

    Five of those six were not dangling but *unresolvable without
    guessing a convention* — `§0` meant item 0 of a list inside a named
    section, `§3` the third `##` by position. The repo's answer is to
    name the section instead of numbering it, which is why the message
    below offers that before it offers the marker.
    """
    broken = [
        f"{rel}:{number}: `{target}` §{section}"
        for rel, number, target, section, marked in _unresolved_section_refs()
        if not marked
    ]
    assert not broken, (
        "section references naming a section the target does not carry:\n  "
        + "\n  ".join(broken)
        + "\nIf the target numbers its sections, repoint to the right "
        "number. If it does not — the number meant an item in a list, or "
        "a heading's position — name the section instead "
        '(`spec/x.md` §"Shared body shape" item 0), which is what the '
        "repo already does elsewhere. Only if the reference is a record "
        f"of a pointer that was wrong on its date, mark it {SECTION_ESCAPE!r}."
    )


def test_no_section_marker_outlives_the_reference_it_covers() -> None:
    """Same both-directions rule as the inline path marker: a marker
    covering nothing is stale, and it is the direction that stays green.
    One marker exists today, and it is how the hatch stays that size.
    """
    covered = {
        (rel, number) for rel, number, _, _, marked in _unresolved_section_refs() if marked
    }
    stale = [
        f"{doc.relative_to(REPO)}:{number}"
        for doc in LIVE_PROSE
        for number, line in enumerate(doc.read_text().splitlines(), 1)
        if SECTION_ESCAPE in line and (str(doc.relative_to(REPO)), number) not in covered
    ]
    assert not stale, (
        f"{SECTION_ESCAPE!r} on a line whose section references all resolve:\n  "
        + "\n  ".join(stale)
        + "\nThe marker has outlived its reason — drop it."
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
