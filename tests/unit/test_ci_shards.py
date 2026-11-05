"""CI's ``test`` job (segment 22H Item 2) and ``CI - Postgres``'s
``postgres`` job (22I Item 1) run as shards: together each workflow's
shards must collect exactly what its single run did, so a new test root
or file cannot fall out of CI. ``ci-postgres.yml`` never ran
``tests/browser``, whose tests serve the app from SQLite."""

from __future__ import annotations

import itertools
import re
import shlex
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
# Each sharded workflow, and the test files its single run left out.
SHARDED = {"ci.yml": (), "ci-postgres.yml": ("tests/browser",)}


def _shard_args(workflow: str) -> list[list[str]]:
    text = (WORKFLOWS / workflow).read_text()
    found = re.findall(r'^\s*pytest_args:\s*"([^"]*)"\s*$', text, flags=re.M)
    assert len(found) >= 2, f"{workflow}'s matrix lists no shards"
    return [shlex.split(args) for args in found]


def _test_files(args: list[str]) -> set[Path]:
    """The test files ``pytest <args>`` would collect, from paths and
    ``--ignore=`` alone, matching pytest's default ``python_files``
    (``test_*.py`` and ``*_test.py``). Any other flag is refused: this
    model could not see what it drops."""
    for arg in args:
        assert not arg.startswith("-") or arg.startswith("--ignore="), (
            f"a shard passes {arg!r}, which this check cannot model"
        )
    ignored = [ROOT / a.split("=", 1)[1] for a in args if a.startswith("--ignore=")]
    roots = [ROOT / a for a in args if not a.startswith("-")]
    files: set[Path] = set()
    for root in roots:
        if root.is_file():
            candidates = [root]
        else:
            candidates = [*root.rglob("test_*.py"), *root.rglob("*_test.py")]
        for path in candidates:
            if not any(path.is_relative_to(i) for i in ignored):
                files.add(path)
    return files


def _testpaths() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return config["tool"]["pytest"]["ini_options"]["testpaths"]


@pytest.mark.parametrize("workflow", sorted(SHARDED))
def test_the_shards_cover_testpaths_once(workflow: str) -> None:
    shards = [_test_files(args) for args in _shard_args(workflow)]
    union = set().union(*shards)
    left_out = [ROOT / p for p in SHARDED[workflow]]
    expected = {
        p for p in _test_files(_testpaths()) if not any(p.is_relative_to(o) for o in left_out)
    }
    assert union == expected, sorted(str(p.relative_to(ROOT)) for p in union ^ expected)
    # Pairwise: a file in any two shards runs twice (item read).
    for a, b in itertools.combinations(shards, 2):
        overlap = a & b
        assert not overlap, sorted(str(p.relative_to(ROOT)) for p in overlap)


@pytest.mark.parametrize("workflow", sorted(SHARDED))
def test_the_run_step_passes_the_shard_args(workflow: str) -> None:
    text = (WORKFLOWS / workflow).read_text()
    assert re.search(r"^\s*pytest -n auto (-q )?\$PYTEST_ARGS\s*$", text, flags=re.M)
    assert "PYTEST_ARGS: ${{ matrix.shard.pytest_args }}" in text


@pytest.mark.parametrize("workflow", sorted(SHARDED))
def test_every_shard_runs_something(workflow: str) -> None:
    assert all(_test_files(args) for args in _shard_args(workflow))
