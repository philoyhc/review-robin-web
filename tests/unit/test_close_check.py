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
import io
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

    # Segment 19J Item 3 carved the tool into a package, and this one
    # line is the whole cost of it at the test seam. ``REPO`` used to be
    # a module global in the single file, so patching it once reached
    # every reader. It now lives in ``close_check/_shared.py``, and the
    # readers reference it as ``_shared.REPO`` rather than importing the
    # name — because ``from ._shared import REPO`` would bind a *copy*
    # per module and a patch here would silently miss them. One patch
    # point survives the carve; it just moved.
    monkeypatch.setattr(cc._shared, "REPO", root)
    cc._ITEM_START_CACHE.clear()
    cc._COMMIT_CACHE.clear()
    yield plan
    cc._ITEM_START_CACHE.clear()
    cc._COMMIT_CACHE.clear()


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


# --------------------------------------------------------------------
# guide/ commitments, counted and not verified (19K.1)


def _guide(bullet_text: str) -> list[str]:
    """The ``guide/`` paths ``parse_bullets`` collects from one bullet."""
    lines = bullet_text.splitlines()
    bullets = cc.parse_bullets(lines, 0, len(lines))
    return [path for bullet in bullets for path in bullet["guide_paths"]]


def test_a_guide_path_is_collected_rather_than_dropped() -> None:
    """The defect 19K.1 closed. ``COMMITTED_PATH`` matched ``spec/`` and
    ``docs/`` only, so a bullet naming a ``guide/`` file was silently
    dropped: not verified, not counted, not warned about, and the
    printed committed-path count smaller than the manifest just read.
    67 such commitments across 33 plans, none reported.
    """
    assert _guide("- `guide/todo_master.md` — mark 19K.1 done.") == [
        "guide/todo_master.md"
    ]


def test_a_guide_path_is_not_a_committed_path() -> None:
    """The half that makes the count honest. Collecting them must not
    fold them into C2/C3: of the 67, 12 point into ``guide/archive/``
    and 13 at paths since moved there, so C2 would turn 25 correct
    closed commitments into failures.
    """
    bullet = "- `guide/todo_master.md` — mark 19K.1 done."
    assert _paths(bullet) == []
    assert _guide(bullet) == ["guide/todo_master.md"]


def test_a_bullet_names_both_kinds_and_each_lands_in_its_own_list() -> None:
    """The common shape: a doc commitment and a checklist row together."""
    bullet = "- `docs/status.md` — row; `guide/todo_master.md` — tick."
    assert _paths(bullet) == ["docs/status.md"]
    assert _guide(bullet) == ["guide/todo_master.md"]


def test_an_archived_guide_path_is_still_collected() -> None:
    """Why C2 is the wrong question for these, stated as a test: a plan
    file legitimately archives when its segment closes."""
    assert _guide("- `guide/archive/segment_19J_x.md` — cross-ref.") == [
        "guide/archive/segment_19J_x.md"
    ]


def test_a_guide_path_satisfies_a_cites_marker() -> None:
    """C7 asks whether a ``cites:`` names a path its bullet contains.
    Before 19K.1 a ``guide/`` path was invisible to that question, so
    citing one read as stale and C7 failed a correct marker."""
    bullet = (
        "- `docs/README.md` — the `guide/todo_master.md` pointer moves.\n"
        "  <!-- cites: guide/todo_master.md -->"
    )
    assert _bullet(bullet)["cited_absent"] == []


def _checks(plan: pathlib.Path, manifest: str) -> dict[str, dict]:
    """Run the checks over a manifest written into ``plan``'s worktree.

    The ``## Doc impact`` heading is already in ``plan``'s history, which
    is what ``window`` pickaxes for; the bullets under it are read from
    the worktree, so a manifest can be varied without a commit per case.
    """
    plan.write_text("# Segment ZZ\n\n## Doc impact\n\n" + manifest + "\n")
    found = cc.find_manifests(plan.read_text())
    body = cc._section(found["lines"], found["segment"], 2)
    result = cc.check_manifest(plan, found, 2, body, "segment", True)
    return {check["id"]: check for check in result["checks"]}


def test_a_waiver_on_a_guide_only_bullet_still_needs_a_reason(plan_repo) -> None:
    """C4 iterates bullets, not committed paths. A bullet whose only
    path is a ``guide/`` one was invisible to C4 as well — it could be
    waived with an empty reason and nothing said so."""
    checks = _checks(
        plan_repo, "- `guide/todo_master.md` — tick. <!-- doc-impact-waived: -->"
    )
    assert checks["C4"]["status"] == cc.FAIL


def test_a_reasoned_waiver_on_a_guide_only_bullet_passes(plan_repo) -> None:
    """The half that must not regress: widening C4 to every bullet must
    not fail the waivers that do carry a reason."""
    checks = _checks(
        plan_repo,
        "- `guide/todo_master.md` — tick. "
        "<!-- doc-impact-waived: the checklist retired -->",
    )
    assert checks["C4"]["status"] == cc.PASS


def test_c5_lists_the_guide_commitments_without_judging_them(plan_repo) -> None:
    """The status that abstains. C5 names each ``guide/`` path and its
    line, and its status is never FAIL — which is what makes it safe to
    switch on for 33 plans at once without reddening a correct close."""
    checks = _checks(
        plan_repo,
        "- `docs/status.md` — row.\n- `guide/todo_master.md` — tick.",
    )
    assert checks["C5"]["status"] == cc.NOTED
    assert any("guide/todo_master.md" in line for line in checks["C5"]["detail"])
    assert checks["C5"]["status"] != cc.FAIL


def test_c5_is_absent_when_the_manifest_names_no_guide_path(plan_repo) -> None:
    """A check that appears on every plan is noise on the 63 that have
    nothing to say. C5 exists only where there is something to read."""
    assert "C5" not in _checks(plan_repo, "- `docs/status.md` — row.")


def test_a_guide_path_does_not_reach_c2_or_c3(plan_repo) -> None:
    """End to end, over the real check bodies rather than the parser: a
    ``guide/`` path that does not exist and was never edited must not
    fail either check. ``guide/archive/`` is where a quarter of the 67
    live, and C2 would call every one of them missing."""
    checks = _checks(plan_repo, "- `guide/no_such_plan.md` — tick.")
    assert checks["C2"]["status"] == cc.PASS
    assert checks["C3"]["status"] == cc.PASS


# --------------------------------------------------------------------
# an uncommitted item heading (19K.1)


def test_an_uncommitted_item_heading_is_provisional(plan_repo) -> None:
    """The silent pass a stub gets. ``_later_commit`` falls back to the
    segment's own ``Doc impact`` commit when an item's heading is not in
    history, so the item inherits every sibling's edits and C3 reads
    clean. Observed twice on 2026-09-11 — 19J.9 and 19J.10 each reported
    PASS uncommitted and FAIL once their headings landed, and the PASS
    was reported to the author both times.
    """
    plan_repo.write_text(plan_repo.read_text() + "\n## Item 9 — a stub\n")
    _, _, _, provisional = cc.window(plan_repo, 2, item=9)
    assert provisional is True


def test_a_committed_item_heading_is_not_provisional(plan_repo) -> None:
    """The half that must not regress: warning on every item would make
    the warning worth nothing."""
    _, _, _, provisional = cc.window(plan_repo, 2, item=2)
    assert provisional is False


def test_the_segment_level_window_is_never_provisional(plan_repo) -> None:
    """``item=None`` asks no item question, so it cannot answer one."""
    _, _, _, provisional = cc.window(plan_repo, 2)
    assert provisional is False


def test_a_provisional_window_still_starts_at_the_doc_impact_commit(
    plan_repo,
) -> None:
    """The warning says so rather than changing the window. Narrowing it
    instead — to HEAD, say — would turn every stub into a wall of C3
    failures at exactly the moment the author is still drafting."""
    plan_repo.write_text(plan_repo.read_text() + "\n## Item 9 — a stub\n")
    base = cc._first_commit_matching(plan_repo, "^## Doc impact$")
    start, _, _, _ = cc.window(plan_repo, 2, item=9)
    assert start == base[0]


def _report(plan: pathlib.Path, manifest: str) -> str:
    """The printed report for a manifest written into ``plan``.

    Asserted on the text, not on the result dict: the committed total is
    computed in ``report`` itself, so a dict-level assertion passes on
    the very mutation it exists to catch (measured 2026-09-11).
    """
    plan.write_text("# Segment ZZ\n\n## Doc impact\n\n" + manifest + "\n")
    buffer = io.StringIO()
    cc.report(cc.run("ZZ", None), buffer)
    return buffer.getvalue()


def test_the_committed_total_includes_the_guide_paths(plan_repo) -> None:
    """The Definition of done's own measure: 19J.7's five-bullet manifest
    read ``3 committed path(s)`` and exited 0. Counted and verified are
    separate axes; the total counts, and C5 says what is not verified."""
    out = _report(
        plan_repo, "- `spec/a.md` — x.\n- `guide/todo_master.md` — tick."
    )
    assert "2 committed path(s), 1 noted," in out


def test_a_manifest_with_no_guide_path_prints_no_noted_clause(plan_repo) -> None:
    """The half that keeps 54 of the 85 plans byte-identical: the clause
    appears only where there is something to say."""
    out = _report(plan_repo, "- `spec/a.md` — x.")
    assert "1 committed path(s), 0 waived," in out
    assert "noted" not in out


def test_a_waived_guide_bullet_counts_as_waived(plan_repo) -> None:
    """Consistency with the total above. Excluding them printed
    ``5 committed path(s), 0 waived`` for a manifest whose own C5 lines
    marked one of the five waived."""
    plan_repo.write_text(
        "# Segment ZZ\n\n## Doc impact\n\n"
        "- `guide/todo_master.md` — tick. "
        "<!-- doc-impact-waived: the checklist retired -->\n"
    )
    assert cc.run("ZZ", None)["levels"][0]["waived"] == ["guide/todo_master.md"]
