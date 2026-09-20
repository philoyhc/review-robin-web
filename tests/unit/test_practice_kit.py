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

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    path = REPO_ROOT / "tools" / "practice_kit.py"
    spec = importlib.util.spec_from_file_location("practice_kit_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pk = _load()


def _deferred_group_landed(needs: str) -> bool:
    """Has setup step 7 exported this deferred group into the tree?

    A group whose trigger the *project* writes — ``app/main.py`` for the app
    pair — has landed when that file appears: the trigger's whole job is to
    say the group is now due.

    A group whose trigger the *kit builds* (``BUILDERS``) cannot use it as
    the signal, because the trigger is itself a group member and a project
    may write its own before the group arrives. Step 7 tells the reader to do
    exactly that. Such a group has landed when any member the kit copies
    rather than builds is present, which stays true however far the built
    file is later edited — so editing ``base.html`` can never quietly retire
    the gate over the other eight theme files."""
    trigger = pk.DEFERRED_GROUPS[needs]
    if trigger not in pk.BUILDERS:
        return (REPO_ROOT / trigger).is_file()
    return any(
        (REPO_ROOT / path).is_file()
        for path, _tier, group, _note in pk.MANIFEST
        if group == needs and path not in pk.BUILDERS
    )


needs_theme_source = pytest.mark.skipif(
    not _deferred_group_landed("theme"),
    reason="the theme group has not landed, so there is no kit base.html to slice (step 7)",
)

_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|")


def _document_rows() -> dict[str, tuple[str, str]]:
    """path -> (tier, needs) as the setup document's table states them; a
    `—` in the Needs column is the table's spelling of no group."""
    text = (REPO_ROOT / "new_project_practices_setup.md").read_text()
    rows = {}
    for line in text.splitlines():
        m = _ROW.match(line)
        if m and m.group(2) in pk.TIERS:
            needs = m.group(3)
            rows[m.group(1)] = (m.group(2), "" if needs == "—" else needs)
    return rows


def test_every_copied_path_exists() -> None:
    """Verbatim and adapt entries always; a deferred group once it has landed
    (`_deferred_group_landed`).

    In a repository the kit was just exported into, a deferred group is
    absent by design until setup step 7 lands it: `app/main.py` triggers the
    `app` pair, and the theme group needs a `base.html` the kit built, since
    a hand-written one is not the group arriving."""
    def required(tier: str, needs: str) -> bool:
        if tier in ("verbatim", "adapt"):
            return True
        return tier == "deferred" and _deferred_group_landed(needs)

    missing = [
        p for p, tier, needs, _ in pk.MANIFEST
        if required(tier, needs) and not (REPO_ROOT / p).is_file()
    ]
    assert not missing, f"manifest names files that are not in the tree: {missing}"


def test_every_skeleton_has_a_generator() -> None:
    absent = [p for p, tier, _, _ in pk.MANIFEST if tier == "skeleton" and p != ".gitignore" and p not in pk.SKELETONS]
    assert not absent, f"skeleton entries with no SKELETONS text: {absent}"


def test_tiers_are_known_and_paths_unique() -> None:
    assert all(tier in pk.TIERS for _, tier, _, _ in pk.MANIFEST)
    assert all((tier == "deferred") == bool(needs) for _, tier, needs, _ in pk.MANIFEST)
    assert all(needs in pk.DEFERRED_GROUPS for _, tier, needs, _ in pk.MANIFEST if needs)
    paths = pk.manifest_paths()
    assert len(paths) == len(set(paths))


def test_the_setup_document_table_matches_the_manifest() -> None:
    rows = _document_rows()
    expected = {p: (tier, needs) for p, tier, needs, _ in pk.MANIFEST}
    assert rows == expected, (
        "new_project_practices_setup.md's kit table has drifted from tools/practice_kit.py MANIFEST; "
        "regenerate it with `python3 tools/practice_kit.py --list`.\n"
        f"only in document: {sorted(set(rows) - set(expected))}\n"
        f"only in manifest: {sorted(set(expected) - set(rows))}\n"
        f"tier or needs mismatch: {sorted(p for p in rows if p in expected and rows[p] != expected[p])}"
    )


def test_export_writes_every_entry_and_never_overwrites(tmp_path: pathlib.Path) -> None:
    dest = tmp_path / "fresh"
    (dest / ".gitignore").parent.mkdir(parents=True)
    (dest / ".gitignore").write_text("*.pyc\n")
    report = pk.export(dest)
    assert not [line for line in report if line.startswith("MISSING")], report
    for path, tier, _, _ in pk.MANIFEST:
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
    """Naming one group exports that group's files and no other's."""
    dest = tmp_path / "fresh"
    pk.export(dest, include_deferred={"app"})
    for path, tier, needs, _ in pk.MANIFEST:
        if tier == "deferred":
            expected = needs == "app" and (REPO_ROOT / path).is_file()
            assert (dest / path).is_file() == expected, path


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


@needs_theme_source
def test_theme_group_builds_a_starter_base_template(tmp_path: pathlib.Path) -> None:
    """The theme group needs base.html, so exporting it builds one from the
    source: the no-flash script and the whole stylesheet, then a content
    block — and never over an existing base.html."""
    dest = tmp_path / "fresh"
    pk.export(dest, include_deferred={"theme"})
    base = dest / "app/web/templates/base.html"
    text = base.read_text()
    assert text.startswith("<!doctype html>")
    assert ":root" in text and "</style>" in text
    assert "{% block content %}" in text
    assert text.count("<body") == 1
    assert '<body class="ui-v2 {% block body_class %}{% endblock %}">' in text
    assert 'data-theme-choice="dark"' in text
    assert 'localStorage.setItem("rrw-theme", mode)' in text
    for path, tier, needs, _ in pk.MANIFEST:
        if needs == "theme":
            assert (dest / path).is_file(), path
    base.write_text("mine\n")
    pk.export(dest, include_deferred={"theme"})
    assert base.read_text() == "mine\n"


def test_an_unknown_deferred_group_is_refused(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="unknown deferred group"):
        pk.export(tmp_path / "fresh", include_deferred={"themes"})


@needs_theme_source
def test_a_kit_built_project_can_be_the_source_for_the_next(tmp_path: pathlib.Path) -> None:
    """Second-generation inheritance: a tree the kit built has the toggle
    inline in base.html and no partial, and must still export the theme
    group — including building the next base.html — without this repo."""
    first = tmp_path / "first"
    pk.export(first, include_deferred={"theme"})
    assert not (first / "app/web/templates/_partials/theme_toggle.html").exists()
    second = tmp_path / "second"
    report = pk.export(second, source=first, include_deferred={"theme"})
    assert not [line for line in report if line.startswith("MISSING")], report
    text = (second / "app/web/templates/base.html").read_text()
    assert text.count('<div class="theme-toggle"') == 1
    assert text.count('data-theme-choice="dark"') == 1
    assert 'localStorage.setItem("rrw-theme", mode)' in text
