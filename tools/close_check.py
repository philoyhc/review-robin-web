#!/usr/bin/env python3
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
- **C4** every waiver carries a reason.
- **C6** a `Status` block exists at the closing level — **warn only** in
  v1, promoted to a failure once the template has been in force for a
  few closes. There is no C5 (see the plan's judgment calls).

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
`(start, end]` — the start commit itself is excluded, so a plan that
lands its manifest and its spec edit in one commit reads as unhonoured.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

# A committed path: backticked, under spec/ or docs/, ending .md. The
# trailing [^`]* absorbs a section reference written inside the ticks
# (`docs/quickstart.md §4c`, `spec/x.md#anchor`).
COMMITTED_PATH = re.compile(r"`((?:spec|docs)/[A-Za-z0-9._/-]+\.md)[^`]*`")
WAIVER = re.compile(r"<!--\s*doc-impact-waived:(.*?)-->", re.DOTALL)
ITEM_HEADING = re.compile(r"^## Item (\d+)\b")
SEGMENT_ID = re.compile(r"^([A-Za-z0-9]+)(?:\.(\d+))?$")

PASS, FAIL, WARN, SKIP = "pass", "fail", "warn", "skip"


class Unresolvable(Exception):
    """A usage or resolution error — exit 2, never a check failure."""


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, check=False,
    ).stdout


# --------------------------------------------------------------------
# resolution


def resolve_plan(segment: str) -> pathlib.Path:
    """`18R` -> guide/segment_18R_ux_refine.md (live dir, then archive).

    Matches `segment_<id>.md` and `segment_<id>_<slug>.md` exactly, so
    `04` does not resolve to `segment_04A.md`.
    """
    candidates = [
        path
        for directory in (REPO / "guide", REPO / "guide" / "archive")
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
        seen: list[str] = []
        for path in COMMITTED_PATH.findall(bullet["text"]):
            if path not in seen:
                seen.append(path)
        bullet["paths"] = seen
    return bullets


# --------------------------------------------------------------------
# window


def pre_archive_path(plan: pathlib.Path) -> str:
    relative = plan.relative_to(REPO).as_posix()
    return relative.replace("guide/archive/", "guide/")


def window(plan: pathlib.Path, depth: int) -> tuple[str | None, str, str | None]:
    """(start commit, end commit, start date) for the manifest's level."""
    heading = "^" + ("###" if depth == 3 else "##") + " Doc impact$"
    relative = plan.relative_to(REPO).as_posix()
    archived = "guide/archive/" in relative

    start = None
    for candidate in dict.fromkeys([pre_archive_path(plan), relative]):
        found = _git(
            "log", "--reverse", "--format=%H %ad", "--date=short",
            "-G", heading, "--", candidate,
        ).split("\n")
        found = [row for row in found if row.strip()]
        if found:
            start = found[0].split(" ", 1)
            break

    if archived:
        adds = [
            row for row in _git(
                "log", "--diff-filter=A", "--format=%H", "--", relative
            ).split("\n") if row.strip()
        ]
        end = adds[0] if adds else "HEAD"
    else:
        end = "HEAD"

    return (start[0] if start else None, end, start[1] if start else None)


def honoured(path: str, start: str, end: str) -> str | None:
    """Last commit date touching `path` in (start, end], or None."""
    out = _git(
        "log", "--no-merges", "--format=%ad", "--date=short",
        f"{start}..{end}", "--", path,
    ).split("\n")
    dates = [row for row in out if row.strip()]
    return dates[0] if dates else None


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
        sys.path.insert(0, str(REPO))
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
    status_present: bool,
) -> dict:
    lines = found["lines"]
    bullets = parse_bullets(lines, *body)
    start, end, start_date = window(plan, depth)

    committed: list[dict] = []
    for bullet in bullets:
        for path in bullet["paths"]:
            committed.append(
                {
                    "path": path,
                    "line": bullet["line"],
                    "waived": bullet["waived"],
                    "reason": bullet["reason"],
                }
            )

    checks: list[dict] = []

    # C2 — every committed path exists, and is not archived.
    c2 = []
    for entry in committed:
        if "archive/" in entry["path"]:
            c2.append(f"{entry['path']} is archived (line {entry['line']})")
        elif not (REPO / entry["path"]).is_file():
            c2.append(f"{entry['path']} does not exist (line {entry['line']})")
    checks.append({
        "id": "C2", "what": "committed paths exist and are live",
        "status": FAIL if c2 else PASS, "detail": c2,
    })

    # C3 — every un-waived path modified in the window.
    c3, honoured_count, checked = [], 0, 0
    if start is None:
        checks.append({
            "id": "C3", "what": "paths modified in window",
            "status": WARN,
            "detail": [f"no window: '{label}' heading never appears in the plan's history"],
        })
    else:
        for entry in committed:
            if entry["waived"] or not (REPO / entry["path"]).is_file():
                continue
            checked += 1
            when = honoured(entry["path"], start, end)
            if when:
                honoured_count += 1
            else:
                ever = last_touched_ever(entry["path"]) or "never"
                c3.append(
                    f"{entry['path']} not modified in window "
                    f"(last modified {ever}, line {entry['line']})"
                )
        checks.append({
            "id": "C3", "what": "paths modified in window",
            "status": FAIL if c3 else PASS, "detail": c3,
        })

    # C4 — every waiver reasoned.
    c4 = [
        f"line {entry['line']}: waiver has no reason"
        for entry in committed
        if entry["waived"] and not entry["reason"]
    ]
    checks.append({
        "id": "C4", "what": "waivers carry a reason",
        "status": FAIL if c4 else PASS, "detail": c4,
    })

    # C6 — Status block at the closing level. Warn only in v1.
    checks.append({
        "id": "C6", "what": "Status block present",
        "status": PASS if status_present else WARN,
        "detail": [] if status_present else [f"no Status block at {label} level"],
    })

    return {
        "level": label,
        "window": {"start": start, "start_date": start_date, "end": end},
        "paths": [entry["path"] for entry in committed],
        "waived": [e["path"] for e in committed if e["waived"]],
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
    relative = plan.relative_to(REPO).as_posix()

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
                plan, found, target["depth"], body, target["label"], target["status"]
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
        print(
            f"  [{level['level']}] {len(level['paths'])} committed path(s), "
            f"{len(level['waived'])} waived, window {span}",
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


def archived_report(stream) -> None:
    plans = sorted((REPO / "guide" / "archive").glob("segment_*.md"))
    total_paths = total_honoured = 0
    fully = considered = no_manifest = missing = 0

    print(f"ARCHIVED PLANS ({len(plans)})", file=stream)
    for plan in plans:
        found = find_manifests(plan.read_text())
        if found["segment"] is None and not found["stray"] and not any(
            i["doc"] is not None for i in found["items"].values()
        ):
            no_manifest += 1
            continue
        depth = 2 if found["segment"] is not None else 3
        line = found["segment"] if depth == 2 else next(
            (i["doc"] for i in found["items"].values() if i["doc"] is not None),
            found["stray"][0] if found["stray"] else None,
        )
        body = _section(found["lines"], line, depth)
        bullets = parse_bullets(found["lines"], *body)
        paths = [p for bullet in bullets for p in bullet["paths"] if not bullet["waived"]]
        paths = list(dict.fromkeys(paths))
        if not paths:
            no_manifest += 1
            continue

        start, end, start_date = window(plan, depth)
        considered += 1
        # Missing paths are C2's business, not C3's — keep them out of the
        # honour denominator so the two code paths divide the work the same
        # way, and report them on their own.
        live = [path for path in paths if (REPO / path).is_file()]
        missing += len(paths) - len(live)
        hits = sum(1 for path in live if start and honoured(path, start, end))
        total_paths += len(live)
        total_honoured += hits
        if live and hits == len(live):
            fully += 1
        flags = []
        if hits != len(live):
            flags.append(f"{len(live) - hits} unhonoured")
        if len(paths) != len(live):
            flags.append(f"{len(paths) - len(live)} missing")
        flag = f"  <- {', '.join(flags)}" if flags else ""
        print(
            f"  {plan.name:58s} {hits:3d}/{len(live):<3d} "
            f"{start_date or '(no window)'}{flag}",
            file=stream,
        )

    share = f"{100 * total_honoured / total_paths:.0f}%" if total_paths else "n/a"
    print(
        f"\n  {total_honoured}/{total_paths} live committed paths honoured ({share}); "
        f"{fully} of {considered} plans fully honoured; "
        f"{missing} committed path(s) no longer exist; "
        f"{no_manifest} plans with no manifest",
        file=stream,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("id", nargs="?", help="segment or item id, e.g. 18R or 19A.3")
    parser.add_argument("--archived", action="store_true",
                        help="report across every archived plan; always exits 0")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable copy on stdout")
    args = parser.parse_args()

    if args.archived:
        archived_report(sys.stderr)
        return 0
    if not args.id:
        parser.error("an id is required unless --archived is given")

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


if __name__ == "__main__":
    sys.exit(main())
