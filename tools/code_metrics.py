#!/usr/bin/env python3
"""Duplication and churn metrics for the codebase assessments.

Standard-item metrics for `guide/codebase_assessment_*.md`. Reads the repo
and its git history; writes nothing, installs nothing, and depends only on
the standard library plus `git` on PATH.

    python3 tools/code_metrics.py              # both metrics, app/ and tests/
    python3 tools/code_metrics.py --dup-only
    python3 tools/code_metrics.py --churn-days 30
    python3 tools/code_metrics.py --churn-only --churn-sample 200   # quick, noisy

Why these two. `docs/practice-audit-2026-09-04.md` Appendix A benchmarked
the practice against the 2026 vibe-coding evidence and found that the two
figures that literature leans on — duplication ratio and code churn — were
simply not measured here, while LOC and file sizes were. These are those
two, defined so the numbers are reproducible rather than impressionistic.

**Duplication** is reported as a curve across block sizes, not a single
number, because the number is meaningless without it: short blocks catch
import and decorator boilerplate, long blocks catch only egregious
copy-paste. Read the >=10 row as the headline for production code.

**Churn** is the share of deleted lines that were younger than
`--churn-days` when they were deleted — i.e. how much of the work is
rewriting recent work rather than adding to settled code. Computed by
blaming each deleted line against the parent commit, across **every**
first-parent merge on `origin/main`.

Walking the whole history is the point. An earlier version sampled merges
evenly and it was the sampling, not the sample size, that was wrong:
deletions per merge are heavy-tailed, so the figure is decided by whichever
few large merges the sample lands on. Measured on this repo 2026-09-04, the
ratio read 1.4x / 1.4x / 0.9x / 1.0x / 0.8x / 1.0x / 1.1x / 1.1x / 1.1x at
sample sizes 60 / 120 / 100 / 200 / 300 / 500 / 700 / 1000 / 400 — no floor
above which it settles. The full history (2,085 merges) gives 1.0x
deterministically in ~76s. A metric an assessment quotes and the next
assessment compares against has to be reproducible, and 76s once per
snapshot is the right trade.

`--churn-sample N` remains for a quick look while iterating on the tool. It
warns, and its output must not be compared against the action thresholds in
`guide/README.md` or against a previous snapshot.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
BLOCK_SIZES = (6, 10, 15, 25)
HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+")
# Sentinel for --churn-sample: walk every merge. Sampling is opt-in because
# no sample size was found at which the ratio settles (see the module
# docstring for the measured spread). Measured 2026-09-04.
CHURN_SAMPLE_ALL = 0


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, check=False,
    ).stdout


def _normalised(path: pathlib.Path) -> list[tuple[int, str]]:
    """Code lines only: stripped, no blanks, no whole-line comments."""
    rows = []
    for number, raw in enumerate(path.read_text(errors="replace").splitlines(), 1):
        line = raw.strip()
        if line and not line.startswith("#"):
            rows.append((number, line))
    return rows


def duplication(root: pathlib.Path) -> None:
    files = sorted(p for p in root.rglob("*.py") if ".venv" not in p.parts)
    per_file = {f: _normalised(f) for f in files}
    total = sum(len(v) for v in per_file.values())
    if not total:
        print(f"  {root.name}/: no Python found")
        return

    print(f"  {root.relative_to(REPO)}/ — {len(files)} files, {total:,} code lines")
    worst_at_10: list[tuple[pathlib.Path, int]] = []
    for size in BLOCK_SIZES:
        windows: dict[str, int] = collections.defaultdict(int)
        seen: dict[pathlib.Path, set[int]] = collections.defaultdict(set)
        locations: dict[str, list[tuple[pathlib.Path, int]]] = collections.defaultdict(list)
        for f, rows in per_file.items():
            for i in range(len(rows) - size + 1):
                key = hashlib.md5(
                    "\n".join(s for _, s in rows[i:i + size]).encode()
                ).hexdigest()
                windows[key] += 1
                locations[key].append((f, i))
        for key, count in windows.items():
            if count < 2:
                continue
            for f, i in locations[key]:
                seen[f].update(range(i, i + size))
        dup = sum(len(v) for v in seen.values())
        print(f"      blocks >= {size:>2} lines: {dup:>6,} lines duplicated  ({dup / total * 100:4.1f}%)")
        if size == 10:
            worst_at_10 = sorted(seen.items(), key=lambda kv: -len(kv[1]))[:5]

    if worst_at_10:
        print("      most-duplicated files (>= 10-line blocks):")
        for f, lines in worst_at_10:
            own = len(per_file[f])
            print(f"        {str(f.relative_to(REPO)):<52} {len(lines):>5}/{own:<5} ({len(lines) / own * 100:3.0f}%)")


def churn(days: int, sample: int) -> None:
    all_merges = [m for m in _git(
        "log", "origin/main", "--first-parent", "--merges", "--format=%H %ct",
    ).split("\n") if m.strip()]
    # Sampling is opt-in and evenly spread across the whole history, never the
    # most recent N: a run of documentation-only PRs at the head would
    # otherwise dominate and report a figure computed from a handful of lines.
    if sample > CHURN_SAMPLE_ALL and len(all_merges) > sample:
        step = len(all_merges) / sample
        merges = [all_merges[int(i * step)] for i in range(sample)]
    else:
        merges = all_merges
    if not merges:
        print("  no merge commits found on origin/main")
        return

    young = old = 0
    base_young = base_old = 0
    for entry in merges:
        sha, when = entry.split()
        merged_at = int(when)
        diff = _git("diff", "--unified=0", f"{sha}^1", sha, "--", "*.py")
        current: str | None = None
        deleted: dict[str, list[int]] = collections.defaultdict(list)
        line_no = 0
        for row in diff.split("\n"):
            if row.startswith("--- a/"):
                current = row[6:]
            elif row.startswith("--- /dev/null"):
                current = None            # file added; nothing to blame
            elif row.startswith("@@"):
                # "@@ -12,3 +12,0 @@" and the single-line form "@@ -89 +89 @@".
                match = HUNK.match(row)
                line_no = int(match.group(1)) if match else 0
            elif row.startswith("-") and not row.startswith("---") and current:
                if line_no:               # a 0 means the header did not parse
                    deleted[current].append(line_no)
                    line_no += 1
        for path, numbers in deleted.items():
            if not numbers:
                continue
            # One blame per file, indexed by line, rather than a batch of -L
            # ranges: a single out-of-range range makes git blame fail for the
            # whole call, silently dropping every deletion in that file.
            blame = _git("blame", "--line-porcelain", f"{sha}^1", "--", path)
            if not blame:
                continue
            times: list[int] = []
            for row in blame.split("\n"):
                if row.startswith("author-time "):
                    times.append(int(row.split()[1]))
            # Baseline: how young was the file as a whole at that moment? A
            # fast-moving repo makes everything young, so the deleted-line
            # figure only means something against this.
            for stamp in times:
                if (merged_at - stamp) / 86400 <= days:
                    base_young += 1
                else:
                    base_old += 1
            for n in numbers:
                if not 1 <= n <= len(times):
                    continue
                age_days = (merged_at - times[n - 1]) / 86400
                if age_days <= days:
                    young += 1
                else:
                    old += 1

    total = young + old
    if not total:
        print("  no Python deletions in the sampled merges")
        return
    if len(merges) == len(all_merges):
        print(f"  all {len(all_merges):,} merges on origin/main")
    else:
        print(f"  sampled {len(merges)} merges spread evenly across "
              f"{len(all_merges):,} on origin/main")
        print("  WARNING: sampled. The ratio below is sample-dependent at any "
              "size — do not compare it against a threshold or against another "
              "snapshot. Drop --churn-sample for the reproducible figure.")
    base_total = base_young + base_old
    base_pct = base_young / base_total * 100 if base_total else 0.0
    churn_pct = young / total * 100
    print(f"  deleted Python lines              : {total:,}")
    print(f"  of which younger than {days:>2} days     : {young:,}  ({churn_pct:.1f}%)  <- churn")
    print("  baseline: same share of ALL lines")
    print(f"  in those files at that moment     : {base_young:,}/{base_total:,}  ({base_pct:.1f}%)")
    if base_pct:
        print(f"  ratio (churn / baseline)          : {churn_pct / base_pct:.1f}x")
        print("  A ratio near 1.0 means deletions are age-blind — the code is")
        print("  simply young. Well above 1.0 means recent work is being")
        print("  rewritten specifically, which is what the term churn describes.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dup-only", action="store_true")
    parser.add_argument("--churn-only", action="store_true")
    parser.add_argument("--churn-days", type=int, default=14)
    parser.add_argument(
        "--churn-sample", type=int, default=CHURN_SAMPLE_ALL,
        help="sample N merges instead of walking all of them; sample-dependent, "
             "for iterating on this tool only",
    )
    args = parser.parse_args()

    if not args.churn_only:
        print("DUPLICATION")
        for name in ("app", "tests"):
            duplication(REPO / name)
        print()
    if not args.dup_only:
        print(f"CHURN (lines deleted within {args.churn_days} days of being written)")
        churn(args.churn_days, args.churn_sample)
    return 0


if __name__ == "__main__":
    sys.exit(main())
