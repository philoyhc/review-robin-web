"""tools/ci_lanes.py: which CI lanes a change needs (segment 22A)."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ci_lanes", REPO / "tools" / "ci_lanes.py")
ci_lanes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci_lanes)


@pytest.mark.parametrize(
    "path",
    [
        "spec/permissions.md",
        "docs/database.md",
        "guide/archive/segment_21D_prefix_flip.md",
        "cordware/spec/host.md",
        "residentialapps/docs/residentialapps_roles.md",
        "residentialapps/guide/todo_master.md",
        "residentialapps/spec/applications.md",
        "residentialapps/README.md",
        "tools/README.md",
        "cordware/spec/README.md",
        "CLAUDE.md",
        "README.md",
    ],
)
def test_prose_paths(path):
    assert ci_lanes.is_prose(path)


@pytest.mark.parametrize(
    "path",
    [
        "app/main.py",
        "app/web/templates/base.html",
        "tests/unit/test_doc_references.py",
        "alembic/env.py",
        ".github/workflows/ci.yml",
        "pyproject.toml",
        "tools/ci_lanes.py",
        "docs/sample_data/basic_cohort/mock_observers.csv",  # not Markdown
        "guide/theme_preview.html",
        "cordware/main.py",
        "cordware/NOTES.md",  # Markdown, but not in a prose folder or a README
        "app/README.md",  # ships with the app
        "app/web/static/guide/README.md",
        "alembic/README.md",
        "cordware/README.md",  # cordware/ ships
        "cordware/web/README.md",
        "residentialapps/core/README.md",  # Residential's code ships
        "tools/README.md.bak",
        "residentialapps/core/models.py",
        "app/web/static/guide/notes.md",
    ],
)
def test_other_paths_are_not_prose(path):
    assert not ci_lanes.is_prose(path)


def test_a_pull_request_touching_only_prose_is_the_prose_lane():
    assert ci_lanes.lane(["spec/lifecycle.md", "CLAUDE.md", "AGENTS.md"], "pull_request") == "prose"


def test_one_non_prose_path_makes_it_full():
    assert ci_lanes.lane(["spec/lifecycle.md", "app/main.py"], "pull_request") == "full"


@pytest.mark.parametrize(
    "paths",
    [
        ["residentialapps/ops/main.py"],
        ["residentialapps/tests/test_mounts.py", "residentialapps/spec/applications.md"],
        ["residentialapps/supportlogs/routes_health.py", "guide/todo_master.md"],
        ["residentialapps/core/README.md"],  # shipped, so not prose
    ],
)
def test_only_prose_and_residential_is_the_residential_lane(paths):
    assert ci_lanes.lane(paths, "pull_request") == "residential"


@pytest.mark.parametrize(
    "outside",
    ["cordware/main.py", "pyproject.toml", "app/main.py", ".github/workflows/ci.yml", "tools/ci_lanes.py"],
)
def test_residential_with_anything_shared_is_full(outside):
    assert ci_lanes.lane(["residentialapps/ops/main.py", outside], "pull_request") == "full"


def test_a_path_merely_named_like_residential_is_not():
    assert ci_lanes.lane(["residentialapps_notes.py"], "pull_request") == "full"


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "merge_group", ""])
def test_any_event_but_a_pull_request_is_full(event):
    assert ci_lanes.lane(["spec/lifecycle.md"], event) == "full"
    assert ci_lanes.lane(["residentialapps/ops/main.py"], event) == "full"


def test_the_residential_lane_runs_residential_host_and_prose_tests(capsys):
    assert ci_lanes.main(["--residential-tests"]) == 0
    targets = capsys.readouterr().out.split()
    assert targets[:2] == ["residentialapps/tests", "cordware/tests"]
    assert set(ci_lanes.PROSE_TESTS) <= set(targets)
    for entry in targets:
        assert (REPO / entry).exists(), entry


@pytest.mark.parametrize("paths", [[], [""], ["   "]])
def test_an_empty_change_is_full(paths):
    assert ci_lanes.lane(paths, "pull_request") == "full"


def test_the_cli_prints_the_lane(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("docs/database.md\nguide/todo_master.md\n"))
    assert ci_lanes.main(["--event", "pull_request"]) == 0
    assert capsys.readouterr().out == "lane=prose\n"


def test_the_cli_fails_toward_full(monkeypatch, capsys):
    def broken(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(ci_lanes, "lane", broken)
    monkeypatch.setattr("sys.stdin", io.StringIO("docs/database.md\n"))
    assert ci_lanes.main(["--event", "pull_request"]) == 0
    assert capsys.readouterr().out == "lane=full\n"


def test_the_prose_lane_runs_every_test_that_reads_prose():
    """Derived, not listed by hand: a test file outside tests/unit/ naming a
    prose path must run in the prose lane or be ruled not to read prose."""
    readers = set(ci_lanes.prose_reading_tests())
    assert readers, "the scan found nothing; its pattern no longer matches the tree"
    undecided = readers - set(ci_lanes.PROSE_TESTS) - set(ci_lanes.NOT_PROSE_READERS)
    assert not undecided, f"add to PROSE_TESTS or NOT_PROSE_READERS: {sorted(undecided)}"


def test_every_ruled_non_reader_still_matches():
    """A stale entry would hide the next real reader in that file."""
    readers = set(ci_lanes.prose_reading_tests())
    assert set(ci_lanes.NOT_PROSE_READERS) <= readers


@pytest.mark.parametrize(
    "source",
    [
        'REPO / "docs/quickstart.md"',
        'ROOT / "residentialapps/README.md"',
        'Path("guide/README.md")',
        "REPO / 'docs'",
        'HERE.parent.parent / "spec"',
        'open("CLAUDE.md")',
        'Path("cordware/spec/host.md")',
        'ROOT / "residentialapps/spec/architecture.md"',
        'REPO / "tools/README.md"',
    ],
)
def test_the_scan_sees_each_way_of_naming_prose(source):
    assert ci_lanes.PROSE_LITERAL.search(source)


@pytest.mark.parametrize("source", ['Path("app/web/static/x.png")', '"operator/settings"', '"specimen"'])
def test_the_scan_ignores_other_literals(source):
    assert not ci_lanes.PROSE_LITERAL.search(source)


def test_every_listed_prose_test_exists():
    for entry in ci_lanes.PROSE_TESTS:
        assert (REPO / entry).exists(), entry


def test_a_file_moved_into_a_prose_folder_is_full(tmp_path):
    """The workflows' diff lists both sides of a rename, so a non-prose file
    moved under guide/ is classified by its old path too."""
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=tmp_path, check=True, capture_output=True, text=True,
        ).stdout

    git("init", "-q")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "notes.md").write_text("a tool's notes\n" * 20)
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    (tmp_path / "guide").mkdir()
    git("mv", "tools/notes.md", "guide/notes.md")
    git("commit", "-q", "-m", "move")
    changed = git("diff", "--name-only", "--no-renames", "HEAD^1", "HEAD").splitlines()
    assert sorted(changed) == ["guide/notes.md", "tools/notes.md"]
    assert ci_lanes.lane(changed, "pull_request") == "full"
