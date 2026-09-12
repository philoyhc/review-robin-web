"""Every document in ``guide/`` and ``guide/archive/`` is named by its index.

Both folders keep a hand-maintained README, and both state the rule in
prose. ``guide/archive/README.md`` is explicit about it:

    **Whenever a file is added to `guide/archive/`, add its row to the
    matching table below in the same change.** ... A file in the
    directory with no row here is a bug.

Nothing checked either one until 2026-09-12, and both had drifted:
``guide/archive/`` carried **three** files with no row (``18R_testing.md``,
``instrument_card_ux_audit.md``, ``semantic_tokens.md``, unindexed since
August), and ``guide/`` carried ``pill_style_audit.md``, which matched no
row and no pattern. The rule was right; the enforcement was a person
remembering.

**The allowed patterns are read out of the README's own table, not
hardcoded here.** ``guide/README.md`` deliberately indexes some files by
shape rather than by name — ``segment_*.md``, ``codebase_assessment_*.md``,
``sweep_<YYYY-MM-DD>_<scope>.md`` — because those are open sets. Parsing
the table means adding a documented shape to the index also teaches this
test about it, and a shape nobody documented covers nothing. The
constitution's "constant-derived gates only" rule, applied to a document.

Scope is ``*.md``. JSON sidecars (``codebase_assessment_11sep.json``,
``assessment.json``) are excluded: the archive index names them inline on
their document's row (``codebase_assessment_17aug.md`` (+ ``.json``))
rather than giving them one, so requiring a row of their own would fail on
the convention the index actually uses.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GUIDE = REPO / "guide"
ARCHIVE = GUIDE / "archive"

#: First backticked token of a markdown table row — the table's Path column.
_ROW_PATH = re.compile(r"^\|\s*`([^`]+)`")

#: A `<placeholder>` in a documented filename shape, e.g. `<YYYY-MM-DD>`.
_PLACEHOLDER = re.compile(r"<[^>]+>")


def _indexed_names(readme: Path) -> tuple[set[str], list[str]]:
    """Split a README's Path column into literal names and glob patterns.

    A cell carrying ``*`` or a ``<placeholder>`` is a shape covering an
    open set; everything else names one file. Placeholders become ``*``
    so ``sweep_<YYYY-MM-DD>_<scope>.md`` matches a real sweep filename.
    """
    literals: set[str] = set()
    patterns: list[str] = []
    for line in readme.read_text().splitlines():
        match = _ROW_PATH.match(line)
        if not match:
            continue
        cell = match.group(1)
        if not cell.endswith(".md"):
            continue  # `archive/` and other non-document rows
        if "*" in cell or "<" in cell:
            patterns.append(_PLACEHOLDER.sub("*", cell))
        else:
            literals.add(cell)
    return literals, patterns


def _documents(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.md") if p.name != "README.md")


def _unindexed(folder: Path) -> list[str]:
    literals, patterns = _indexed_names(folder / "README.md")
    return [
        doc.name
        for doc in _documents(folder)
        if doc.name not in literals
        and not any(fnmatch.fnmatch(doc.name, pat) for pat in patterns)
    ]


def test_the_archive_index_names_every_archived_document() -> None:
    """`guide/archive/README.md`'s own rule: no row here is a bug."""
    missing = _unindexed(ARCHIVE)
    assert not missing, (
        "archived with no row in guide/archive/README.md: "
        f"{missing}. Add a row describing what the document is and when "
        "it was archived — that index is maintained by hand."
    )


def test_the_guide_index_names_every_live_document() -> None:
    """Every live `guide/` document is named, by name or by shape."""
    missing = _unindexed(GUIDE)
    assert not missing, (
        f"live in guide/ with no row and matching no documented shape: {missing}. "
        "Add a row to guide/README.md, or archive the document."
    )


def test_the_archive_index_uses_no_patterns() -> None:
    """The archive is a closed set, so every row there names one file.

    Guards the guard: a `*` row in the archive index would silently
    satisfy the completeness test above for every file it matched,
    turning a per-document index into a wildcard that checks nothing.
    """
    _, patterns = _indexed_names(ARCHIVE / "README.md")
    assert not patterns, (
        f"guide/archive/README.md carries pattern row(s) {patterns}. "
        "The archive index names each file individually; a pattern row "
        "would make the completeness check vacuous for everything it covers."
    )


#: Names no documented shape should ever cover. A pattern matching one of
#: these is broad enough to make the completeness tests vacuous.
_PROBES = ("zzz_unindexed_probe.md", "notes.md", "scratch_2026.md")


@pytest.mark.parametrize("folder", [GUIDE, ARCHIVE], ids=["guide", "archive"])
def test_no_documented_shape_is_a_catch_all(folder: Path) -> None:
    """A shape row covers an open set, not *any* name.

    This is the vacuity these tests are actually exposed to. A README
    row of ``*.md`` — or a shape that decays into one — would satisfy
    the completeness checks for every file in the folder while checking
    nothing, and unlike a parse that stops matching (which fails loudly,
    reporting every file as missing) it fails silent and green.

    Deliberately not a count threshold. The first version of this test
    asserted the parse found at least ten rows, and that broke the same
    day, when archiving two documents took ``guide/README.md`` from
    eleven document rows to nine — a hardcoded number in a test whose
    own docstring argues for deriving gates from the document.
    """
    _, patterns = _indexed_names(folder / "README.md")
    for probe in _PROBES:
        covering = [pat for pat in patterns if fnmatch.fnmatch(probe, pat)]
        assert not covering, (
            f"{folder.name}/README.md shape row(s) {covering} match "
            f"{probe!r}, which nothing in the index should cover. A shape "
            "this broad makes the completeness check pass for anything."
        )

    # The probes above catch a *total* catch-all. They do not catch partial
    # broadening: `*assessment*.md` matches none of them while quietly
    # covering any file with "assessment" in its name — which is how
    # `inplace_pagination_assessment.md` would have gone unindexed. Found by
    # mutation, not by reading. A documented shape names a family by its
    # prefix (`segment_`, `codebase_assessment_`, `sweep_`), so a leading
    # wildcard means the row has stopped naming a family.
    leading = [pat for pat in patterns if pat.startswith("*")]
    assert not leading, (
        f"{folder.name}/README.md shape row(s) {leading} start with a "
        "wildcard, so they name no family and cover files no one indexed. "
        "Write the prefix the family actually shares."
    )
