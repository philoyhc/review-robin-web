#!/usr/bin/env python3
"""Practice kit: the files a new repository inherits from this one.

Read-only against this repo. The manifest below is the constant the
setup procedure in ``new_project_practices_setup.md`` derives from; a
test keeps that document's table and this list identical, so neither can
drift from the other or from the tree.

    python3 tools/practice_kit.py --list              # the manifest, as a table
    python3 tools/practice_kit.py --export DEST       # copy the kit into DEST

Three tiers. ``verbatim`` files are copied and need at most a project
name. ``adapt`` files are copied and carry a named edit the setup
document spells out. ``skeleton`` files are not copied from here at all —
they are generated empty-but-well-formed, because this repo's version is
its own history, not a template. Export never overwrites an existing
file; ``--force`` does.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

#: (path, tier, one-line note). Order is the order the setup document works in.
MANIFEST: tuple[tuple[str, str, str], ...] = (
    ("CLAUDE.md", "adapt", "rewrite Project conventions + Architecture + Where to look; keep Where work runs; cp to AGENTS.md"),
    ("constitution.md", "adapt", "keep the six articles; drop the dated annotations; re-point 'derived from'"),
    ("CONTRIBUTING.md", "adapt", "fill the merge-policy paragraph's <slow job> and <paths> for the new CI"),
    (".gitignore", "skeleton", "the .claude/* negation lines only; appended if absent"),
    (".claude/agents/diff-reviewer.md", "adapt", "check 4 names this app's seams (routes_operator/_shared.py, base.html); name yours"),
    (".claude/agents/spec-writer.md", "adapt", "cites spec/README.md and the close procedure; re-point once your spec/ exists"),
    (".claude/skills/segment-plan/SKILL.md", "verbatim", "the plan / item / close procedure"),
    ("guide/segment_plan_template.md", "verbatim", "the shape every plan copies"),
    ("guide/sweep_template.md", "verbatim", "the shape every spec/docs sweep copies"),
    ("guide/README.md", "skeleton", "index with the documented shapes the guide-index gate reads"),
    ("guide/archive/README.md", "skeleton", "index the archive gate reads; one row per file, no patterns"),
    ("guide/todo_master.md", "skeleton", "Done / Upcoming roadmap"),
    ("guide/deferred_consolidated.md", "skeleton", "everything scoped but not scheduled"),
    ("spec/README.md", "skeleton", "index of the surface contracts"),
    ("docs/README.md", "skeleton", "index of the operational docs"),
    ("docs/status.md", "skeleton", "implementation state; first row is this setup"),
    ("docs/unenforced_conventions.md", "skeleton", "constitution VI's short list; starts empty"),
    (".github/workflows/ci.yml", "verbatim", "ruff + pytest -n auto on 3.12"),
    (".github/workflows/ci-postgres.yml", "adapt", "DB user / password / name; the alembic round-trip stays"),
    ("tests/unit/test_doc_conventions.py", "adapt", "keep the twins, path-reference and section-reference checks; delete the checks that import app constants until you have one"),
    ("tests/unit/test_guide_indexes.py", "verbatim", "the guide-index gate; reads the skeleton READMEs"),
    ("app/web/spec_registry.py", "adapt", "the route-table -> spec mapping; empty the table, lower _MINIMUM_ROUTES"),
    ("tests/unit/test_spec_coverage.py", "adapt", "pairs with spec_registry; baseline set starts empty"),
    ("tools/close_check.py", "verbatim", "close check entry point"),
    ("tools/close_check/__init__.py", "verbatim", "close check package"),
    ("tools/close_check/_shared.py", "verbatim", "close check package"),
    ("tools/close_check/_manifest.py", "verbatim", "close check package"),
    ("tools/close_check/_archive.py", "verbatim", "close check package"),
    ("tools/close_check/_sweep.py", "verbatim", "close check package"),
    ("tests/unit/test_close_check.py", "verbatim", "builds its own repo; runs on an empty guide/"),
    ("tests/unit/test_close_check_archived.py", "verbatim", "builds its own repo; passes on an empty archive"),
    ("tools/pace_audit.py", "verbatim", "merge-history pace audit; needs full history"),
    ("tests/unit/test_pace_audit.py", "verbatim", "builds its own repo"),
    ("tools/practice_kit.py", "verbatim", "this tool, so the next project can inherit from yours"),
    ("tests/unit/test_practice_kit.py", "verbatim", "keeps the manifest, the tree and the setup document in step"),
    ("tools/README.md", "adapt", "keep the rows and sections for the tools you copied"),
    ("new_project_practices_setup.md", "verbatim", "the procedure; a new project re-derives it from its own kit"),
)

TIERS = ("verbatim", "adapt", "skeleton")

GITIGNORE_LINES = """
# Agent-harness config is local, EXCEPT the checked-in agent definitions.
# Without the negation a new agent file is silently ignored and never committed.
.claude/*
!.claude/agents/
!.claude/skills/
"""

SKELETONS: dict[str, str] = {
    "guide/README.md": """# guide/

**Forward-looking planning and todos.** Once a segment ships, move its plan
into `guide/archive/` and add its row to `guide/archive/README.md` in the
same change. `tests/unit/test_guide_indexes.py` reads this table: a file in
this folder must match a row below, by name or by documented shape.

| Path | What it is |
|---|---|
| `todo_master.md` | Done / Upcoming roadmap. |
| `deferred_consolidated.md` | Everything scoped but not scheduled. |
| `segment_plan_template.md` | The shape every segment plan copies. |
| `sweep_template.md` | The shape every spec/docs sweep copies. |
| `segment_*.md` | Live segment plans. |
| `sweep_<YYYY-MM-DD>_<scope>.md` | Dated sweep records. |
| `codebase_assessment_*.md` | Dated code-vs-spec snapshots. |
""",
    "guide/archive/README.md": """# guide/archive/

**Shipped and superseded planning documents — historical reference only.**
Whenever a file is added here, add its row in the same change; the
archive is a closed set, so every row names one file and none is a
pattern (`tests/unit/test_guide_indexes.py`).

| Path | What it was | Archived |
|---|---|---|
""",
    "guide/todo_master.md": """# Roadmap

## Done

- (nothing yet)

## Upcoming

- Segment 01 — repository setup: the practice kit, CI, the first spec.
""",
    "guide/deferred_consolidated.md": """# Deferred — consolidated

Everything scoped but not scheduled, one entry per item with the reason it
waits and what would unblock it.

- (nothing yet)
""",
    "spec/README.md": """# spec/

**The surface contracts.** One document per surface or subsystem, written
at a segment's close to match what shipped (constitution I). This table is
the index `spec-writer` and `app/web/spec_registry.py` point at.

| Path | Covers |
|---|---|
| `README.md` | This index. |
""",
    "docs/README.md": """# docs/

**Operational documents**: state, setup, deployment, security posture.

| Path | What it is |
|---|---|
| `status.md` | Implementation state and segment history. Authoritative. |
| `unenforced_conventions.md` | Conventions deliberately left to prose (constitution VI). |
""",
    "docs/status.md": """# Status

**As of:** <date>. **Segment 01 — repository setup** is open.

## Segment history

| Date | Segment | What shipped |
|---|---|---|
| <date> | Practice kit | The practice inherited from `review-robin-web` via its `tools/practice_kit.py`, adapted per `new_project_practices_setup.md`. |
""",
    "docs/unenforced_conventions.md": """# Unenforced conventions

The short list constitution VI promises: rules that stay prose because no
code constant exists to derive a check from. Revisit each when one appears.

| Convention | Why no check | Revisit when |
|---|---|---|
| (none yet) | | |
""",
}


def manifest_paths() -> list[str]:
    return [path for path, _tier, _note in MANIFEST]


def render_table() -> str:
    lines = ["| Path | Tier | Note |", "|---|---|---|"]
    for path, tier, note in MANIFEST:
        lines.append(f"| `{path}` | {tier} | {note} |")
    return "\n".join(lines)


def export(dest: pathlib.Path, source: pathlib.Path = REPO, force: bool = False) -> list[str]:
    """Copy the kit into ``dest``. Returns one report line per manifest entry."""
    report: list[str] = []
    for path, tier, _note in MANIFEST:
        target = dest / path
        if tier == "skeleton":
            if path == ".gitignore":
                existing = target.read_text() if target.exists() else ""
                if ".claude/*" in existing:
                    report.append(f"kept     {path} (negation lines present)")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as fh:
                    fh.write(GITIGNORE_LINES)
                report.append(f"appended {path}")
                continue
            if target.exists() and not force:
                report.append(f"kept     {path} (exists)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(SKELETONS[path], encoding="utf-8")
            report.append(f"skeleton {path}")
            continue
        src = source / path
        if not src.is_file():
            report.append(f"MISSING  {path} (not in source)")
            continue
        if target.exists() and not force:
            report.append(f"kept     {path} (exists)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        report.append(f"{tier:8} {path}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the manifest as a markdown table")
    ap.add_argument("--export", metavar="DEST", help="copy the kit into DEST")
    ap.add_argument("--force", action="store_true", help="overwrite files that already exist in DEST")
    args = ap.parse_args(argv)
    if args.list:
        print(render_table())
        return 0
    if args.export:
        dest = pathlib.Path(args.export).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        lines = export(dest, force=args.force)
        print("\n".join(lines))
        missing = [line for line in lines if line.startswith("MISSING")]
        return 1 if missing else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
