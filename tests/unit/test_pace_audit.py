"""The ``Instruction-Received`` split in ``tools/pace_audit.py``.

The trailer is read from a slice's *first* commit only, bounded to the
slice's own window, and reported once three slices carry it. These tests
build a throwaway git repo rather than reading this one: ``actions/checkout@v4``
clones at depth 1, so nothing that depends on this repository's history
can run in CI.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    path = REPO_ROOT / "tools" / "pace_audit.py"
    spec = importlib.util.spec_from_file_location("pace_audit_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pa = _load()

T0 = dt.datetime(2026, 9, 20, 10, 0, tzinfo=dt.timezone.utc)


def _at(minutes: int) -> str:
    return (T0 + dt.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


class Repo:
    """A main line with merged slices, each commit at a chosen minute."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.n = 0
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        (root / "README.md").write_text("start\n")
        self.git("add", "-A")
        self.commit("start", minute=0)

    def git(self, *args: str, minute: int | None = None) -> str:
        env = dict(os.environ)
        if minute is not None:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = _at(minute)
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True,
            text=True, env=env,
        ).stdout

    def commit(self, message: str, minute: int) -> None:
        self.git("commit", "-q", "--allow-empty", "-m", message, minute=minute)

    def slice(self, commits: list[tuple[str, int]], merge_minute: int, code: bool = True) -> str:
        """Branch, commit each (message, minute), merge as a PR. Returns the merge SHA."""
        self.n += 1
        branch = f"slice-{self.n}"
        self.git("checkout", "-q", "-b", branch)
        for i, (message, minute) in enumerate(commits):
            path = self.root / ("app" if code else "guide") / f"s{self.n}_{i}.txt"
            path.parent.mkdir(exist_ok=True)
            path.write_text("x\n" * 10)
            self.git("add", "-A")
            self.commit(message, minute)
        self.git("checkout", "-q", "main")
        self.git(
            "merge", "-q", "--no-ff", branch, "-m",
            f"Merge pull request #{self.n} from x/{branch}\n\nSlice {self.n}",
            minute=merge_minute,
        )
        return self.git("rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    r = Repo(tmp_path / "repo")
    monkeypatch.chdir(r.root)
    return r


def _stamped(minute: int, subject: str = "build") -> str:
    return f"{subject}\n\nInstruction-Received: {_at(minute)}"


# --------------------------------------------------------------------
# instruction_received: which commit, and what it accepts


def test_trailer_on_the_first_commit_is_read(repo: Repo) -> None:
    sha = repo.slice([(_stamped(3), 8)], merge_minute=10)
    assert pa.instruction_received(sha) == int((T0 + dt.timedelta(minutes=3)).timestamp())


def test_no_trailer_is_none(repo: Repo) -> None:
    sha = repo.slice([("build\n\nCo-Authored-By: X <x@example.com>", 8)], merge_minute=10)
    assert pa.instruction_received(sha) is None


def test_malformed_trailer_is_none(repo: Repo) -> None:
    sha = repo.slice([("build\n\nInstruction-Received: yesterday-ish", 8)], merge_minute=10)
    assert pa.instruction_received(sha) is None


def test_trailer_on_a_later_commit_only_is_not_read(repo: Repo) -> None:
    # A fix commit answering a reader does not carry the stamp, and one
    # that does by mistake must not be mistaken for the slice's start.
    sha = repo.slice([("build", 8), (_stamped(9, "act on the cold read"), 12)], merge_minute=14)
    assert pa.instruction_received(sha) is None


# --------------------------------------------------------------------
# the split: bounded to the slice's own window


def _rows(repo: Repo) -> list[dict]:
    return pa.load("2026-09-01", ref="main")


def test_split_inside_the_window(repo: Repo) -> None:
    repo.slice([("first", 5)], merge_minute=10)
    repo.slice([(_stamped(13), 20)], merge_minute=25)
    rows = _rows(repo)
    second = rows[-1]
    assert second["turn"] == pytest.approx(10.0)
    assert second["wait"] == pytest.approx(3.0)
    assert second["build"] == pytest.approx(7.0)


def test_stamp_before_the_previous_merge_is_not_split(repo: Repo) -> None:
    repo.slice([("first", 5)], merge_minute=10)
    repo.slice([(_stamped(2), 20)], merge_minute=25)  # stamped before #1 merged
    second = _rows(repo)[-1]
    assert second["received"] is not None
    assert second["wait"] is None and second["build"] is None


def test_stamp_after_the_first_commit_is_not_split(repo: Repo) -> None:
    repo.slice([("first", 5)], merge_minute=10)
    repo.slice([(_stamped(22), 20)], merge_minute=25)  # stamped after committing
    second = _rows(repo)[-1]
    assert second["wait"] is None and second["build"] is None


def test_first_slice_has_no_previous_merge_and_no_split(repo: Repo) -> None:
    repo.slice([(_stamped(3), 8)], merge_minute=10)
    first = _rows(repo)[0]
    assert first["received"] is not None
    assert first["turn"] is None and first["wait"] is None


# --------------------------------------------------------------------
# the report: silent below three stamped slices, one line at three


def test_report_needs_three_stamped_slices(repo: Repo, capsys: pytest.CaptureFixture) -> None:
    repo.slice([("first", 5)], merge_minute=10)
    repo.slice([(_stamped(13), 20)], merge_minute=25)
    repo.slice([(_stamped(28), 35)], merge_minute=40)
    pa.report("t", _rows(repo))
    out = capsys.readouterr().out
    assert "turn split: 2 slices carry Instruction-Received; needs 3" in out


def test_report_prints_the_split_at_three(repo: Repo, capsys: pytest.CaptureFixture) -> None:
    repo.slice([("first", 5)], merge_minute=10)
    repo.slice([(_stamped(13), 20)], merge_minute=25)  # wait 3, build 7
    repo.slice([(_stamped(28), 35)], merge_minute=40)  # wait 3, build 7
    repo.slice([(_stamped(46), 50)], merge_minute=55)  # wait 6, build 4
    pa.report("t", _rows(repo))
    out = capsys.readouterr().out
    assert "turn split on Instruction-Received (n=3)" in out
    assert "wait med  3.0 mean  4.0" in out
    assert "build med  7.0 mean  6.0" in out
