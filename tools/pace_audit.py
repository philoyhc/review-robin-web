#!/usr/bin/env python3
"""Pace audit: elapsed time per merged slice, from merge history.

Read-only. Stdlib + ``git``. The method behind ``rrw_sdd_in_practice.md``
§6.4 (2026-09-19) and the figure ``CLAUDE.md`` "Where work runs" points at.

    python3 tools/pace_audit.py --cut 2460 [--since 2026-09-04]
                               [--recent 2026-09-14] [--prs prs.jsonl]

Merged PRs since ``--since`` are split into BEFORE (number below the cut)
and AFTER (at or above it); a second BEFORE window from ``--recent`` gives
the last stretch under the old rules on its own. Needs a full history
(``git fetch --unshallow origin main`` on a session clone).

Every figure is git-only except PR-opened -> merged, which needs
``--prs``: one ``{"number", "created_at", "merged_at"}`` JSON object per
line, taken from the GitHub API (PR timestamps are not in git).

Definitions, all in minutes:

* ``cycle``      merge-to-merge on ``main``, within a session only — a gap
                 over three hours is the author's scheduling, not the work,
                 and is dropped.
* ``turn``       previous merge -> first commit of the PR. Includes the
                 time the instruction took to write, so read it as a
                 ceiling on build time.
* ``iter``       first -> last commit inside the PR: the fix-and-re-push
                 loop a reader or CI adds.
* ``push2merge`` last commit -> merge.
* ``review``     the PR carries a commit whose subject names a cold read,
                 a second reader or acting on one.
* ``turn`` fit   least squares of turn on code+test lines over product PRs:
                 the intercept is the cost a slice pays whatever its size
                 (instruction, context load, the gate run), the slope what
                 scales with the build.
* ``wait`` / ``build``  when a slice's first commit carries an
                 ``Instruction-Received: <UTC ISO-8601>`` line (CLAUDE.md
                 "Where work runs"), turn splits at it: ``wait`` is previous
                 merge -> instruction, ``build`` is instruction -> first
                 commit. Reported once at least three slices carry it.

Exit 0 always; it reports, a person reads.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import statistics
import subprocess

REVIEW_RE = re.compile(
    # Response forms only — "act on the cold read", "cold-read fixes", "the
    # cold read: ...", "Codex: ...", "Codex #2485: ...", "spec-writer pass" —
    # never a bare topic word: "Refresh Codex codebase assessment" and
    # "Cold-read cadence: per item" are about the reader, not answers to it.
    r"act(?:ed|ing)? on (?:the|both|its|all|each)\b"
    r"|cold[- ]reads?(?:'s)?[ -](?:fix|adjudicat|round|finding|found|pass)"
    r"|cold readers adjudicated"
    r"|(?:the|a|an|its|item's|cumulative) cold read(?:'s)?\b"
    r"|second read\b"
    r"|\bcodex(?:'s)?(?::|,| #\d+:| review| finding| p[0-9]| two| three)"
    r"|from the codex review|spec-writer pass|close pass(?:es)?\b|close's spec-writer",
    re.I,
)
BUCKETS = [(1, 50), (50, 150), (150, 400), (400, 10**9)]
SESSION_GAP_MIN = 180
MAIN_REF = "origin/main"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def category(path: str) -> str:
    if path.startswith("app/web/templates"):
        return "tpl"
    if path.startswith(("app/", "alembic/")):
        return "code"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith(("spec/", "docs/", "guide/")) or path.endswith(".md"):
        return "prose"
    return "other"


def since_arg(since: str) -> str:
    """A bare date must be pinned to midnight UTC.

    ``git log --since=2026-09-04`` fills the missing time of day with the
    *current* clock, so the same command run at 23:50 UTC drops every merge
    made before 23:50 on that date and the count drifts with the hour it was
    run. Measured 2026-09-20: 25 merges lost and recovered across three runs.
    """
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        return f"{since}T00:00:00+00:00"
    return since


def resolve_ref(ref: str = MAIN_REF) -> str:
    """``ref`` if it exists, else the local ``main`` a fresh clone has, else an error.

    A repository with no remote yet, or one whose remote branch is called
    something else, should say so rather than fail inside ``git log``.
    """
    for candidate in (ref, "main"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            return candidate
    raise SystemExit(
        f"pace_audit: neither {ref!r} nor 'main' names a commit here. "
        "Run from a clone with the main line fetched, or name it with --ref."
    )


def load(since: str, ref: str = MAIN_REF) -> list[dict]:
    """Every merge on ``ref``'s first-parent line since ``since``, oldest first."""
    rows: list[dict] = []
    log = git(
        "log", "--merges", "--first-parent", resolve_ref(ref), f"--since={since_arg(since)}",
        "--format=%H|%ct|%s|%b",
    )
    for line in log.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 3:
            continue
        sha, merged_at, subject = parts[0], int(parts[1]), parts[2]
        number = re.search(r"#(\d+)", subject)
        if not number:
            continue
        commits = git("log", "--format=%at|%s", f"{sha}^1..{sha}^2").splitlines()
        if not commits:
            continue
        times = [int(c.split("|", 1)[0]) for c in commits]
        subjects = [c.split("|", 1)[1] for c in commits]
        received = instruction_received(sha)
        loc: collections.Counter[str] = collections.Counter()
        for stat in git("diff", "--numstat", f"{sha}^1", sha).splitlines():
            added, deleted, path = stat.split("\t", 2)
            if added != "-":
                loc[category(path)] += int(added) + int(deleted)
        rows.append(
            {
                "pr": int(number.group(1)),
                "merge": merged_at,
                "first": min(times),
                "last": max(times),
                "n": len(subjects),
                "title": parts[3].strip() if len(parts) > 3 else "",
                "code": loc["code"] + loc["tpl"],
                "tests": loc["tests"],
                "prose": loc["prose"],
                "review": any(REVIEW_RE.search(s) for s in subjects),
                "received": received,
            }
        )
    rows.sort(key=lambda r: r["merge"])
    prev = None
    for r in rows:
        r["product"] = bool(r["code"] + r["tests"])
        r["turn"] = (r["first"] - prev) / 60 if prev else None
        r["cycle"] = (r["merge"] - prev) / 60 if prev else None
        r["iter"] = (r["last"] - r["first"]) / 60
        r["push2merge"] = (r["merge"] - r["last"]) / 60
        r["wait"] = r["build"] = None
        if prev and r["received"] and prev <= r["received"] <= r["first"]:
            r["wait"] = (r["received"] - prev) / 60
            r["build"] = (r["first"] - r["received"]) / 60
        prev = r["merge"]
    return rows


STAMP_RE = re.compile(r"^Instruction-Received:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def instruction_received(merge_sha: str) -> int | None:
    """Epoch seconds from the ``Instruction-Received`` line on the slice's
    first commit, or None. Read from the earliest commit only: a later fix
    commit answers a reader or CI, not an instruction.

    Matched on its own line anywhere in the message, not as a git trailer:
    git parses only a message's *last* paragraph as trailers, and of the
    38 slices that had written the line by 2026-09-22, 21 had put it in a
    paragraph of its own above ``Co-Authored-By`` and were silently
    dropped by ``%(trailers:...)`` (19R Item 7). The first match wins."""
    first = git("rev-list", "--reverse", f"{merge_sha}^1..{merge_sha}^2").split()
    if not first:
        return None
    match = STAMP_RE.search(git("log", "-1", "--format=%B", first[0]))
    if not match:
        return None
    try:
        return int(dt.datetime.fromisoformat(match.group(1).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def add_pr_timestamps(rows: list[dict], path: str) -> None:
    prs = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                record = json.loads(line)
                prs[record["number"]] = record

    def ts(value: str) -> float:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

    for r in rows:
        record = prs.get(r["pr"])
        if record and record.get("merged_at"):
            r["open2merge"] = (ts(record["merged_at"]) - ts(record["created_at"])) / 60


def median(values) -> float:
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else float("nan")


def mean(values) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else float("nan")


def report(label: str, rows: list[dict]) -> None:
    if not rows:
        print(f"\n== {label}: no merged PRs")
        return
    within = [r for r in rows if r["cycle"] is not None and r["cycle"] < SESSION_GAP_MIN]
    days = {dt.date.fromtimestamp(r["merge"]) for r in rows}
    hours = sum(r["cycle"] for r in within) / 60
    print(f"\n== {label}: {len(rows)} PRs, {len(days)} active days, {hours:.1f} within-session hours")
    print(
        f"  cycle med {median(r['cycle'] for r in within):5.1f}  "
        f"mean {mean(r['cycle'] for r in within):5.1f} = "
        f"turn {mean(r['turn'] for r in within):4.1f} + "
        f"iter {mean(r['iter'] for r in within):4.1f} + "
        f"push2merge {mean(r['push2merge'] for r in within):4.1f}"
    )
    print(
        f"  PR opened->merged med {median(r.get('open2merge') for r in rows):5.1f}   "
        f"multi-commit PRs {mean(r['n'] > 1 for r in rows) * 100:3.0f}%   "
        f"PRs with a review-response commit {mean(r['review'] for r in rows) * 100:3.0f}%"
    )
    for kind, keep in (("product", True), ("docs-only", False)):
        sub = [r for r in within if r["product"] is keep]
        if not sub:
            continue
        with_review = [r["cycle"] for r in sub if r["review"]]
        without = [r["cycle"] for r in sub if not r["review"]]
        print(
            f"  {kind:9}: n={len(sub):3}  cycle med {median(r['cycle'] for r in sub):5.1f}  "
            f"with review round {median(with_review):5.1f} (n={len(with_review)})  "
            f"without {median(without):5.1f}"
        )
    product = [r for r in within if r["product"]]
    cells = []
    for lo, hi in BUCKETS:
        in_bucket = [r["cycle"] for r in product if lo <= r["code"] + r["tests"] < hi]
        top = hi if hi < 10**9 else "+"
        cells.append(f"{lo}-{top}: {median(in_bucket):4.0f} (n={len(in_bucket)})")
    print("  product PRs, median cycle by code+test LOC bucket: " + "  ".join(cells))
    product_hours = sum(r["cycle"] for r in product) / 60
    loc = sum(r["code"] + r["tests"] for r in product)
    rate = loc / product_hours if product_hours else 0
    print(f"  code+test LOC per within-session hour (product PRs): {rate:6.0f}")
    turns = sorted(r["turn"] for r in within if r["turn"] > 0)
    if len(product) >= 3 and turns:
        xs = [r["code"] + r["tests"] for r in product]
        ys = [r["turn"] for r in product]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
        fixed = my - slope * mx
        pct = lambda p: turns[int(p * (len(turns) - 1))]  # noqa: E731
        print(
            f"  turn p25 {pct(0.25):4.1f}  med {pct(0.5):4.1f}  p75 {pct(0.75):4.1f}  "
            f"| fit on product PRs: fixed {fixed:4.1f} min + {slope * 100:4.2f} min per 100 LOC"
        )
    stamped = [r for r in within if r["wait"] is not None]
    if len(stamped) >= 3:
        print(
            f"  turn split on Instruction-Received (n={len(stamped)}): "
            f"wait med {median(r['wait'] for r in stamped):4.1f} "
            f"mean {mean(r['wait'] for r in stamped):4.1f}  |  "
            f"build med {median(r['build'] for r in stamped):4.1f} "
            f"mean {mean(r['build'] for r in stamped):4.1f}"
        )
    else:
        print(f"  turn split: {len(stamped)} slices carry Instruction-Received; needs 3")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cut", type=int, required=True, help="first PR number under the new rules")
    ap.add_argument("--since", default="2026-09-04", help="earliest merge date to read")
    ap.add_argument("--recent", default="2026-09-14", help="start of the last BEFORE window")
    ap.add_argument("--prs", help="JSONL of PR number/created_at/merged_at from the GitHub API")
    ap.add_argument("--ref", default=MAIN_REF, help="the main line to read (default origin/main, then main)")
    args = ap.parse_args()

    rows = load(args.since, ref=args.ref)
    if args.prs:
        add_pr_timestamps(rows, args.prs)
    recent = dt.date.fromisoformat(args.recent)
    before = [r for r in rows if r["pr"] < args.cut]
    report(f"BEFORE (PR < #{args.cut}, since {args.since})", before)
    report(
        f"BEFORE, from {args.recent} to #{args.cut - 1}",
        [r for r in before if dt.date.fromtimestamp(r["merge"]) >= recent],
    )
    report(f"AFTER (PR >= #{args.cut})", [r for r in rows if r["pr"] >= args.cut])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
