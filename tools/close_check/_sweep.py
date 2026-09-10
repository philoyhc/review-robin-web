"""``--stale`` — the whole-folder sweep cadence (Segment 19A Item 2).

Genuinely independent of the close check: it shares ``REPO`` and
``_git`` and nothing else. Different question, different cadence,
different reader — ``close_check.py <id>`` verifies one segment's
declared commitments at its close; this lists live docs by age and
says whether a sweep is due.

Always exits 0.
"""

from __future__ import annotations

import datetime
import re

from . import _shared
from ._shared import Unresolvable, _git

# Sweep cadence (Segment 19A Item 2). Two signals because either alone
# misleads: a quiet eight weeks needs a sweep less than a frantic three,
# and calendar time alone let 1,120 merges pass as "only three months".
SWEEP_INTERVAL_WEEKS = 8
SWEEP_INTERVAL_MERGES = 500
# What a whole-folder sweep reads: live spec/ + docs/ + the root practice
# docs. Wider than the manifest regex, deliberately — that regex bounds
# what a plan may *commit* to; this bounds what a reader must *read*.
SWEEP_SCOPE_DIRS = ("spec", "docs")
SWEEP_DATED_NAME = re.compile(r"^sweep_(\d{4}-\d{2}-\d{2})_")


def sweep_scope() -> list[str]:
    """Live spec/ + docs/ + root practice docs, repo-relative, sorted."""
    paths = [
        path.relative_to(_shared.REPO).as_posix()
        for directory in SWEEP_SCOPE_DIRS
        for path in (_shared.REPO / directory).rglob("*.md")
        if "archive" not in path.relative_to(_shared.REPO).parts
    ]
    paths += [path.name for path in _shared.REPO.glob("*.md")]
    return sorted(paths)


def last_sweep_date() -> str | None:
    """Newest `guide/sweep_<YYYY-MM-DD>_*.md`, or None if none exists yet.

    Only the dated convention is read. The three pre-convention sweeps
    (`spec_sweep_11may.md` and friends) carry no parseable date, so
    guessing one would be worse than asking for ``--since``.
    """
    dates = [
        match.group(1)
        for path in (_shared.REPO / "guide").glob("sweep_*.md")
        if (match := SWEEP_DATED_NAME.match(path.name))
    ]
    return max(dates) if dates else None


def stale_report(since: str | None, stream) -> int:
    """List in-scope docs by age, and answer 'are we due for a sweep?'."""
    since = since or last_sweep_date()
    if since is not None:
        try:
            datetime.date.fromisoformat(since)
        except ValueError:
            raise Unresolvable(f"--since {since!r} is not a YYYY-MM-DD date")

    today = datetime.date.today()
    rows = []
    for path in sweep_scope():
        edited = _git("log", "-1", "--format=%ad", "--date=short", "--", path).strip()
        if not edited:
            continue
        age = (today - datetime.date.fromisoformat(edited)).days
        rows.append((age, edited, path))
    rows.sort(reverse=True)

    print(f"DOC STALENESS ({len(rows)} live files in spec/, docs/, root)", file=stream)
    for age, edited, path in rows:
        mark = " <-" if since and edited < since else "   "
        print(f"  {age:4d} d  {edited}  {path}{mark}", file=stream)

    if since is None:
        print(
            "\n  No dated sweep found (guide/sweep_<YYYY-MM-DD>_*.md). Pass "
            "--since <date> for the trigger arithmetic.",
            file=stream,
        )
        return 0

    untouched = sum(1 for _, edited, _ in rows if edited < since)
    days = (today - datetime.date.fromisoformat(since)).days
    if not _git("rev-parse", "--verify", "--quiet", "origin/main").strip():
        raise Unresolvable(
            "origin/main does not resolve, so the merge count would read 0 "
            "and the trigger would say 'not due' for the wrong reason — "
            "fetch first"
        )
    merges = len([
        row for row in _git(
            "rev-list", "--merges", f"--since={since}", "origin/main"
        ).split("\n") if row.strip()
    ])
    due_weeks = days >= SWEEP_INTERVAL_WEEKS * 7
    due_merges = merges >= SWEEP_INTERVAL_MERGES
    print(
        f"\n  {untouched} of {len(rows)} not modified since the last sweep "
        f"({since}) — marked <- above; read those first.",
        file=stream,
    )
    print(f"\nSWEEP TRIGGER (last sweep {since})", file=stream)
    print(
        f"  elapsed  {days:4d} d of {SWEEP_INTERVAL_WEEKS * 7} "
        f"({SWEEP_INTERVAL_WEEKS} weeks){'  <- due' if due_weeks else ''}",
        file=stream,
    )
    print(
        f"  merges   {merges:4d}   of {SWEEP_INTERVAL_MERGES}"
        f"{'  <- due' if due_merges else ''}",
        file=stream,
    )
    print(
        f"  => {'DUE' if due_weeks or due_merges else 'not due'}", file=stream
    )
    return 0


