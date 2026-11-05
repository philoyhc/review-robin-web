"""CI's ``test`` job runs as shards (segment 22H Item 2): together they
must collect exactly what a bare ``pytest`` collects, so a new test root
or file cannot fall out of CI."""

from __future__ import annotations

import itertools
import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _shard_args() -> list[list[str]]:
    found = re.findall(r'^\s*pytest_args:\s*"([^"]*)"\s*$', CI.read_text(), flags=re.M)
    assert len(found) >= 2, "ci.yml's test matrix lists no shards"
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


def test_the_shards_cover_testpaths_once() -> None:
    shards = [_test_files(args) for args in _shard_args()]
    union = set().union(*shards)
    expected = _test_files(_testpaths())
    assert union == expected, sorted(str(p.relative_to(ROOT)) for p in union ^ expected)
    # Pairwise: a file in any two shards runs twice (item read).
    for a, b in itertools.combinations(shards, 2):
        overlap = a & b
        assert not overlap, sorted(str(p.relative_to(ROOT)) for p in overlap)


def test_the_run_step_passes_the_shard_args() -> None:
    assert re.search(r"^\s*pytest -n auto \$PYTEST_ARGS\s*$", CI.read_text(), flags=re.M)
    assert "PYTEST_ARGS: ${{ matrix.shard.pytest_args }}" in CI.read_text()


def test_every_shard_runs_something() -> None:
    assert all(_test_files(args) for args in _shard_args())
