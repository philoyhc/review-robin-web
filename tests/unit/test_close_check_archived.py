r"""``--archived``, the sweep half of ``tools/close_check.py``.

The sweep had **no tests at all** until Segment 19K Item 4
(``grep -rln 'archived_report\|--archived' tests/`` returned nothing),
which is how it read **one manifest per plan** for the six days between
the tool being written and that being noticed. A segment-level manifest
spans its whole plan, so those plans were read whole; an item-shaped
plan was read at its *first* item and stopped — 37 of the 42 item
manifests in the archive had never been read, and ``19I`` was judged on
1 of its 13.

Every one of the 112 committed paths it hid turned out to be honoured,
so the sweep was **understating** the practice it exists to measure
(147/162, 91% → 259/274, 95%) — and understating it more as the plans
got better, item-shaped manifests being the newer convention.

Like ``test_close_check.py`` these build a throwaway git repo:
``actions/checkout@v4`` clones at depth 1, so nothing depending on this
repository's history can run in CI. The plan is written under
``guide/`` and ``git mv``-d into ``guide/archive/`` at the end, because
``window()`` ends an archived plan's window at the commit that added it
*at its archive path* — a plan born in ``guide/archive/`` would have a
one-commit window and test nothing.
"""

from __future__ import annotations

import importlib.util
import io
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    path = REPO_ROOT / "tools" / "close_check.py"
    spec = importlib.util.spec_from_file_location("close_check_archived_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load()


# --------------------------------------------------------------------
# manifest_levels — which manifests a plan has


def _found(text: str) -> dict:
    return cc.find_manifests(text)


def test_a_segment_manifest_is_the_only_level() -> None:
    """A segment-level manifest spans every item in the plan, so the 35
    segment-shaped archived plans were always read whole."""
    found = _found("# S\n\n## Doc impact\n\n- `spec/a.md` — x.\n")
    assert cc.manifest_levels(found) == [(2, 2, None)]


def test_every_item_manifest_is_a_level() -> None:
    """The defect. ``archived_report`` took ``next(...)`` over the items
    and stopped at the first."""
    found = _found(
        "# S\n\n## Item 1 — a\n\n### Doc impact\n\n- `spec/a.md` — x.\n\n"
        "## Item 2 — b\n\n### Doc impact\n\n- `spec/b.md` — y.\n\n"
        "## Item 3 — c\n\n### Doc impact\n\n- `spec/c.md` — z.\n"
    )
    levels = cc.manifest_levels(found)
    assert [item for _, _, item in levels] == [1, 2, 3]
    assert all(depth == 3 for _, depth, _ in levels)


def test_an_item_without_a_manifest_is_not_a_level() -> None:
    """Items are logged before they have a manifest; an item with no
    ``### Doc impact`` commits to nothing and must not be counted as a
    level with zero paths."""
    found = _found(
        "# S\n\n## Item 1 — a\n\n### Doc impact\n\n- `spec/a.md` — x.\n\n"
        "## Item 2 — logged, not yet planned\n"
    )
    assert [item for _, _, item in cc.manifest_levels(found)] == [1]


def test_a_stray_manifest_is_a_level_with_no_item() -> None:
    """A ``### Doc impact`` outside any ``## Item n`` block — 11E has one
    under ``## Follow-on`` — has no item number, so it takes the
    manifest heading's own window rather than an item's."""
    found = _found(
        "# S\n\n## Item 1 — a\n\n### Doc impact\n\n- `spec/a.md` — x.\n\n"
        "## Follow-on\n\n### Doc impact\n\n- `spec/b.md` — y.\n"
    )
    levels = cc.manifest_levels(found)
    assert (None in [item for _, _, item in levels])
    assert len(levels) == 2


def test_a_plan_with_no_manifest_has_no_levels() -> None:
    """58 of the 98 archived plans predate the convention."""
    assert cc.manifest_levels(_found("# S\n\nNo manifest here.\n")) == []


def test_both_shapes_present_keeps_the_segment_manifest() -> None:
    """A plan carrying both shapes is a C1 failure adjudicated at its own
    close. The sweep does not re-adjudicate it; it reads the segment
    manifest, as it did before."""
    found = _found(
        "# S\n\n## Doc impact\n\n- `spec/a.md` — x.\n\n"
        "## Item 1 — a\n\n### Doc impact\n\n- `spec/b.md` — y.\n"
    )
    assert [depth for _, depth, _ in cc.manifest_levels(found)] == [2]


# --------------------------------------------------------------------
# the sweep itself, against a real (throwaway) history


@pytest.fixture
def archive_repo(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """An archived, item-shaped plan with three item manifests.

    Item 1 and Item 2 each have their commitment honoured inside their
    own window. Item 3's bullet names a path that was edited **for Item
    1**, before Item 3's heading existed — the 19A.2 shape, at the sweep
    level.
    """
    root = tmp_path / "repo"
    (root / "guide" / "archive").mkdir(parents=True)
    (root / "spec").mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731 - test-local shorthand
        ["git", "-C", str(root), *a], check=True, capture_output=True
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "T")

    plan = root / "guide" / "segment_ZZ_demo.md"
    body = "# Segment ZZ\n\n## Item 1 — one\n\n### Doc impact\n\n- `spec/a.md` — x.\n"
    plan.write_text(body)
    (root / "spec" / "a.md").write_text("one\n")
    run("add", "-A")
    run("commit", "-qm", "Item 1 manifest + its edit")

    # Item 1's edit to spec/c.md — before Item 3 exists.
    (root / "spec" / "c.md").write_text("edited for Item 1\n")
    run("add", "-A")
    run("commit", "-qm", "Item 1 also touches spec/c.md")

    body += "\n## Item 2 — two\n\n### Doc impact\n\n- `spec/b.md` — y.\n"
    plan.write_text(body)
    run("add", "-A")
    run("commit", "-qm", "log Item 2")

    (root / "spec" / "b.md").write_text("two\n")
    run("add", "-A")
    run("commit", "-qm", "Item 2's edit")

    body += "\n## Item 3 — three\n\n### Doc impact\n\n- `spec/c.md` — z.\n"
    plan.write_text(body)
    run("add", "-A")
    run("commit", "-qm", "log Item 3")

    run("mv", "guide/segment_ZZ_demo.md", "guide/archive/segment_ZZ_demo.md")
    run("commit", "-qm", "archive Segment ZZ")

    monkeypatch.setattr(cc._shared, "REPO", root)
    cc._ITEM_START_CACHE.clear()
    yield root
    cc._ITEM_START_CACHE.clear()


def _sweep(root: pathlib.Path) -> str:
    buffer = io.StringIO()
    cc.archived_report(buffer)
    return buffer.getvalue()


def test_the_sweep_reads_every_item_manifest(archive_repo) -> None:
    """The defect itself. Reading only Item 1 gave ``1/1``; all three
    levels give three committed paths, two of them honoured."""
    out = _sweep(archive_repo)
    assert "2/3" in out
    assert "3 live committed paths honoured" in out


def test_the_row_says_how_many_manifests_it_read(archive_repo) -> None:
    """A summed row over 13 manifests is indistinguishable from a row
    over one unless it says so, and the count is the only signal that
    the plan closed item-by-item."""
    assert "3 manifests" in _sweep(archive_repo)


def test_each_item_manifest_takes_its_own_window(archive_repo) -> None:
    """The 19A.2 false pass, at the sweep level. ``spec/c.md`` was edited
    **for Item 1**, before Item 3's heading existed. Passing
    ``item=None`` for every level would open all three windows at the
    first manifest, and Item 3's bullet would read as honoured on Item
    1's edit — so fixing the read without fixing the window would import
    a false pass the close check had already removed.
    """
    out = _sweep(archive_repo)
    assert "1 unhonoured" in out
    assert "2/3" in out


def test_a_guide_path_named_twice_in_one_level_counts_once(
    archive_repo,
) -> None:
    """The footer deduplicates per plan. It is extended one path at a
    time rather than by a comprehension, because a comprehension's
    ``if path not in noted_here`` is evaluated against the list as it
    stood *before* ``+=`` extends it — so a path named twice inside one
    level slips through. That cost exactly one duplicate against the
    real corpus, 64 where 63 was measured.
    """
    plan = archive_repo / "guide" / "archive" / "segment_ZZ_demo.md"
    plan.write_text(
        plan.read_text()
        + "\n## Item 4 — four\n\n### Doc impact\n\n"
        "- `guide/todo_master.md` — tick.\n"
        "- `guide/todo_master.md` — tick again.\n"
    )
    out = _sweep(archive_repo)
    assert "1 guide/ commitment(s)" in out
