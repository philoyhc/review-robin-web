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
    # Committed in the same commit as the manifest and never touched
    # again: the boundary case (19G.6).
    (root / "spec" / "b.md").write_text("landed with the manifest\n")
    plan.write_text(
        "# Segment ZZ\n\n## Doc impact\n\n"
        "- `spec/a.md` — x (Item 1).\n- `spec/b.md` — y.\n"
    )
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


def test_the_commit_that_records_the_commitment_can_also_honour_it(
    plan_repo,
) -> None:
    """The boundary the window used to drop (19G.6).

    ``spec/b.md`` is written in the same commit as the manifest and
    never again — the manifest and the doc edit landing together. Under
    ``git log start..end`` that commit is excluded and the bullet reads
    as unhonoured, which is range arithmetic rather than a rule:
    nowhere else does C3 ask *when* in the window an edit fell. Measured
    over the 99 plans it cost 6 of 22 C3 failures, every one of them a
    same-commit landing.
    """
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    assert cc.honoured("spec/b.md", base[0], "HEAD") is not None


def test_a_path_the_window_never_touched_is_still_unhonoured(
    plan_repo,
) -> None:
    """The half that must not regress: including the start commit must
    not make every path pass. ``spec/c.md`` exists in no commit."""
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    assert cc.honoured("spec/c.md", base[0], "HEAD") is None


def test_an_edit_before_the_window_opens_is_still_outside_it(
    plan_repo,
) -> None:
    """Including the start commit widens the window at its *start* only,
    by one commit. ``spec/b.md`` was written before Item 3's heading
    existed, so Item 3's bullet cannot claim it."""
    item3 = cc.item_heading_start(plan_repo, 3)
    assert cc.honoured("spec/b.md", item3[0], "HEAD") is None


# --------------------------------------------------------------------
# root-level and bare-filename manifest paths (19G.4)


def _paths(bullet_text: str) -> list[str]:
    """The committed paths ``parse_bullets`` extracts from one bullet."""
    lines = bullet_text.splitlines()
    bullets = cc.parse_bullets(lines, 0, len(lines))
    return [path for bullet in bullets for path in bullet["paths"]]


def test_a_root_level_document_is_a_committed_path() -> None:
    """The gap this closed: ``COMMITTED_PATH`` matched ``spec/`` and
    ``docs/`` only, so a manifest committing to ``constitution.md`` had
    that bullet silently dropped — not verified, and a waiver on it not
    counted. 19G.1 committed to a ``constitution.md`` edit and the tool
    reported four committed paths against a five-bullet manifest.
    """
    assert _paths("- `constitution.md` — VI gains a pointer.") == ["constitution.md"]


def test_a_bare_filename_resolves_to_the_folder_that_holds_it() -> None:
    """Two of the 99 plans use a bare name as shorthand for a spec.
    Resolution reads the filesystem — root, then ``spec/``, then
    ``docs/`` — so there is no list to maintain."""
    assert _paths("- `architecture.md` — the module map.") == ["spec/architecture.md"]


def test_a_bare_name_after_the_dash_is_prose_not_a_commitment() -> None:
    """The reason bare names are matched in the leading position only.

    Measured over the 99 plans: matching them anywhere counted five
    passing mentions as commitments and flipped one archived plan to
    FAIL — 19E's ``docs/README.md`` bullet *describes* ``quickstart.md``
    retiring, and the tool would have demanded the retired file still
    exist.
    """
    bullet = "- `docs/README.md` — `quickstart.md` retires to `docs/archive/`."
    assert _paths(bullet) == ["docs/README.md"]


def test_a_prefixed_path_after_the_dash_is_still_a_commitment() -> None:
    """The asymmetry is deliberate, and this is the half that must not
    regress: bullets legitimately commit to several specs in their
    description ("Per-Part spec docs as the scope settles — A, B, C"),
    and a head-only rule would have dropped seven such commitments
    across the archived plans."""
    bullet = (
        "- Per-Part spec docs as the scope settles — `spec/assignments.md` "
        "(Part 1), `spec/csv_contracts.md` (Part 2)."
    )
    assert _paths(bullet) == ["spec/assignments.md", "spec/csv_contracts.md"]


def test_an_unresolvable_bare_name_is_reported_as_written() -> None:
    """C2 should name the string the author wrote, not a guess at what
    they meant — otherwise its message points at a file nobody typed."""
    assert _paths("- `no_such_document.md` — nothing.") == ["no_such_document.md"]
# --------------------------------------------------------------------
# cited paths (19G.8)


def _bullet(text: str) -> dict:
    lines = text.splitlines()
    return cc.parse_bullets(lines, 0, len(lines))[0]


def test_a_cited_path_is_not_a_commitment() -> None:
    """The defect: `COMMITTED_PATH` matches a prefixed path anywhere in
    the bullet, so a bullet describing an edit *to a pointer* commits the
    item to editing the pointer's target. It bit two manifests in this
    segment, each worked around by dropping the backticks — distorting
    the prose to satisfy the checker, against `CLAUDE.md`'s "backtick
    every path".
    """
    bullet = (
        "- `docs/unenforced_conventions.md` — §2.1's `spec/architecture.md`\n"
        "  pointer names the section rather than numbering it.\n"
        "  <!-- cites: spec/architecture.md -->"
    )
    assert _bullet(bullet)["paths"] == ["docs/unenforced_conventions.md"]


def test_without_the_marker_the_cited_path_still_counts() -> None:
    """The half that must not regress. A prefixed path after the dash is
    a commitment by default — bullets legitimately commit to several
    specs there, and a head-only rule for every path loses seven such
    commitments across the archived plans (19G.4). The marker is opt-in
    precisely because the default is right more often than not."""
    bullet = (
        "- `docs/unenforced_conventions.md` — §2.1's `spec/architecture.md`\n"
        "  pointer names the section rather than numbering it."
    )
    assert _bullet(bullet)["paths"] == [
        "docs/unenforced_conventions.md",
        "spec/architecture.md",
    ]


def test_cites_takes_several_paths() -> None:
    """19G.5's bullet cited two: the wrong file and the right one."""
    bullet = (
        "- `spec/operator_button_audit.md` — row #155 repointed from\n"
        "  `spec/visual_style_rrw.md` to `spec/ui_elements.md`.\n"
        "  <!-- cites: spec/visual_style_rrw.md, spec/ui_elements.md -->"
    )
    assert _bullet(bullet)["paths"] == ["spec/operator_button_audit.md"]


def test_a_cites_naming_a_path_the_bullet_lacks_is_reported() -> None:
    """C7's input. An escape that covers nothing is stale in the
    direction nobody notices: the suite stays green while the marker
    quietly excuses a path that is no longer in the bullet, and the next
    path added under that name is silently uncommitted."""
    bullet = (
        "- `docs/x.md` — a change.\n"
        "  <!-- cites: spec/architecture.md -->"
    )
    parsed = _bullet(bullet)
    assert parsed["paths"] == ["docs/x.md"]
    assert parsed["cited_absent"] == ["spec/architecture.md"]


def test_a_cites_that_covers_a_real_path_is_not_reported_as_absent() -> None:
    """The other direction of C7: a live marker must not read as stale,
    or the check would fail every correct use of the escape it defines."""
    bullet = (
        "- `docs/x.md` — the `spec/architecture.md` pointer moves.\n"
        "  <!-- cites: spec/architecture.md -->"
    )
    assert _bullet(bullet)["cited_absent"] == []
