"""Segment close check — did the spec edits a plan committed to happen?

Planned in `guide/segment_19A_spec_documentation.md` Item 3. Reads a
segment plan's `Doc impact` manifest and the repo's git history; writes
nothing, calls no LLM, and depends only on the standard library plus
`git` on PATH.

    python3 tools/close_check.py 19A.3      # one item
    python3 tools/close_check.py 18R        # a whole segment
    python3 tools/close_check.py 18R --json
    python3 tools/close_check.py --archived # report across every archived plan

Exit `0` pass (warnings allowed) · `1` a check failed · `2` usage or
resolution error. `--archived` is report-only and always exits 0.

Why this exists. The phase rule — plan on the way in, spec on the way
out (`rrw_sdd_in_practice.md` §6.1, `constitution.md` Article I) — is
held on the way out by convention. Every plan's definition of done
*asserts* the spec was updated; nothing checked it. Measured over the
archived plans on 2026-09-05, 85% of committed paths were edited inside
their plan's window and 13 of 32 plans dropped at least one commitment
silently. This makes that checkable. It is the **declared** half; the
undeclared half — a routing surface with no spec at all — is
`app/web/spec_registry.py` + `tests/unit/test_spec_coverage.py`.

What it does not check. Whether the edit was *correct*: a one-character
change to a committed path passes C3. That judgement is `spec-writer`'s
at close, and the human's. The script reports; the human acts.

## The checks

- **C1** `Doc impact` present at the level being closed, and the file
  uses one shape — never both a segment-level and an item-level
  manifest (`.claude/skills/segment-plan/SKILL.md`).
- **C2** every committed path exists and is not under an `archive/`.
- **C3** every un-waived path was modified inside the plan's window.
  On a segment-level manifest a bullet tagged `(Item n)` gets a
  narrower window of its own — see "The window" — and an edit that
  falls inside the segment's window but before that item's heading
  existed **warns** rather than fails.
- **C4** every waiver carries a reason.
- **C6** a `Status` block exists at the closing level — **warn only** in
  v1, promoted to a failure once the template has been in force for a
  few closes.
- **C7** every `<!-- cites: … -->` names a path its bullet contains. The
  marker says a path is *cited*, not committed to — see `CITES`. Both
  directions, so an escape covering nothing fails rather than quietly
  becoming a blanket.

There is no C5: the draft's vocabulary-rename check was dropped at 19A
(see that plan's judgment calls), and the number stays retired rather
than reused, so the record keeps meaning what it said.

## Heading matching, and why it is asymmetric

`Doc impact` matches **exactly** — `## Doc impact`, not `## Doc impact —
segment sketch (superseded)`. Suffixing the heading is how a plan
retires a manifest without deleting it (Segment 19A does exactly this),
so a suffixed heading must not be read as a live commitment. `Status`
matches with an optional suffix, because dated headings like `## Status
(started 2026-08-19)` are the existing convention.

## The window

Start = the first commit in which the `Doc impact` heading appears at
that level — the moment the commitment was made — found with
`git log -G'^## Doc impact$' --reverse` on the plan's **pre-archive**
path. Never `--follow --reverse`, which returns the archive-move commit
for a renamed file (measured: start = end, 0 of 110 paths "touched").
End = `HEAD`, or for an archived plan the commit that added the archived
path. A path is honoured by at least one non-merge commit touching it in
`[start, end]` — the start commit **included**, so a plan that lands its
manifest and its spec edit in one commit reads as honoured.

That boundary was open until 2026-09-08 (`(start, end]`, from `git log
A..B` dropping `A`), and the exclusion was arithmetic rather than a
rule: nowhere else does C3 ask *when* in the window an edit fell, and an
edit in the commit that recorded the commitment is the same evidence as
an edit the day after. Measured across all 99 plans it cost 6 of the 22
C3 failures — 19B's `docs/status.md`, 14B's `spec/email_infra_options.md`
(twice) and three paths in 19G Item 5 — every one of them a manifest and
its doc edit landing together. The item-anchor logic is unaffected: an
edit before its item's heading is still outside that bullet's window.

A **segment-level** manifest spans every item, so that one window let an
older item's edit satisfy a newer item's bullet. Measured on `19C` at
`2520dc7d`: C3 read a silent `PASS` while three Item 7 commitments were
outstanding, because the same specs had been edited for Item 3 three
weeks earlier. A bullet tagged `(Item n)` therefore opens at the **later**
of the segment window and that item's own `## Item n` heading; until the
heading existed the bullet was not yet making that promise. A bullet
carrying two tags takes the later item.

That anchor **warns, it does not fail**, and the distinction is the whole
design. Items are often written up after their work lands — `19C`'s
Items 3 and 4 were logged on 2026-08-21 in a commit titled "log 19C
refinements", for spec edits that shipped on 2026-08-20. Nothing in the
timestamps separates that from an edit made for a different item, so a
FAIL here would fire on honest work and the check would be routinely
waived, or switched off (`constitution.md` Article VI). It reports the
ambiguity, names both readings, and a person resolves it in one
`git log`. Measured across all 96 plans this fires once, and changes no
plan's exit code.

The cost is that the close gate still exits 0 with a warning standing, so
the definition-of-done line reads "exits 0; any warning adjudicated" —
the reader, not the exit code, closes the loop.
"""

from __future__ import annotations

import argparse
import json
import sys

from ._archive import archived_report
from ._manifest import (
    _first_commit_matching,
    _ITEM_START_CACHE,
    bullet_window_start,
    check_manifest,
    honoured,
    item_heading_start,
    parse_bullets,
    parse_id,
    report,
    resolve_plan,
    run,
    window,
)
from ._shared import REPO, Unresolvable, _git
from ._sweep import last_sweep_date, stale_report, sweep_scope

__all__ = [
    "REPO",
    "Unresolvable",
    "_ITEM_START_CACHE",
    "_first_commit_matching",
    "_git",
    "archived_report",
    "bullet_window_start",
    "check_manifest",
    "honoured",
    "item_heading_start",
    "last_sweep_date",
    "main",
    "parse_bullets",
    "parse_id",
    "report",
    "resolve_plan",
    "run",
    "stale_report",
    "sweep_scope",
    "window",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("id", nargs="?", help="segment or item id, e.g. 18R or 19A.3")
    parser.add_argument("--archived", action="store_true",
                        help="report across every archived plan; always exits 0")
    parser.add_argument("--stale", action="store_true",
                        help="list live spec/ + docs/ + root docs by age, and "
                             "report whether a sweep is due; always exits 0")
    parser.add_argument("--since", metavar="YYYY-MM-DD",
                        help="date of the last sweep, for --stale; defaults to "
                             "the newest guide/sweep_<date>_*.md")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable copy on stdout")
    args = parser.parse_args()

    if args.since and not args.stale:
        parser.error("--since is only meaningful with --stale")
    if args.stale:
        try:
            return stale_report(args.since, sys.stderr)
        except Unresolvable as exc:
            print(f"close_check: {exc}", file=sys.stderr)
            return 2
    if args.archived:
        archived_report(sys.stderr)
        return 0
    if not args.id:
        parser.error("an id is required unless --archived or --stale is given")

    try:
        segment, item = parse_id(args.id)
        result = run(segment, item)
    except Unresolvable as exc:
        print(f"close_check: {exc}", file=sys.stderr)
        return 2

    ok = report(result, sys.stderr)
    if args.json:
        print(json.dumps(result, indent=2))
    return 0 if ok else 1