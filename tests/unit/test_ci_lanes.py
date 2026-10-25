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
        "residentialapps/README.md",
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
        "cordware/README.md",  # Markdown, but not in a prose folder
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


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "merge_group", ""])
def test_any_event_but_a_pull_request_is_full(event):
    assert ci_lanes.lane(["spec/lifecycle.md"], event) == "full"


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
    ci_lanes.main(["--event", "pull_request"])
    assert capsys.readouterr().out == "lane=full\n"


def test_the_prose_lane_runs_every_test_that_reads_prose():
    """Derived, not listed by hand: a test file outside tests/unit/ that reads
    a prose path must be in PROSE_TESTS, or a prose-only PR would skip it."""
    readers = set(ci_lanes.prose_reading_tests())
    assert readers, "the scan found nothing; its pattern no longer matches the tree"
    assert readers <= set(ci_lanes.PROSE_TESTS)


def test_every_listed_prose_test_exists():
    for entry in ci_lanes.PROSE_TESTS:
        assert (REPO / entry).exists(), entry
