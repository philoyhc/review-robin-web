"""`tools/code_metrics.py` must refuse the churn metric on a shallow clone.

The 2026-09-18 assessment found the churn figure could not come out
wrong: `git blame` cannot see past a shallow graft, so both halves of
the ratio are forced to the same number and it reports `1.0x` whatever
the truth is — while the header claimed to have walked "all 130 merges"
of a history with 2,452. Nothing in `.github/workflows/` sets
`fetch-depth`, so an agent sandbox is the only place the tool is ever
run, which is precisely where it is least able to answer.

The guard is itself an instrument, so it is tested against **real git
state** rather than a monkeypatched predicate: a throwaway repository
is cloned at `--depth 1` and both sides are asserted. A stubbed `_git`
would only prove that the string comparison works.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "code_metrics", REPO / "tools" / "code_metrics.py"
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(*args: str, cwd: pathlib.Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def shallow_and_full(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """A two-commit repository and a depth-1 clone of it.

    `file://` matters: a clone from a plain local path is a hardlink
    copy and ignores `--depth` entirely, so the "shallow" side would
    silently not be shallow and the test would pass while asserting
    nothing.
    """
    full = tmp_path / "full"
    full.mkdir()
    _run("git", "init", "-q", "-b", "main", cwd=full)
    _run("git", "config", "user.email", "t@example.edu", cwd=full)
    _run("git", "config", "user.name", "T", cwd=full)
    for n in (1, 2):
        (full / "f.txt").write_text(f"{n}\n")
        _run("git", "add", "f.txt", cwd=full)
        _run("git", "commit", "-qm", f"c{n}", cwd=full)

    shallow = tmp_path / "shallow"
    _run(
        "git",
        "clone",
        "-q",
        "--depth",
        "1",
        f"file://{full}",
        str(shallow),
        cwd=tmp_path,
    )
    return shallow, full


def test_the_fixture_really_produces_a_shallow_clone(
    shallow_and_full: tuple[pathlib.Path, pathlib.Path],
) -> None:
    """Guards the fixture: if `--depth` were ignored, every case below
    would pass without exercising the branch it exists for."""
    shallow, full = shallow_and_full
    assert (shallow / ".git" / "shallow").exists()
    assert not (full / ".git" / "shallow").exists()


def test_is_shallow_repository_reads_real_git_state(
    shallow_and_full: tuple[pathlib.Path, pathlib.Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shallow, full = shallow_and_full
    module = _load()

    monkeypatch.setattr(module, "REPO", shallow)
    assert module.is_shallow_repository() is True

    monkeypatch.setattr(module, "REPO", full)
    assert module.is_shallow_repository() is False


def test_churn_exits_non_zero_and_names_the_remedy_on_a_shallow_clone(
    shallow_and_full: tuple[pathlib.Path, pathlib.Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The exit code is the point: a sandbox that runs this in a script
    has to be told, and a printed warning above a plausible-looking
    number is what the old behaviour amounted to."""
    shallow, _ = shallow_and_full
    module = _load()
    monkeypatch.setattr(module, "REPO", shallow)
    monkeypatch.setattr("sys.argv", ["code_metrics.py", "--churn-only"])

    assert module.main() == 1

    out = capsys.readouterr().out
    assert "refusing to run on a shallow clone" in out
    assert "git fetch --unshallow" in out
    # And no report. The refusal *quotes* the degenerate `1.0x` while
    # explaining itself, so the assertion is that the churn output is
    # absent — its header and its percentages — rather than that no
    # digits appear anywhere.
    assert "lines deleted within" not in out, out
    assert "%" not in out, out


def test_duplication_still_runs_on_a_shallow_clone(
    shallow_and_full: tuple[pathlib.Path, pathlib.Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Duplication reads the worktree, not the history, so the graft does
    not touch it. Refusing both halves would make the guard cost more
    than it saves."""
    shallow, _ = shallow_and_full
    module = _load()
    monkeypatch.setattr(module, "REPO", shallow)
    monkeypatch.setattr("sys.argv", ["code_metrics.py", "--dup-only"])

    assert module.main() == 0
    assert "DUPLICATION" in capsys.readouterr().out


def test_pr_commits_counts_merges_and_squash_merges_not_direct_commits(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Findings 2026-11-06 N9: the churn walk read merge commits only and
    missed every squash-merged PR. A squash commit is a PR when its
    subject ends ``(#N)``; a direct commit with no number is not one."""
    root = tmp_path / "repo"
    root.mkdir()
    _run("git", "init", "-q", "-b", "main", cwd=root)
    _run("git", "config", "user.email", "t@example.com", cwd=root)
    _run("git", "config", "user.name", "T", cwd=root)
    (root / "a.py").write_text("a = 1\n")
    _run("git", "add", "-A", cwd=root)
    _run("git", "commit", "-q", "-m", "Start", cwd=root)
    _run("git", "checkout", "-q", "-b", "slice", cwd=root)
    (root / "b.py").write_text("b = 1\n")
    _run("git", "add", "-A", cwd=root)
    _run("git", "commit", "-q", "-m", "Slice work", cwd=root)
    _run("git", "checkout", "-q", "main", cwd=root)
    _run(
        "git",
        "merge",
        "-q",
        "--no-ff",
        "slice",
        "-m",
        "Merge pull request #1 from x/slice",
        cwd=root,
    )
    (root / "c.py").write_text("c = 1\n")
    _run("git", "add", "-A", cwd=root)
    _run("git", "commit", "-q", "-m", "A squashed slice (#2)", cwd=root)
    (root / "d.py").write_text("d = 1\n")
    _run("git", "add", "-A", cwd=root)
    _run("git", "commit", "-q", "-m", "Fix a typo on main", cwd=root)
    _run("git", "update-ref", "refs/remotes/origin/main", "main", cwd=root)
    code_metrics = _load()
    monkeypatch.setattr(code_metrics, "REPO", root)
    entries, squashed = code_metrics.pr_commits()
    assert len(entries) == 2
    assert squashed == 1
