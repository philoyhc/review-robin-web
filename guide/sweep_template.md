# Sweep — <scope> (YYYY-MM-DD)

**Swept:** YYYY-MM-DD · **Scope:** `spec/` + `docs/` + root practice docs
· **Previous sweep:** `guide/sweep_<date>_<scope>.md` (or "none — first
under this template") · **Trigger:** <weeks elapsed / merges since, from
`--stale`>

<!--
Copy to guide/sweep_<YYYY-MM-DD>_<scope>.md. The date in the filename is
read by tools/close_check.py --stale to find the last sweep, so keep the
YYYY-MM-DD_ shape exactly.

A sweep is not a segment plan. It produces findings; the fixes ship
afterwards as ordinary work. It carries no "Doc impact" section and
close_check.py does not read it. Delete these comments as you fill in.

Planned in guide/segment_19A_spec_documentation.md Item 2.
-->

## 0. Carried forward

<!--
FIRST, before opening anything new. This section is the reason the
template exists: the 2026-05-11 sweep found two Tier-1 spec gaps and the
next sweep never re-read them, so they sat open 117 days and closed only
on 2026-09-05 (#2101). A finding is closed as **done**, **moot** (the
code moved underneath it) or **declined** (with a reason) — never
dropped silently. If the previous sweep left nothing open, say so.
-->

| Finding | From | Age | Now | Note |
|---|---|---|---|---|
| <finding> | YYYY-MM-DD | N d | done / moot / declined | <reason if declined> |

## 1. Write or deepen

<!--
A surface with no adequate spec. This is the disposition that produced
the 117-day gap, so it goes first among the new findings.

Note what the automated checks CANNOT see here, because this is the only
place it gets caught: tests/unit/test_spec_coverage.py fails a routing
module with no spec at all, but says nothing about a spec that exists and
is too thin — both 2026-05-11 Tier-1 gaps had sections in
spec/operator_ui_concept.md and would have passed it.
-->

## 2. Update in place

<!-- The doc is right in shape but wrong in detail. One bullet per file:
what it says, what the code does, which wins. -->

## 3. Consolidate

<!-- Two docs covering one thing. Name the survivor, the donor, and what
moves. A consolidation is a retirement plus an update — say both. -->

## 4. Retire

<!-- Dead. Name what replaces it and every inbound reference that must be
repointed first (see the dead-cross-reference command below). -->

## 5. Move

<!-- Right content, wrong folder — e.g. a docs/ file that has become a
contract and belongs in spec/. -->

## 6. Read, no action

<!--
Name every in-scope file read and found current. This is not padding: it
is what makes silence mean something. A file that appears in neither the
findings nor this list was NOT read, and section 7 says so.
-->

## 7. Not read

<!-- In-scope files this sweep did not open, and why (out of time, out of
scope for a partial sweep). A partial sweep is fine; a partial sweep that
implies completeness is not. -->

## Headline numbers

<!-- Filled at the end. Comparable between sweeps only if the shape stays
fixed — that is the point of a template. -->

| | |
|---|---|
| In scope | N |
| Read | N |
| Findings | N (write N / update N / consolidate N / retire N / move N) |
| Carried in / closed / still open | N / N / N |

---

## How to run one

Entry points, in order. None of these is a finding on its own — they
order the reading.

**1. Staleness.** The files no segment touched are the ones no close
check will ever look at (`close_check.py` reads only paths a plan
*committed* to).

```bash
python3 tools/close_check.py --stale --since <previous sweep date>
```

Read the marked files first. Staleness is a prompt, never a finding: a
spec untouched for 117 days may be perfectly correct, and
`spec/blob_storage.md` is a deliberate stub.

**2. Dropped commitments.** A plan that named a spec and never edited it
points straight at a page worth reading.

```bash
python3 tools/close_check.py --archived
```

**3. Orphan specs** — live specs no routing module maps to.

```bash
python3 - <<'PY'
import pathlib, sys; sys.path.insert(0, ".")
from app.web.spec_registry import SPEC_COVERAGE
mapped = {p for paths in SPEC_COVERAGE.values() for p in paths}
for p in sorted(pathlib.Path("spec").rglob("*.md")):
    if "archive" not in p.parts and p.name != "README.md" and p.as_posix() not in mapped:
        print(p)
PY
```

Most hits are legitimately cross-cutting (`architecture.md`,
`ui_elements.md`, the visual-style pair, `rrw_functional_spec.md`) and
some are deliberate — three specs were unmapped on 2026-09-05 for
describing a model rather than a route. Read the list for the one that
surprises you. Sizing a `CROSS_CUTTING` allowlist from several sweeps'
worth of this list is what would decide Item 3's deferred orphan-spec
test.

**4. Dead cross-references** — backticked paths that no longer exist.

```bash
python3 - <<'PY'
import re, pathlib
PATH = re.compile(r"`((?:spec|docs|guide|tools|app|tests)/[A-Za-z0-9._/-]+\.(?:md|py))`")
for f in list(pathlib.Path("spec").rglob("*.md")) + list(pathlib.Path("docs").rglob("*.md")):
    if "archive" in f.parts:
        continue
    for m in sorted(set(PATH.findall(f.read_text()))):
        if not pathlib.Path(m).exists():
            print(f"{f}: {m}")
PY
```

Judgement required on `docs/status.md`: it is a dated timeline, so a
reference to a since-retired file is history, not drift. Elsewhere a dead
path is a finding.

**5. Read the diff since the last sweep** for the areas the four
mechanical passes did not reach.

```bash
git diff --stat "$(git rev-list -1 --before=<previous sweep date> origin/main)"..HEAD -- app/ | tail -30
```

A bare date is not a git revision, hence the `rev-list` — `git diff
2026-08-18..HEAD` fails.

## What a sweep is not

- **Not a gate.** It recommends; a person decides and the fixes ship as
  ordinary work. Nothing here fails CI (`constitution.md` Article VI).
- **Not the close check.** `close_check.py <id>` verifies one segment's
  declared commitments at its close. A sweep reads the whole folder,
  including everything no plan named. Different cadence, different
  reader — do not run one at the other's moment.
- **Not exhaustive by obligation.** A bounded sweep that finishes beats a
  complete one that is abandoned. Say what you did not read (section 7).
