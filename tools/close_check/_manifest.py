"""The per-segment close check — C1 through C7.

``close_check.py <id>`` resolves a plan, reads the ``Doc impact``
manifest at the closing level, and asks of every committed path
whether it was edited inside the segment's window. The reasoning —
why a bullet is dated from its own item heading, why an edit
predating that heading warns rather than fails, why a bare root-level
filename counts only in the leading position — is in the package
docstring (``tools/close_check/__init__.py``), which is where it was
before Segment 19J Item 3 carved this module out.

This module is the bulk of the tool: 680 of its 1,000 lines. The
carve did not shrink it; it separated the two smaller jobs that were
sharing its file.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

from . import _shared
from ._shared import Unresolvable, _git


# A committed path: backticked, ending .md, under spec/ or docs/. The
# trailing [^`]* absorbs a section reference written inside the ticks
# (`docs/setup.md §4c`, `spec/x.md#anchor`). Matched anywhere in the
# bullet, because bullets legitimately commit to several specs in their
# description ("Per-Part spec docs as the scope settles — A, B, C").
COMMITTED_PATH = re.compile(r"`((?:spec|docs)/[A-Za-z0-9._/-]+\.md)[^`]*`")

# A `guide/` commitment. Counted and listed, never verified — which is a
# decision about what this tool can honestly say, not an omission.
#
# It was invisible until 2026-09-11 (19K.1): `COMMITTED_PATH` matched
# `spec/` and `docs/` only, so a bullet naming a `guide/` file was
# silently dropped — not reported as unchecked, not counted, not warned
# about, and the printed committed-path count was quietly smaller than
# the manifest it had just read. This parser finds **80 such commitments
# across 35 plans**, none of them reported before 19K.1. Two went
# unhonoured in Segment 19J alone and nothing failed; both were caught by
# a person reading the manifests at close, which is the control this tool
# exists to replace.
#
# (19K.1's plan opened with a hand-parsed 67 across 33. The two counts
# are not reconciled and the plan keeps its figure; this comment carries
# the parser's, because a comment on the regex should state what the
# regex finds.)
#
# Why counted-but-not-verified rather than checked like a spec:
#
#   * A `guide/` commitment is typically "add a row to a checklist", and
#     no diff-shaped check can confirm the row was the *right* one. C3
#     would pass on "the file was touched", which for a shared checklist
#     is nearly always true for unrelated reasons —
#     `post_azure_todo_checklist.md` was edited three times on
#     2026-09-11 for three different items. A check that passes for the
#     wrong reason is worse than one that abstains.
#   * C2 ("exists and is live") is the wrong question too. A plan file
#     legitimately archives when its segment closes, so a bullet naming
#     it goes stale by the segment closing correctly. Measured over the
#     80: **11 have no file at the path the bullet names, and 8 of those
#     are exactly that case** — the file is sitting in `guide/archive/`.
#     Three are genuinely gone. So C2 would fail eight correct, closed
#     commitments to catch three, and would do it across `--archived`,
#     which sweeps every archived plan.
#
# So the tool reports them and says it is not checking them. The reader
# closes that loop, exactly as they already do for a C3 warning.
GUIDE_PATH = re.compile(r"`(guide/[A-Za-z0-9._/-]+\.md)[^`]*`")

# A bare filename, matched **only in the bullet's leading position** —
# before the em-dash that separates the path from its description.
#
# Root-level documents were invisible to this tool until 2026-09-08
# (19G.4): a manifest committing to `constitution.md`, `CLAUDE.md` or
# `rrw_sdd_in_practice.md` had that bullet silently dropped, so the
# check that asks whether promised doc edits happened had a scope
# narrower than the manifests it validated. 19G.1 committed to a
# `constitution.md` edit and this tool reported four committed paths
# against a five-bullet manifest.
#
# Leading position only, because a bare name is ambiguous in a way a
# prefixed path is not, and the description half is where prose mentions
# live. Measured over the 99 plans: matching bare names anywhere would
# have counted five passing mentions as commitments and flipped one
# archived plan to FAIL on a `quickstart.md` that its bullet merely
# described retiring. Restricted to the head, it counts six names, five
# of them real commitments no previous run could see.
COMMITTED_BARE = re.compile(r"`([A-Za-z0-9._-]+\.md)[^`]*`")

# A commitment to a path outside `spec/` and `docs/` — `tools/README.md`,
# `.claude/skills/segment-plan/SKILL.md`, a workflow, a package. Matched in
# the **leading position only**, exactly as bare root-level names are
# (19G.4), and for the same reason, measured rather than assumed.
#
# Of the 16 such paths across every live and archived plan (2026-09-11),
# only **3 sit in the leading position**. The other 13 are *citations*: the
# bullet commits to a `spec/` file and names a code path as the content of
# the edit — "name the `app/services/assignments/` package, not the retired
# module path", "one sentence, new routing modules must be registered in
# `app/web/spec_registry.py`". Matching anywhere would convert all 13 into
# commitments the author never made, and one of them
# (`tests/integration/test_extracts_round_trip.py`) no longer exists, so C2
# would fail an archived plan that did nothing wrong.
#
# The root list is explicit rather than "any path that resolves on disk",
# which is how bare names work: resolution-on-disk would make a *deleted*
# path silently stop being a commitment, which is precisely what C2 exists
# to catch.
# At least one character after the root's slash. A bare `` `tools/` `` is a
# folder named in prose — "the `tools/` and `.claude/` paths the regex never
# matched" — not a path, and `*` matched four of those across the archive.
# Harmless while they all sat after the dash, and a commitment to an entire
# top-level directory the first time one led a bullet. A trailing-slash
# *path* still matches: `.github/workflows/` has `workflows/` after the root.
#
# Found because the published count (16 paths, 3 leading, 13 citations) did
# not reproduce against the shipped regex, which gave 20/3/17. The prose was
# right and the code was wrong — the four extra were these.
COMMITTED_ROOT = re.compile(
    r"`((?:app|tests|tools|alembic|\.github|\.claude)/[A-Za-z0-9._/-]+)[^`]*`"
)

# The em-dash (or en-dash) that ends a manifest bullet's path list.
BULLET_HEAD = re.compile(r"\s[\u2014\u2013]\s")


def resolve_committed(path: str) -> str:
    """Resolve a bare filename to a repo-relative path.

    A bullet may name a root-level document, or use a bare filename as
    shorthand for one under ``spec/`` or ``docs/``. Resolution order is
    root, then ``spec/``, then ``docs/``, read from the filesystem so
    there is no list to maintain and no way for it to go stale.

    An unresolvable name is returned unchanged, so C2 reports the string
    the author actually wrote rather than a guess about what they meant.
    """
    if "/" in path:
        return path
    for candidate in (path, f"spec/{path}", f"docs/{path}"):
        if (_shared.REPO / candidate).is_file():
            return candidate
    return path


WAIVER = re.compile(r"<!--\s*doc-impact-waived:(.*?)-->", re.DOTALL)

# A path a bullet *cites* rather than commits to. `COMMITTED_PATH` matches
# a prefixed path anywhere in the bullet, deliberately — bullets
# legitimately commit to several specs after the dash, and a head-only
# rule loses seven such commitments (19G.4's measurement). The cost is
# that a bullet describing an edit *to a pointer* names its target, and
# the target reads as a commitment the item never made. Both escapes were
# bad: waive it (the waiver is per-bullet and would waive the real
# commitment too) or drop the backticks (which distorts the prose to
# satisfy the checker, against `CLAUDE.md`'s "backtick every path").
# So the author says which, once, in the bullet:
#
#     - `docs/x.md` — §2.1's `spec/architecture.md` pointer is renamed.
#       <!-- cites: spec/architecture.md -->
#
# Comma-separated, repo-relative, matched anywhere in the bullet. C7
# fails a `cites:` naming a path the bullet does not contain, so the
# escape cannot outlive its reason or quietly become a blanket.
CITES = re.compile(r"<!--\s*cites:(.*?)-->", re.DOTALL)
ITEM_HEADING = re.compile(r"^## Item (\d+)\b")
# An "(Item n)" ownership tag on a segment-level manifest bullet. The
# parenthetical must *begin* with the item reference (after an optional
# "done —"), which is every form in use across the 96 plans — "(Item 1)",
# "(Item 2, on wiring)", "(done — Item 3)" — and excludes the prose
# references that share the words: "(18S Item 3)" points at another
# segment's item, "(footgun from Item 1)" and "(Slice 1 of Item 4)" are
# commentary. A bullet naming two items carries two parentheticals
# (`18R`'s `docs/status.md`), not one listing both.
ITEM_TAG = re.compile(r"\((?:done\s*[—–-]\s*)?(Items?\s+\d+[^)]*)\)")
ITEM_TAG_NUMBER = re.compile(r"\bItem\s+(\d+)")
SEGMENT_ID = re.compile(r"^([A-Za-z0-9]+)(?:\.(\d+))?$")

PASS, FAIL, WARN, SKIP = "pass", "fail", "warn", "skip"
# Counted, listed, and deliberately not judged. Never affects the exit
# code: `report()` fails only on FAIL, so a NOTED line can never turn a
# correct close red — which is what makes it safe to switch on for 33
# plans at once.
NOTED = "noted"

# --------------------------------------------------------------------
# resolution


def resolve_plan(segment: str) -> pathlib.Path:
    """`18R` -> guide/segment_18R_ux_refine.md (live dir, then archive).

    Matches `segment_<id>.md` and `segment_<id>_<slug>.md` exactly, so
    `04` does not resolve to `segment_04A.md`.
    """
    candidates = [
        path
        for directory in (_shared.REPO / "guide", _shared.REPO / "guide" / "archive")
        for path in sorted(directory.glob(f"segment_{segment}*.md"))
        if path.stem == f"segment_{segment}"
        or path.stem.startswith(f"segment_{segment}_")
    ]
    if not candidates:
        raise Unresolvable(f"no plan file for segment {segment!r} in guide/")
    if len({p.name for p in candidates}) > 1:
        names = ", ".join(sorted(p.name for p in candidates))
        raise Unresolvable(f"segment {segment!r} is ambiguous: {names}")
    return candidates[0]


def parse_id(raw: str) -> tuple[str, int | None]:
    match = SEGMENT_ID.match(raw)
    if not match:
        raise Unresolvable(
            f"{raw!r} is not a segment id — expected e.g. 18R or 19A.3"
        )
    segment, item = match.groups()
    return segment, int(item) if item else None


# --------------------------------------------------------------------
# manifest parsing


def _section(lines: list[str], start: int, depth: int) -> tuple[int, int]:
    """Body of the heading at `start`, ending at the next heading <= depth."""
    for offset in range(start + 1, len(lines)):
        stripped = lines[offset].lstrip("#")
        level = len(lines[offset]) - len(stripped)
        if 0 < level <= depth and lines[offset].startswith("#"):
            return start + 1, offset
    return start + 1, len(lines)


def find_manifests(text: str) -> dict[str, object]:
    """Locate every `Doc impact` heading, exactly matched, by level."""
    lines = text.splitlines()
    segment_line = None
    items: dict[int, dict[str, int | None]] = {}
    current_item = None

    for number, line in enumerate(lines):
        item_match = ITEM_HEADING.match(line)
        if item_match:
            current_item = int(item_match.group(1))
            items[current_item] = {"heading": number, "doc": None, "status": None}
        elif line == "## Doc impact":
            segment_line = number
            current_item = None
        elif line == "### Doc impact" and current_item is not None:
            items[current_item]["doc"] = number
        elif line.startswith("### Status") and current_item is not None:
            items[current_item]["status"] = number

    has_segment_status = any(line.startswith("## Status") for line in lines)
    # A "### Doc impact" outside any "## Item n" block still counts as a
    # second shape — 11E has one under a "## Follow-on" heading.
    stray = [
        n
        for n, line in enumerate(lines)
        if line == "### Doc impact"
        and n not in {i["doc"] for i in items.values() if i["doc"] is not None}
    ]
    return {
        "lines": lines,
        "segment": segment_line,
        "items": items,
        "stray": stray,
        "segment_status": has_segment_status,
    }


def _all_paths(bullet: dict) -> list[str]:
    """Every path the bullet names, before `cites:` removes any."""
    head = BULLET_HEAD.split(bullet["text"], maxsplit=1)[0]
    # `COMMITTED_ROOT` over the **whole** text, not the head, even though
    # only the head makes a commitment. This function answers "does the
    # bullet name this path at all", which is C7's question, and the 13
    # after-dash citations are precisely the ones an author would mark
    # `cites:`. Head-only here would fail C7 on every correct use of the
    # escape for a root path — the escape unusable exactly where it is
    # needed.
    return [
        resolve_committed(raw)
        for raw in COMMITTED_PATH.findall(bullet["text"])
        + COMMITTED_BARE.findall(head)
        + COMMITTED_ROOT.findall(bullet["text"])
    ] + GUIDE_PATH.findall(bullet["text"])


def parse_bullets(lines: list[str], start: int, end: int) -> list[dict]:
    """Split a manifest body into bullets; a bullet may wrap over lines."""
    bullets: list[dict] = []
    for number in range(start, end):
        line = lines[number]
        if line.lstrip().startswith(("- ", "* ")) and not line.startswith("  "):
            bullets.append({"line": number + 1, "text": line})
        elif bullets and line.strip() and not line.startswith("#"):
            bullets[-1]["text"] += "\n" + line
    for bullet in bullets:
        # One waiver covers every path in its bullet: bullets legitimately
        # carry more than one path (segment 18R lists two per bullet).
        waiver = WAIVER.search(bullet["text"])
        bullet["waived"] = waiver is not None
        bullet["reason"] = waiver.group(1).strip() if waiver else None
        cited = [
            name.strip()
            for marker in CITES.findall(bullet["text"])
            for name in marker.split(",")
            if name.strip()
        ]
        bullet["cites"] = cited
        seen: list[str] = []
        head = BULLET_HEAD.split(bullet["text"], maxsplit=1)[0]
        for raw in (COMMITTED_PATH.findall(bullet["text"])
                    + COMMITTED_BARE.findall(head)
                    + COMMITTED_ROOT.findall(head)):
            path = resolve_committed(raw)
            if path not in seen and path not in cited:
                seen.append(path)
        bullet["paths"] = seen
        guide_seen: list[str] = []
        for raw in GUIDE_PATH.findall(bullet["text"]):
            if raw not in guide_seen and raw not in cited:
                guide_seen.append(raw)
        bullet["guide_paths"] = guide_seen
        bullet["cited_absent"] = [
            name for name in cited if name not in seen and name not in _all_paths(bullet)
        ]
        bullet["items"] = sorted({
            int(number)
            for tag in ITEM_TAG.findall(bullet["text"])
            for number in ITEM_TAG_NUMBER.findall(tag)
        })
    return bullets


# --------------------------------------------------------------------
# window


def pre_archive_path(plan: pathlib.Path) -> str:
    relative = plan.relative_to(_shared.REPO).as_posix()
    return relative.replace("guide/archive/", "guide/")


# Memoised because `--archived` asks the same question once per manifest
# level, and a plan has as many levels as it has items: `19I` ran the
# identical `^## Doc impact$` pickaxe 13 times.
#
# Measured over the 98 archived plans (2026-09-11), reading every level
# (19K.4) took `--archived` from 258 `git log` calls / 5.9s to 491 / 17.8s.
# Memoisation brings it to **417 / 11.3s** — 15% fewer calls for 37% less
# time, because the calls it removes are the `-G` pickaxes, which scan a
# file's whole history, rather than the cheap ranged lookups.
#
# The rest of the gap over 5.9s is not waste: 274 paths are now checked
# where 162 were, and each one is a `git log` that has to happen. Reading
# more evidence costs more.
#
# Keyed on the plan path and the pattern, both of which fully determine
# the answer for a given tree.
_COMMIT_CACHE: dict[tuple[str, str], list[str] | None] = {}


def _first_commit_matching(plan: pathlib.Path, pattern: str) -> list[str] | None:
    """[sha, date] of the first commit adding a line matching `pattern`.

    Searched on the pre-archive path first, never with ``--follow``, per the
    window rules in this module's docstring.
    """
    key = (plan.as_posix(), pattern)
    if key in _COMMIT_CACHE:
        return _COMMIT_CACHE[key]
    _COMMIT_CACHE[key] = _uncached_first_commit_matching(plan, pattern)
    return _COMMIT_CACHE[key]


def _uncached_first_commit_matching(
    plan: pathlib.Path, pattern: str
) -> list[str] | None:
    for candidate in dict.fromkeys(
        [pre_archive_path(plan), plan.relative_to(_shared.REPO).as_posix()]
    ):
        found = [
            row for row in _git(
                "log", "--reverse", "--format=%H %ad", "--date=short",
                "-G", pattern, "--", candidate,
            ).split("\n") if row.strip()
        ]
        if found:
            return found[0].split(" ", 1)
    return None


def _later_commit(a: list[str] | None, b: list[str] | None) -> list[str] | None:
    """Whichever of two commits comes later in history."""
    if a is None or b is None:
        return a or b
    if a[0] == b[0]:
        return a
    # Ancestry is the honest ordering; dates can tie or run backwards.
    if subprocess.run(
        ["git", "-C", str(_shared.REPO), "merge-base", "--is-ancestor", a[0], b[0]]
    ).returncode == 0:
        return b
    return a


_ITEM_START_CACHE: dict[tuple[str, int], list[str] | None] = {}


def item_heading_start(plan: pathlib.Path, number: int) -> list[str] | None:
    """[sha, date] of the commit that added ``## Item <n>`` to this plan."""
    key = (plan.as_posix(), number)
    if key not in _ITEM_START_CACHE:
        _ITEM_START_CACHE[key] = _first_commit_matching(
            plan, f"^## Item {number} "
        )
    return _ITEM_START_CACHE[key]


def bullet_window_start(
    plan: pathlib.Path, base: list[str] | None, items: list[int]
) -> list[str] | None:
    """Window start for one segment-level bullet.

    The later of the segment window and the `## Item n` heading of each
    item the bullet is tagged with; the latest, for a bullet naming two.
    Why this exists and why it only warns: module docstring, "The
    window".
    """
    start = base
    for number in items:
        start = _later_commit(start, item_heading_start(plan, number))
    return start


def window(
    plan: pathlib.Path, depth: int, item: int | None = None
) -> tuple[str | None, str, str | None, bool]:
    """(start commit, end commit, start date, provisional) for the level.

    For an item, the window opens at the later of the ``### Doc impact``
    heading and that item's own ``## Item <n>`` heading. The heading
    pickaxe alone is not enough once a file carries more than one item:
    every item would inherit the *first* item's start, and a path another
    item had edited would read as honoured. That was a live false pass —
    ``19A.2`` reported C3 pass on Item 3's ``docs/status.md`` row (fixed
    2026-09-05, Segment 19A Item 2 PR 2).
    """
    relative = plan.relative_to(_shared.REPO).as_posix()
    archived = "guide/archive/" in relative

    start = _first_commit_matching(
        plan, "^" + ("###" if depth == 3 else "##") + " Doc impact$"
    )
    provisional = False
    if item is not None:
        heading = _first_commit_matching(plan, f"^## Item {item} ")
        # An item heading that is not yet in history leaves `_later_commit`
        # returning the segment's own `Doc impact` commit, so the item
        # inherits every sibling's edits and C3 reads clean. That is
        # exactly the state a stub is in when its author runs this check
        # on it: observed twice on 2026-09-11, where 19J.9's and 19J.10's
        # stubs each reported PASS uncommitted and FAIL once their
        # headings landed — and the PASS was reported to the author both
        # times before being corrected. Say so rather than pass quietly.
        provisional = heading is None and start is not None
        start = _later_commit(start, heading)

    if archived:
        # Same memoisation, same reason: one question per plan, asked once
        # per manifest level. The `A:` prefix keeps it out of the pickaxe
        # keyspace, since the value means something different.
        key = (plan.as_posix(), "A:" + relative)
        if key not in _COMMIT_CACHE:
            _COMMIT_CACHE[key] = [
                row for row in _git(
                    "log", "--diff-filter=A", "--format=%H", "--", relative
                ).split("\n") if row.strip()
            ]
        adds = _COMMIT_CACHE[key]
        end = adds[0] if adds else "HEAD"
    else:
        end = "HEAD"

    return (start[0] if start else None, end, start[1] if start else None, provisional)


def honoured(path: str, start: str, end: str) -> str | None:
    """Last commit date touching `path` in [start, end], or None.

    The start commit counts. It is the commit that *recorded* the
    commitment, so an edit inside it is the manifest and the doc edit
    landing together — the commitment kept in one commit rather than
    two. Excluding it was range arithmetic (``git log A..B`` drops
    ``A``), not a rule: nowhere else does C3 ask when in the window an
    edit fell, and a boundary edit is the same evidence as any other.
    """
    out = _git(
        "log", "--no-merges", "--format=%ad", "--date=short",
        f"{start}..{end}", "--", path,
    ).split("\n")
    dates = [row for row in out if row.strip()]
    if dates:
        return dates[0]
    # `start^!` is the start commit with its parents excluded — the one
    # commit, whether or not it has a parent. `--no-merges` keeps a merge
    # start (which the `-G` pickaxe cannot return anyway) reading as it
    # did before.
    return _git(
        "log", "--no-merges", "--format=%ad", "--date=short",
        f"{start}^!", "--", path,
    ).strip() or None


def last_touched_ever(path: str) -> str | None:
    out = _git("log", "-1", "--format=%ad", "--date=short", "--", path).strip()
    return out or None


# --------------------------------------------------------------------
# coverage note (informational; never affects exit status)


NOTE_CAP = 6


def coverage_note(start: str | None, end: str, committed: set[str]) -> list[str]:
    """Routing modules the window touched whose spec the plan didn't name.

    Informational, and deliberately not a check: a segment can touch a
    module without changing the contract its spec describes. It is here
    because the manifest is written at planning time and the code moves
    after — this is the cheapest place to notice a surface the plan did
    not think it would reach. Capped, because a broad segment touches
    many modules and the checks must stay readable.
    """
    if start is None:
        return []
    try:
        sys.path.insert(0, str(_shared.REPO))
        from app.web.spec_registry import SPEC_COVERAGE
    except Exception:  # pragma: no cover - the note is optional
        return []

    changed = [
        row for row in _git(
            "diff", "--name-only", f"{start}..{end}"
        ).split("\n") if row.strip().startswith("app/web/routes") and row.endswith(".py")
    ]
    notes = []
    for path in sorted(set(changed)):
        module = path[: -len(".py")].replace("/", ".")
        unnamed = [s for s in SPEC_COVERAGE.get(module, ()) if s not in committed]
        if unnamed:
            notes.append(
                f"{module.split('.')[-1]} touched; not in manifest: "
                + ", ".join(unnamed)
            )
    if len(notes) > NOTE_CAP:
        extra = len(notes) - NOTE_CAP
        notes = notes[:NOTE_CAP] + [f"... and {extra} more touched module(s)"]
    return notes


# --------------------------------------------------------------------
# the checks


def check_manifest(
    plan: pathlib.Path, found: dict, depth: int, body: tuple[int, int], label: str,
    status_present: bool, item: int | None = None,
) -> dict:
    lines = found["lines"]
    bullets = parse_bullets(lines, *body)
    start, end, start_date, provisional = window(plan, depth, item)

    base = [start, start_date] if start else None
    committed: list[dict] = []
    for bullet in bullets:
        # Item tags only bind a segment-level manifest; an item-level one
        # is already anchored on its own heading by window().
        tagged = bullet["items"] if depth == 2 else []
        entry_start = bullet_window_start(plan, base, tagged) if tagged else base
        for path in bullet["paths"]:
            committed.append(
                {
                    "path": path,
                    "line": bullet["line"],
                    "waived": bullet["waived"],
                    "reason": bullet["reason"],
                    "items": tagged,
                    "start": entry_start[0] if entry_start else None,
                    "start_date": entry_start[1] if entry_start else None,
                }
            )

    checks: list[dict] = []

    # C2 — every committed path exists, and is not archived.
    c2 = []
    for entry in committed:
        if "archive/" in entry["path"]:
            c2.append(f"{entry['path']} is archived (line {entry['line']})")
        # `exists`, not `is_file`: a manifest legitimately commits to a
        # directory — `.github/workflows/` in 18Q, `app/services/assignments/`
        # in 19C — and `is_file` called every one of them missing. Invisible
        # until 19K.5 made such paths commitments in the first place.
        elif not (_shared.REPO / entry["path"]).exists():
            c2.append(f"{entry['path']} does not exist (line {entry['line']})")
    checks.append({
        "id": "C2", "what": "committed paths exist and are live",
        "status": FAIL if c2 else PASS, "detail": c2,
    })

    # C3 — every un-waived path modified in the window.
    c3, c3_warn, honoured_count, checked = [], [], 0, 0
    if start is None:
        checks.append({
            "id": "C3", "what": "paths modified in window",
            "status": WARN,
            "detail": [f"no window: '{label}' heading never appears in the plan's history"],
        })
    else:
        for entry in committed:
            if entry["waived"] or not (_shared.REPO / entry["path"]).exists():
                continue
            checked += 1
            entry_start = entry["start"] or start
            if honoured(entry["path"], entry_start, end):
                honoured_count += 1
                continue
            # Fall back to the segment window: an edit inside it but
            # before this item's heading is ambiguous, not absent.
            if entry["items"] and honoured(entry["path"], start, end):
                honoured_count += 1
                c3_warn.append(
                    f"{entry['path']} was edited in the segment window but "
                    f"before Item {max(entry['items'])} existed "
                    f"({entry['start_date']}) — either the item was logged "
                    f"after its work landed, or this is another item's edit "
                    f"(line {entry['line']})"
                )
                continue
            ever = last_touched_ever(entry["path"]) or "never"
            c3.append(
                f"{entry['path']} not modified in window "
                f"(last modified {ever}, line {entry['line']})"
            )
        if provisional:
            c3_warn.append(
                f"Item {item}'s heading is not committed yet, so the window "
                "starts at the segment's own Doc impact and this item can "
                "read clean on a sibling's edits — provisional until the "
                "heading lands"
            )
        checks.append({
            "id": "C3", "what": "paths modified in window",
            "status": FAIL if c3 else (WARN if c3_warn else PASS),
            "detail": c3 + c3_warn,
        })

    # C4 — every waiver reasoned.
    # Bullets, not paths: a waiver is per-bullet, and a bullet whose only
    # path is a `guide/` one still needs its reason.
    c4 = [
        f"line {bullet['line']}: waiver has no reason"
        for bullet in bullets
        if bullet["waived"]
        and not bullet["reason"]
        and (bullet["paths"] or bullet["guide_paths"])
    ]
    checks.append({
        "id": "C4", "what": "waivers carry a reason",
        "status": FAIL if c4 else PASS, "detail": c4,
    })

    # C5 — guide/ commitments, counted and named, not verified.
    noted = [
        {
            "path": path,
            "line": bullet["line"],
            "waived": bullet["waived"],
        }
        for bullet in bullets
        for path in bullet["guide_paths"]
    ]
    if noted:
        checks.append({
            "id": "C5",
            "what": "guide/ commitments (counted, not verified)",
            "status": NOTED,
            "detail": [
                f"{entry['path']}"
                + (" (waived)" if entry["waived"] else "")
                + f" (line {entry['line']})"
                for entry in noted
            ],
        })

    # C6 — Status block at the closing level. Warn only in v1.
    checks.append({
        "id": "C6", "what": "Status block present",
        "status": PASS if status_present else WARN,
        "detail": [] if status_present else [f"no Status block at {label} level"],
    })

    # C7 — every `cites:` names a path its bullet actually contains.
    # Both directions, like the doc-conventions markers: an escape that
    # covers nothing is stale in the way nobody notices, because the
    # suite stays green while the marker quietly excuses a path that is
    # no longer there.
    c7 = [
        f"line {bullet['line']}: cites `{name}`, which the bullet does not name"
        for bullet in bullets
        for name in bullet["cited_absent"]
    ]
    checks.append({
        "id": "C7", "what": "every cites: names a path in its bullet",
        "status": FAIL if c7 else PASS, "detail": c7,
    })

    return {
        "level": label,
        "window": {"start": start, "start_date": start_date, "end": end},
        "paths": [entry["path"] for entry in committed],
        "noted": [entry["path"] for entry in noted],
        # `guide/` waivers count here too. The total above includes
        # them, so excluding them would print "5 committed path(s),
        # 0 waived" for a manifest whose C5 lines say otherwise.
        "waived": [e["path"] for e in committed if e["waived"]]
        + [e["path"] for e in noted if e["waived"]],
        "honoured": honoured_count,
        "checked": checked,
        "checks": checks,
        "coverage_note": coverage_note(
            start, end, {entry["path"] for entry in committed}
        ),
    }


def run(segment: str, item: int | None) -> dict:
    plan = resolve_plan(segment)
    found = find_manifests(plan.read_text())
    lines = found["lines"]
    relative = plan.relative_to(_shared.REPO).as_posix()

    has_segment = found["segment"] is not None
    item_docs = {n: i["doc"] for n, i in found["items"].items() if i["doc"] is not None}
    has_items = bool(item_docs)

    # C1 — present at the level, one shape.
    c1: list[str] = []
    if has_segment and (has_items or found["stray"]):
        c1.append(
            "two manifest shapes in one file: a segment-level '## Doc impact' "
            "and an item-level '### Doc impact' — pick one "
            "(.claude/skills/segment-plan/SKILL.md)"
        )

    targets: list[dict] = []
    if item is not None:
        if item not in found["items"]:
            c1.append(f"no '## Item {item}' heading in {relative}")
        elif item_docs.get(item) is None:
            c1.append(f"Item {item} has no '### Doc impact' heading")
        else:
            targets.append({
                "depth": 3,
                "line": item_docs[item],
                "label": f"Item {item}",
                "status": found["items"][item]["status"] is not None,
                "item": item,
            })
    elif has_segment:
        targets.append({
            "depth": 2, "line": found["segment"], "label": "segment",
            "status": found["segment_status"],
        })
    elif has_items:
        # A segment whose items close independently: every item must pass.
        for number in sorted(item_docs):
            targets.append({
                "depth": 3, "line": item_docs[number], "label": f"Item {number}",
                "status": found["items"][number]["status"] is not None,
                "item": number,
            })
    elif found["stray"]:
        c1.append(
            f"{relative} has a '### Doc impact' that is not inside a "
            "'## Item <n>' block, so no level closes — move it under its "
            "item, or make it the segment-level '## Doc impact'"
        )
    else:
        c1.append(f"no 'Doc impact' heading in {relative}")

    result = {
        "id": f"{segment}.{item}" if item is not None else segment,
        "plan": relative,
        "c1": {
            "id": "C1", "what": "Doc impact present at level, one shape",
            "status": FAIL if c1 else PASS, "detail": c1,
        },
        "levels": [],
    }
    for target in targets:
        body = _section(lines, target["line"], target["depth"])
        result["levels"].append(
            check_manifest(
                plan, found, target["depth"], body, target["label"],
                target["status"], target.get("item"),
            )
        )
    return result


# --------------------------------------------------------------------
# reporting


def report(result: dict, stream) -> bool:
    """Write the human report; return True if every check passed."""
    print(f"{result['id']} — {result['plan']}", file=stream)
    ok = True

    c1 = result["c1"]
    print(f"  {c1['status'].upper():5s} {c1['id']} {c1['what']}", file=stream)
    for line in c1["detail"]:
        print(f"          {line}", file=stream)
    ok = ok and c1["status"] != FAIL

    for level in result["levels"]:
        win = level["window"]
        span = (
            f"{win['start_date']} .. {win['end'][:9] if win['end'] != 'HEAD' else 'HEAD'}"
            if win["start"] else "no window"
        )
        # The total counts `guide/` paths; the parenthetical says how
        # many of them the tool is not verifying. Counted and verified
        # are separate axes, and printing only the verified subtotal is
        # the defect 19K.1 closed — 19J.7 read "3 committed path(s)"
        # against a five-bullet manifest and exited 0.
        noted = level.get("noted") or []
        print(
            f"  [{level['level']}] "
            f"{len(level['paths']) + len(noted)} committed path(s), "
            + (f"{len(noted)} noted, " if noted else "")
            + f"{len(level['waived'])} waived, window {span}",
            file=stream,
        )
        for check in level["checks"]:
            print(
                f"  {check['status'].upper():5s} {check['id']} {check['what']}",
                file=stream,
            )
            for line in check["detail"]:
                print(f"          {line}", file=stream)
            ok = ok and check["status"] != FAIL
        for note in level["coverage_note"]:
            print(f"  note        {note}", file=stream)

    print(f"  => {'PASS' if ok else 'FAIL'}", file=stream)
    return ok


