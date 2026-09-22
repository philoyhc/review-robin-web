"""Guard the references live prose makes into the tree — and the twins.

Three checks that read nothing but the repository: `CLAUDE.md` and
`AGENTS.md` are byte-identical; every backticked repo path in live prose
resolves; every `§N` pointer names a section its target carries. They
depend on no application constant, which is why they live apart from
`test_doc_conventions.py` (whose checks derive from `app` constants and
`base.html`) and why `tools/practice_kit.py` ships this file verbatim to a
new repository. Split out 2026-09-20 for that reason; the checks and their
escape markers are unchanged from where they were written (19G.1, 19G.5,
19G.7).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


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
#:
#: Assessment snapshots come in **lineages**, one per agent that writes
#: them (`codebase_assessment_` for Claude Code, `codex_assessment_` for
#: Codex), and each lineage retires its own. Both are dated records, so
#: both are exempt. `codex_assessment_` was missing until 2026-09-12, so
#: that lineage was being held to live-prose standards: it passed only
#: because none of its 17 path references had moved yet, while the
#: `codebase_assessment_` snapshot beside it already carried one dangling
#: reference (`guide/inplace_pagination_assessment.md`, archived the day
#: before) and was correctly exempt from failing on it.
#:
#: Enumerated rather than generalised to `assessment_`: a broader token
#: would silently exempt a live document that happened to carry the word,
#: and a new lineage needs a `guide/README.md` row anyway, so one line
#: here is the same edit.
DATED_DOC = re.compile(
    r"(codebase_assessment_|codex_assessment_|sweep_|practice-audit-|segment_)"
)

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


# --- Node ids: `tests/…py::test_name` must name a test that exists ---

#: A pytest node id in prose. The file half is anchored on ``tests/``
#: and the name half allows ``[case]`` so a parametrised id is *matched*
#: and then rejected with a reason, rather than skipped by the pattern
#: and silently tolerated (19S Item 8, `Semantics`).
#:
#: Deliberately disjoint from :data:`PATH_REF`, which stops at the first
#: character outside ``[A-Za-z0-9_./-]`` and so cannot reach the closing
#: backtick of a node id — the file half of a citation is unchecked by
#: the path check today, which is the gap this closes. Asserted below, so
#: that a later widening of ``PATH_REF`` shows up as a decision rather
#: than as silent double coverage.
NODE_REF = re.compile(r"`(tests/[A-Za-z0-9_./-]+\.py)::([A-Za-z0-9_\[\]-]+)`")


def _node_ref_failure(path: str, name: str) -> str:
    """Why a cited node id does not resolve, or ``""`` if it does.

    Resolution is by **definition name read from the file**, not by
    ``pytest --collect-only``: collection is the authoritative answer and
    the wrong instrument here, costing a subprocess per hit and turning
    an unrelated collection error anywhere in the suite into this check's
    failure (19S Item 8, `Decision`).

    That substitution is exact only while every test is a module-level
    function. The suite has **0** class-based tests
    (``grep -rc "^class Test" tests/``), re-measured at the close; if one
    ever lands, a citation of its method resolves here by name alone and
    this docstring is the thing to revisit.
    """
    if "[" in name:
        # Checked before the file, because it is a statement about the
        # citation's shape rather than about the repo: a parametrised id
        # on a missing file should say which complaint the author can
        # act on without also fixing the other.
        return (
            "parametrised ids are not resolved by this check — cite the "
            "base test name, or mark the line if the case id matters"
        )
    target = REPO / path
    if not target.exists():
        return "no such file"
    pattern = rf"^\s*(?:async\s+)?def {re.escape(name)}\("
    if re.search(pattern, target.read_text(), re.M) is None:
        return "file has no test by that name"
    return ""


def _node_refs() -> list[tuple[str, int, str, str, str, str]]:
    """Every node-id citation in live prose as
    ``(doc, line, path, name, failure, cover)``, with ``cover`` one of
    ``""`` / ``"inline"`` / ``"section"``.

    The **section** escape is the path check's, reused rather than
    duplicated: a node id is a repo reference like any other, and the
    reason a dated register carries a stale one — ``renamed X`` — is the
    same reason. The consequence is named rather than left implicit:
    `docs/status.md`'s timeline and `guide/todo_master.md`'s `## Done`
    opt out as whole sections, so a node id written *there* is not
    checked.

    There is deliberately **no inline escape**, and the reason was
    measured rather than assumed. Reusing ``PATH_ESCAPE`` looked free and
    is not: ``test_no_inline_path_marker_outlives_the_reference_it_covers``
    computes its coverage from path references alone, so a marker placed
    over a broken *node id* reads as a marker covering nothing and turns
    the suite red — the remedy the failure message offers would itself
    fail. Teaching that check about node ids means editing a check this
    item is scoped not to touch (19S Item 8, `PR ladder`), and minting a
    second marker with zero uses is mechanism ahead of need. So a
    one-line historical citation has no escape today; the first one that
    needs it is the argument for adding it.
    """
    found: list[tuple[str, int, str, str, str, str]] = []
    for doc in LIVE_PROSE:
        rel = str(doc.relative_to(REPO))
        lines = doc.read_text().splitlines()
        opted = _dated_register_lines(lines)
        for number, line in enumerate(lines, 1):
            for match in NODE_REF.finditer(line):
                failure = _node_ref_failure(match.group(1), match.group(2))
                if not failure:
                    continue
                cover = "section" if number in opted else ""
                found.append(
                    (rel, number, match.group(1), match.group(2), failure, cover)
                )
    return found


def test_every_node_id_in_live_prose_names_a_test_that_exists() -> None:
    """A cited proof must be runnable, or the reader gets a collection
    error where they expected evidence.

    The instance is 19S Item 4's: a findings register cited a test by its
    pre-rename name, and `guide/findings_2026-09-22_csv_contracts.md` is
    not matched by ``DATED_DOC``, so this check would have caught it.
    The case is not the size of today's corpus — 2 citations, both
    resolving — but that all **3** citations in `guide/archive/` are
    stale, across two segments. Archived prose is history and stays
    exempt; those three are the evidence that the failure mode recurs.
    """
    dangling = [
        f"{rel}:{number}: `{path}::{name}` — {failure}"
        for rel, number, path, name, failure, cover in _node_refs()
        if not cover
    ]
    assert not dangling, (
        "node ids naming no test:\n  "
        + "\n  ".join(dangling)
        + "\nRepoint it at the test as it is named now. A record of what "
        "was true on its date belongs in a section already marked "
        f"{PATH_SECTION_ESCAPE!r}, which exempts it — there is no inline "
        "escape for a node id, deliberately; see ``_node_refs``."
    )


def test_the_node_id_scan_still_sees_the_citations_that_exist() -> None:
    """A floor, so a recogniser that matches nothing cannot pass.

    ``test_every_node_id_in_live_prose_names_a_test_that_exists`` is
    satisfied by an empty scan, which is how a pattern that silently
    stopped matching would look. Two live citations existed at the close;
    the floor asserts the scan reaches them without pinning the count,
    since a figure self-stales and the next legitimate citation should
    not fail a test.

    It asserts reach and **not** that every citation resolves. A draft of
    this test did assert that, and a citation inside a section-escaped
    dated register — legal, and exempt from the check above — made it
    fail. A floor that contradicts its own escape is a floor that will be
    deleted the first time someone uses the escape.
    """
    seen = [
        (str(doc.relative_to(REPO)), match.group(1), match.group(2))
        for doc in LIVE_PROSE
        for line in doc.read_text().splitlines()
        for match in NODE_REF.finditer(line)
    ]
    assert seen, (
        "the node-id pattern matched nothing in live prose. Either every "
        "citation was removed, or NODE_REF stopped recognising them."
    )


def test_the_node_id_recogniser_works_outside_its_live_examples() -> None:
    """The recogniser tested on inputs it was not written against, per
    `docs/unenforced_conventions.md` §1.8's third clause — two live
    citations are too few to show a pattern recognises the right shape
    rather than those two strings.
    """
    matched = lambda s: NODE_REF.findall(s)  # noqa: E731
    assert matched("proof: `tests/unit/test_a.py::test_b`") == [
        ("tests/unit/test_a.py", "test_b")
    ]
    assert matched("`tests/integration/sub/test_a.py::test_b_c-d`") == [
        ("tests/integration/sub/test_a.py", "test_b_c-d")
    ]
    assert matched("two `tests/a.py::test_x` and `tests/b.py::test_y`") == [
        ("tests/a.py", "test_x"),
        ("tests/b.py", "test_y"),
    ]
    # Shapes that must NOT match: unbackticked, outside tests/, and a
    # bare path (which is PATH_REF's job, not this one's).
    assert matched("tests/unit/test_a.py::test_b") == []
    assert matched("`app/services/x.py::thing`") == []
    assert matched("`tests/unit/test_a.py`") == []
    # A parametrised id is matched and then rejected with a reason,
    # rather than skipped by the pattern.
    assert matched("`tests/a.py::test_x[case]`") == [("tests/a.py", "test_x[case]")]
    # On a file that exists, so the reason is the shape and not the path
    # — the ordering inside ``_node_ref_failure`` is what this pins.
    here = "tests/unit/test_doc_references.py"
    assert "parametrised" in _node_ref_failure(here, "test_x[case]")
    assert _node_ref_failure("tests/nope.py", "test_x") == "no such file"
    assert _node_ref_failure(here, "test_not_here") == (
        "file has no test by that name"
    )
    assert _node_ref_failure(here, "test_every_node_id_in_live_prose_names_a_test_that_exists") == ""
    # PATH_REF cannot reach a node id's closing backtick, so the two
    # patterns do not double-cover. A widening of PATH_REF breaks this.
    assert PATH_REF.findall("`tests/unit/test_a.py::test_b`") == []


def test_archived_prose_is_exempt_from_the_node_id_check() -> None:
    """The exemption is asserted, not assumed.

    `guide/archive/` carries 3 node-id citations and **none** of them
    resolves — an archived plan records what was true, and repointing it
    would falsify it. If the corpus ever widened to include the archive,
    the suite would go red on history, so this states the concession
    where it can fail rather than only in the plan's prose.
    """
    archived = sorted((REPO / "guide" / "archive").glob("*.md"))
    stale = [
        (str(doc.relative_to(REPO)), match.group(1), match.group(2))
        for doc in archived
        for line in doc.read_text().splitlines()
        for match in NODE_REF.finditer(line)
        if _node_ref_failure(match.group(1), match.group(2))
    ]
    assert stale, (
        "no stale archived citations found — if the archive was cleaned "
        "up, this test's premise is gone and it should be retired"
    )
    assert not any(doc in {str(p.relative_to(REPO)) for p in LIVE_PROSE} for doc, _, _ in stale)
