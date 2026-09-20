"""``tools/practice_kit.py``: the manifest, the tree and the setup document agree.

The manifest is the constant; the setup document's table and the export
are derived from it, so a file added to the kit without a row, or a row
naming a file that no longer exists, fails here rather than on the day a
new project runs the export (constitution II).
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    path = REPO_ROOT / "tools" / "practice_kit.py"
    spec = importlib.util.spec_from_file_location("practice_kit_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pk = _load()

_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\w+)\s*\|")


def _document_rows() -> dict[str, str]:
    text = (REPO_ROOT / "new_project_practices_setup.md").read_text()
    rows = {}
    for line in text.splitlines():
        m = _ROW.match(line)
        if m and m.group(2) in pk.TIERS:
            rows[m.group(1)] = m.group(2)
    return rows


def test_every_copied_path_exists() -> None:
    """Verbatim and adapt entries always; deferred ones once the app exists.

    In a repository the kit was just exported into, the deferred pair is
    absent by design until `app/main.py` is written (setup step 7)."""
    app_exists = (REPO_ROOT / "app" / "main.py").is_file()
    missing = [
        p for p, tier, _ in pk.MANIFEST
        if tier in ("verbatim", "adapt") or (tier == "deferred" and app_exists)
        if not (REPO_ROOT / p).is_file()
    ]
    assert not missing, f"manifest names files that are not in the tree: {missing}"


def test_every_skeleton_has_a_generator() -> None:
    absent = [p for p, tier, _ in pk.MANIFEST if tier == "skeleton" and p != ".gitignore" and p not in pk.SKELETONS]
    assert not absent, f"skeleton entries with no SKELETONS text: {absent}"


def test_tiers_are_known_and_paths_unique() -> None:
    assert all(tier in pk.TIERS for _, tier, _ in pk.MANIFEST)
    paths = pk.manifest_paths()
    assert len(paths) == len(set(paths))


def test_the_setup_document_table_matches_the_manifest() -> None:
    rows = _document_rows()
    expected = {p: tier for p, tier, _ in pk.MANIFEST}
    assert rows == expected, (
        "new_project_practices_setup.md's kit table has drifted from tools/practice_kit.py MANIFEST; "
        "regenerate it with `python3 tools/practice_kit.py --list`.\n"
        f"only in document: {sorted(set(rows) - set(expected))}\n"
        f"only in manifest: {sorted(set(expected) - set(rows))}\n"
        f"tier mismatch: {sorted(p for p in rows if p in expected and rows[p] != expected[p])}"
    )


def test_export_writes_every_entry_and_never_overwrites(tmp_path: pathlib.Path) -> None:
    dest = tmp_path / "fresh"
    (dest / ".gitignore").parent.mkdir(parents=True)
    (dest / ".gitignore").write_text("*.pyc\n")
    report = pk.export(dest)
    assert not [line for line in report if line.startswith("MISSING")], report
    for path, tier, _ in pk.MANIFEST:
        if tier == "deferred":
            assert not (dest / path).exists(), f"{path} exported without --include-deferred"
        else:
            assert (dest / path).is_file(), path
    assert ".claude/*" in (dest / ".gitignore").read_text()
    # A second export keeps what is there rather than clobbering an adapted file.
    (dest / "CLAUDE.md").write_text("adapted\n")
    second = pk.export(dest)
    assert (dest / "CLAUDE.md").read_text() == "adapted\n"
    assert any(line.startswith("kept") and "CLAUDE.md" in line for line in second)
    assert (dest / ".gitignore").read_text().count(".claude/*") == 1


def test_skeleton_indexes_satisfy_the_guide_index_gate(tmp_path: pathlib.Path) -> None:
    """The generated guide/README.md must name the generated guide/ files."""
    dest = tmp_path / "fresh"
    pk.export(dest)
    row = re.compile(r"^\|\s*`([^`]+)`")
    names = {m.group(1) for line in (dest / "guide/README.md").read_text().splitlines() if (m := row.match(line))}
    for doc in (dest / "guide").glob("*.md"):
        if doc.name == "README.md":
            continue
        assert doc.name in names or any(
            n.endswith("*.md") and doc.name.startswith(n.split("*")[0]) for n in names
        ), f"{doc.name} has no row in the skeleton guide/README.md"


def test_deferred_tier_exports_only_on_request(tmp_path: pathlib.Path) -> None:
    """With the flag, every deferred file the source has lands in DEST."""
    dest = tmp_path / "fresh"
    pk.export(dest, include_deferred=True)
    for path, tier, _ in pk.MANIFEST:
        if tier == "deferred":
            assert (dest / path).is_file() == (REPO_ROOT / path).is_file(), path


def test_gitignore_guard_checks_each_harness_line(tmp_path: pathlib.Path) -> None:
    """A destination that ignores .claude/* but negates nothing would swallow
    the exported agents silently; the guard must add the missing lines."""
    dest = tmp_path / "fresh"
    dest.mkdir()
    (dest / ".gitignore").write_text(".claude/*\n")
    pk.export(dest)
    text = (dest / ".gitignore").read_text()
    for line in pk.GITIGNORE_REQUIRED:
        assert text.count(line + "\n") == 1, line
