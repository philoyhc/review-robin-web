"""The segment-level item window in ``tools/close_check.py``.

A segment-level ``Doc impact`` manifest spans every item in the plan, so
one window let an *older* item's spec edit satisfy a *newer* item's
bullet — measured on ``19C`` at ``2520dc7d``, where C3 read a silent
``PASS`` with three Item 7 commitments outstanding. A bullet tagged
``(Item n)`` is therefore dated from that item's own heading. The
module's docstring carries the reasoning, including why an edit that
predates its item's heading warns rather than fails.

These tests build a throwaway git repo rather than reading this one:
``actions/checkout@v4`` clones at depth 1, so nothing that depends on
this repository's history can run in CI.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    path = REPO_ROOT / "tools" / "close_check.py"
    spec = importlib.util.spec_from_file_location("close_check_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load()


# --------------------------------------------------------------------
# tag parsing


def _items(text: str) -> list[int]:
    lines = ["## Doc impact", "", text, ""]
    return cc.parse_bullets(lines, 1, len(lines))[0]["items"]


@pytest.mark.parametrize(
    ("bullet", "expected"),
    [
        # Every ownership form in use across the 96 plans.
        ("- `spec/a.md` — thing (Item 1).", [1]),
        ("- `spec/a.md` — thing (Item 7).", [7]),
        ("- `spec/a.md` — thing (Item 2, on wiring).", [2]),
        ("- `spec/a.md` — thing (done — Item 3).", [3]),
        ("- `spec/a.md` — thing (done - Item 4).", [4]),
        # Two tags in one bullet, as `18R`'s `docs/status.md` bullet has.
        ("- `docs/status.md` — a (Item 1) and b (Item 2).", [1, 2]),
        # Untagged: the bullet keeps the segment window.
        ("- `spec/a.md` — thing.", []),
        # Prose that shares the words but is not an ownership tag.
        ("- `spec/a.md` — as narrowed (18S Item 3).", []),
        ("- `spec/a.md` — thing (footgun from Item 1).", []),
        ("- `spec/a.md` — landed (Slice 1 of Item 4).", []),
    ],
)
def test_item_tags_parsed(bullet: str, expected: list[int]) -> None:
    assert _items(bullet) == expected


# --------------------------------------------------------------------
# the window itself, against a real (throwaway) history


@pytest.fixture
def plan_repo(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """A git repo whose plan gains its manifest, then two item headings.

    Returns the plan path. Commits are made one at a time so that
    ancestry — which is what ``_later_commit`` orders by — is real.
    """
    root = tmp_path / "repo"
    (root / "guide").mkdir(parents=True)
    (root / "spec").mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731 - test-local shorthand
        ["git", "-C", str(root), *a], check=True, capture_output=True
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "T")

    plan = root / "guide" / "segment_ZZ_demo.md"
    spec = root / "spec" / "a.md"
    spec.write_text("one\n")
    plan.write_text("# Segment ZZ\n\n## Doc impact\n\n- `spec/a.md` — x (Item 1).\n")
    run("add", "-A")
    run("commit", "-qm", "manifest + Item 1 bullet")

    spec.write_text("two\n")  # the Item 1 edit
    run("add", "-A")
    run("commit", "-qm", "Item 1 spec edit")

    plan.write_text(plan.read_text() + "\n## Item 2 — later\n")
    run("add", "-A")
    run("commit", "-qm", "log Item 2")

    plan.write_text(plan.read_text() + "\n## Item 3 — later still\n")
    run("add", "-A")
    run("commit", "-qm", "log Item 3")

    monkeypatch.setattr(cc, "REPO", root)
    cc._ITEM_START_CACHE.clear()
    yield plan
    cc._ITEM_START_CACHE.clear()


def test_untagged_bullet_keeps_the_segment_window(plan_repo) -> None:
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    assert base is not None
    assert cc.bullet_window_start(plan_repo, base, []) == base


def test_tagged_bullet_opens_at_its_own_item_heading(plan_repo) -> None:
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    item2 = cc.item_heading_start(plan_repo, 2)
    assert item2 is not None and item2 != base
    assert cc.bullet_window_start(plan_repo, base, [2]) == item2


def test_two_tags_take_the_later_item(plan_repo) -> None:
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    item3 = cc.item_heading_start(plan_repo, 3)
    assert cc.bullet_window_start(plan_repo, base, [2, 3]) == item3
    assert cc.bullet_window_start(plan_repo, base, [3, 2]) == item3


def test_heading_earlier_than_the_manifest_does_not_widen_the_window(
    plan_repo,
) -> None:
    """An item logged *before* the manifest cannot reopen the window."""
    base = cc.item_heading_start(plan_repo, 3)
    assert cc.bullet_window_start(plan_repo, base, [2]) == base


def test_older_item_edit_does_not_honour_a_newer_item_bullet(plan_repo) -> None:
    """The blind spot itself: `spec/a.md` was edited for Item 1 only."""
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    assert cc.honoured("spec/a.md", base[0], "HEAD")
    item3 = cc.bullet_window_start(plan_repo, base, [3])
    assert cc.honoured("spec/a.md", item3[0], "HEAD") is None
