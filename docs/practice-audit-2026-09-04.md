# Practice audit — 2026-09-04

**Repository:** `philoyhc/review-robin-web` · **Head at audit:** `main` @ `6d13aad9`
(PR #2084 merged 2026-09-04 07:33 UTC) · **History examined:** 4,460 commits,
2026-04-27 → 2026-09-04.

<!-- retired-term-ok: file -->

> **Status (updated 2026-09-04).** Both recommendations are implemented and
> the withdrawn one stays withdrawn. R1 (documentation-drift test) shipped in
> **#2086** as `tests/unit/test_doc_conventions.py`, together with the six
> live violations it caught. R2 (fresh-context diff reviewer) shipped in
> **#2087** as `.claude/agents/diff-reviewer.md`, alongside the `CLAUDE.md`
> de-duplication and stale-CI-claim fixes logged in §3. The §5 carry-forward
> item about writing the merge policy down shipped in **#2088**
> (`CONTRIBUTING.md` "When to wait for CI"), which also added
> `new_project_practices_setup.md`, the portable version of §5 for a new
> repository. **Branch protection was not added** — see §1 and §3.
>
> Appendix A's one **Behind** score, context hygiene, was closed after the
> appendix was written: `CLAUDE.md` went 266 → 183 lines and the twin-file
> convention it cited as unenforced is now a test (#2092). A.2, A.5 and §5
> carry dated "closed" annotations recording that; the original findings are
> preserved alongside them rather than rewritten.
>
> The findings below are the record as it stood on the audit date and are
> left unedited. Two things noted here rather than in the text: the
> `diff-reviewer` has not yet been run against a real diff (it parses and the
> harness loads it, which is all that has been demonstrated), and the check
> shipped in #2086 needed a file-level escape hatch that the version printed
> in §4 lacks — this document itself was the first thing it wrongly flagged.

**Question asked.** Two gaps were suspected in the development practice: that
project conventions are held in place by the developer noticing violations
rather than by anything that fails, and that nothing sits between code being
generated and code landing. This document reports what the evidence shows.

**Method.** Configuration was read, but every claim about what is *enforced*
was established by running a deliberate violation and observing the result.
Where a check could not be run, that is stated in **Limitations** rather than
inferred. All commands were run against a scratch copy of the repository at
the head above, on Python 3.12 with `pip install -e ".[dev]"`.

Baseline for every falsification run: `ruff check .` → *All checks passed*;
`pytest -n auto` → **2,697 passed, 17 skipped** in ~35 s.

---

## 1. What the real gate is

**The merge gate is the author's judgement, applied per-change according to
what the change touches — and on this evidence it is applied correctly.**

The mechanical part of that sentence is easy to establish. The `main` branch
carries no protection rule (`GET /repos/philoyhc/review-robin-web/branches`
returns `"protected": false`), so neither CI workflow is a required status
check and no failure can stop a merge. Nothing blocks.

The interesting part is what the author does with that freedom. Across the 23
most recent merged pull requests whose runs could be resolved, **9 were merged
before the `CI - Postgres` job on their head commit had finished** — between
4 s and 168 s ahead of it. Taken alone that reads as a gap. It is not, because
of what those nine PRs contained:

| PR | app code | `app/db/` | `alembic/` | tests | what it touched |
|---|---|---|---|---|---|
| #2084 | 0 | 0 | 0 | 0 | `guide/` only — docs |
| #2082, #2080, #2074, #2073, #2072, #2068, #2066, #2064 | 0 | 0 | 0 | 0 | `tools/` only — the dev-only theme customizer |

**Not one of the nine touched application code, a model, a migration, or a
test.** Eight are the developer-only theme-customizer harness; one is
documentation. The suite could not have said anything about any of them.

The complementary test is the one that matters, and it holds. Scanning the
**last 244 pull-request merges** on `main` (2026-06-07 → 2026-09-04), only
**four** touched `alembic/` or `app/db/` — #2003, #1977, #1927, #1875. Of the
three whose CI runs could be retrieved, **all three waited for `CI - Postgres`
to report green before merging**: #1977 by 282 s, #1875 by 429 s, #1927 by
6,046 s. (#2003's run was not in the pages retrieved — see **Limitations**.)

So the practice is: risk-stratify the change, wait for the dialect job when it
could possibly matter, merge ahead of it when it provably cannot. That is a
defensible policy, and the record shows it being followed rather than merely
intended. The structural observation still worth recording is that the deploy
workflow (`main_app-review-robin-web-dev.yml`) triggers on push to `main` and
declares no dependency on either CI workflow, so a red `CI - Postgres` would
not stop `alembic upgrade head` running against Azure Postgres. That coupling
is absent by configuration and present by discipline; see §3 for why this is
recorded rather than recommended against.

### Inventory of automated checks

| Check | Where | Automatic? | Scope | Blocking? |
|---|---|---|---|---|
| `ruff check .` | `ci.yml` job `test` | Yes | PRs to `main` + push to `main` | **No** — reports only; `main` is unprotected |
| `pytest -n auto` (SQLite) | `ci.yml` job `test` | Yes | PRs to `main` + push to `main` | **No** — same |
| `alembic upgrade head` (Postgres 16) | `ci-postgres.yml` job `postgres` | Yes | PRs to `main` + push to `main` | **No** — same |
| `alembic downgrade base` + `upgrade head` round-trip | `ci-postgres.yml` | Yes | as above | **No** — same |
| `pytest -q` against Postgres 16 | `ci-postgres.yml` | Yes | as above | **No** — same |
| `audit_events` `EVENT_SCHEMAS` strict mode | `app/services/audit.py`, enabled by `tests/conftest.py` | Yes | every emit exercised by a test | **Yes** — fails the suite (see §3) |
| `alembic upgrade head` (production) | deploy workflow `migrate` job | Yes | push to `main` | **Yes, for deploy only** — `deploy` needs `migrate`; it does **not** need CI |
| Pre-commit hooks | — | **None exist** (`.git/hooks` holds only samples; no `.pre-commit-config.yaml`) | — | — |
| Type checking | — | **None configured** (no mypy/pyright config or dependency) | — | — |
| PR template | — | **None** (no `pull_request_template.md` anywhere) | — | — |
| `CONTRIBUTING.md` checklist | `CONTRIBUTING.md` §"Pull request checklist" | No — prose only, not rendered into a PR body | — | **No** |

One configuration detail worth correcting: `pyproject.toml` sets
`line-length = 100`, but `ruff check` does not enforce it. Ruff's default rule
selection (`E4`, `E7`, `E9`, `F`) excludes `E501`, so the setting only affects
the formatter, which is not run. Adding a 240-character line to `app/config.py`
left `ruff check .` passing, and 337 Python lines in the repository already
exceed 100 characters (8 of them under `app/`) with CI green. This is a note,
not a finding — the line length is not load-bearing — but it is an example of
a configured value reading as an enforced one.

---

## 2. Findings

Enforcement status is: **mechanical** (a named check fails), **review** (a
human or agent reading the diff would plausibly catch it), or **unenforced**
(nothing fails and nothing routinely looks).

| # | Convention | Written down at | What checks it | Status | Evidence |
|---|---|---|---|---|---|
| 1a | Lifecycle enum → display label goes through one mapping, **in code** | `spec/session_home.md` §"Lifecycle state vocabulary"; docstring of `app/services/lifecycle_display.py` | `tests/unit/test_lifecycle_display.py:35` pins `DISPLAY_LABELS` exactly; `tests/integration/test_operator_sessions.py:871` asserts the rendered pill | **Mechanical** | All four lifecycle-pill render sites go through the `lifecycle_label` filter; no Python module hard-codes a lifecycle label |
| 1b | …and the **specs** state that mapping correctly | same | **Nothing** | **Unenforced — and currently violated** | `expired → "Closed"` landed 2026-06-01 (`d65e825a`). Three months later `spec/lifecycle.md:43`, `spec/session_home.md:20` and `spec/operator_ui_concept.md:36` still say "Expired"; only `spec/rrw_functional_spec.md:634` is correct. The pinning test's own docstring cites `spec/session_home.md`, which contradicts it |
| 1c | Bypassing the mapping in a template | same | **Nothing** | **Unenforced** | **V1:** replacing `{{ s.status \| lifecycle_label }}` with `{{ s.status \| capitalize }}` in `sys_admin_sessions.html` → ruff passes, **2,697 tests pass** |
| 2 | Retired terminology (pre-19B button names) must not appear | `CLAUDE.md` lines 29–31 | **Nothing** | **Unenforced — and currently violated** | `spec/rehydrate.md:117,184` prescribe "Primary Outline" — in a spec *created* by the Segment 19 documentation sweep (`3c24e13a`, 2026-08-19). Also `app/web/templates/base.html:1896` and its two generated copies in `tools/`. **V2:** adding "Alert Outline / Danger Outline" to `spec/setup_pages.md` and `class="btn alert-solid"` to a live template → ruff passes, **2,697 tests pass** |
| 3 | British spelling in documentation | **Nowhere** — no mention of British/en-GB/Oxford spelling in any `.md` in the repository | **Nothing** | **Unenforced, and not a convention the repository states** | Usage is mixed, including inside `CLAUDE.md` itself: "behaviour" at line 54, "behavior" at lines 21 and 225. Across live `.md` prose: behaviour 79 / behavior 30; grey 35 / gray 12; centre 6 / center 9; defence 4 / defense 9 |
| 4 | No `sqlalchemy.dialects.postgresql` imports in `app/db/models/` | `CLAUDE.md` (stated three times: lines ~15, "Architecture at a glance" §3, "Stack summary") | **Nothing directly** | **Unenforced** | **V4:** importing `JSONB` into `app/db/models/review_session.py` without using it → ruff passes (`F401` catches it only without a `noqa`), **2,697 tests pass**. **V4b:** using `JSONB` as a column type → 34 errors, but from `UnsupportedCompilationError` (SQLite cannot compile `JSONB`), i.e. a dialect accident, not enforcement. A dialect import SQLite tolerates would pass |
| 5 | `audit_events` detail envelope + `EVENT_SCHEMAS` registration | `CLAUDE.md` §"Audit events"; `app/services/audit.py:10` | `settings.audit_strict_mode`, switched on by `tests/conftest.py`; validated on every write | **Mechanical** | `app/services/audit.py:199,756` raise on an unregistered `event_type`; the error message names `EVENT_SCHEMAS in app/services/audit.py` |

A third falsification, **V3** — inserting "centers the colour organization"
into `CLAUDE.md`, flipping a "behaviour" in `spec/lifecycle.md`, and mixing
"focussed / normalise / finalize" into `CONTRIBUTING.md` — also left ruff and
all 2,697 tests passing. It is reported here rather than as a finding because
the convention it violates is not one the repository states (row 3).

### Frequency evidence

Of the 30 most recent fix/correction commits on `main` (2026-05-16 →
2026-09-04), **six touched only documentation and existed solely to correct
drift**: `585372fa` (a spec prescribing behaviour the code did not have),
`61ce86c0` ("Correct three doc inaccuracies against actual code"),
`4befdcec`, `7b055d1c`, `3f09441d`, `deec2db9` ("carried forward the stale
May 11 framing without verifying"). That is one in five fix commits over a
16-week span — comfortably clearing the "recurred at least twice" bar for a
remedy, and it excludes the five live violations in the table above, which
have not yet been noticed at all.

The decisive evidence is not the count. It is that the drift in finding 1b
survived a **deliberate, whole-folder manual hygiene sweep**. The Segment 19
documentation arc (`ab5125a6` whole-`spec/` drift sweep 2026-08-18, `78efaca7`
"Sweep spec/ + docs/ for the Segment 19B consistency changes" 2026-08-19,
`049dd1c9` closing the docs sweep) re-read these exact files —
`spec/lifecycle.md` was last touched by that sweep — and did not catch a
three-month-old, single-word, two-place contradiction. Vigilance is not
failing here through carelessness. It is failing at the thing vigilance is
structurally bad at.

A smaller demonstration of the same point, from this audit: an early grep in
this investigation missed `spec/visual_style_rrw.md:11` because that line
happens to contain the substring `guide/archive/`, which the `grep -v
'/archive/'` filter removed. Ad-hoc grepping is exactly the mechanism under
audit, and it silently under-reported.

---

## 3. Nothing to close

Several things that could plausibly have been gaps are already sound. Naming
them is as much the point of this audit as the corrections.

- **The merge discipline works, and branch protection is not needed to make
  it work.** This was the audit's leading hypothesis and the evidence
  contradicts it. Every early merge in the sample was docs-only or
  `tools/`-only; every database-touching PR waited for the Postgres job. The
  policy in force — stratify by what the change touches, wait when it could
  matter — is the same policy a required-status-check rule would impose, minus
  the friction on the ~95% of PRs where the dialect job is irrelevant. Making
  the checks required would codify an existing habit, not close a gap, and the
  same is true of adding a `needs: test` edge to the deploy pipeline. Both
  remain available as cheap belt-and-braces if the cadence ever changes (a
  second contributor, a return to migration-heavy segments), which is why the
  configuration facts are recorded in §1. Neither is recommended now.
- **Change flow is genuinely PR-based.** All 50 of the last 50 first-parent
  commits on `main` are pull-request merges; the only three direct commits in
  the last 200 are `Update quickstart.md` edits made through the GitHub web UI
  on 2026-08-15.
- **CI coverage itself is not the weak point.** Both dialects run on every
  pull request, the Alembic chain is round-tripped in both directions against
  Postgres 16, and lint runs. The suite is fast (~35 s on 2,697 tests with
  `-n auto`).
- **The enum/label convention holds in code.** All four lifecycle-pill render
  sites use the filter, `DISPLAY_LABELS` is pinned by an exact-equality test,
  and the rendered output is asserted in an integration test. Only the prose
  drifted. The suspicion that this convention rests on vigilance is **half
  right and worth stating precisely**: the code half is mechanised, the
  documentation half is not.
- **The project already knows how to mechanise a convention.** The
  `EVENT_SCHEMAS` strict-mode gate is a working, in-repository example of
  turning a prose rule into a failing test. Recommendation 1 below is that
  pattern applied a second time, not a new idea.
- **A review layer partly exists.** `.claude/agents/spec-writer.md` is a
  subagent whose stated purpose is "so the specs never drift from reality",
  and twelve dated codebase assessments run from 2026-05-09 to 2026-08-19.
  These work when run — `2fdfe57e` fixed two real logic bugs surfaced by the
  17-May assessment, both landing with regression tests.
- **`CLAUDE.md` is longer than the ~100-line guidance but not bloated with
  rules.** It is 265 lines / 2,752 words, of which the "Where to look" index
  is 27 lines and "Architecture at a glance" plus "Stack summary" are 127
  lines of orientation. Roughly 12 bullets are genuinely normative. Two things
  are worth a five-minute edit rather than a recommendation: **"Workflow
  notes" (lines 239–242) and "Where work runs" (lines 244–256) restate the
  same three instructions back to back**, and both say lint is not yet in CI —
  "(and `ruff` once wired into CI)" at line 241, "(and lint, once it's wired
  into CI)" at line 249 — which is **stale**: `ci.yml` lines 27–28 have run
  `ruff check .` for some time. The `dialects.postgresql` ban appears three
  times and the "no frontend framework" rule four times. The file's
  mechanically checkable rules are cross-referenced into Recommendation 1
  rather than counted separately.

---

## 4. Recommendations

Two. The third slot is deliberately unused: the branch-protection
recommendation this audit expected to make was withdrawn once the merge
timings were read against what each PR contained (§3).

### R1 — One test that fails on documentation drift

**What to do.** Add `tests/unit/test_doc_conventions.py` (below). It derives
the expected labels from `DISPLAY_LABELS` itself, so it cannot go stale when
the mapping changes, and it follows the existing `EVENT_SCHEMAS` idiom: the
rule lives in code, and drift fails a test. No new tool, no new dependency, no
new service. It runs in **0.08 s**.

Run against the current tree it fails, naming five genuine violations and one
line needing a one-time marker:

```
spec/lifecycle.md:43: `expired` documented as 'Expired', mapping says 'Closed'
spec/operator_ui_concept.md:36: `expired` documented as 'Expired', mapping says 'Closed'
spec/session_home.md:20: `expired` documented as 'Expired', mapping says 'Closed'
spec/operator_button_audit.md:283: 'Primary Outline'
spec/rehydrate.md:117: 'Primary Outline'
spec/rehydrate.md:184: 'Primary Outline'
```

Fixing those six lines is the other half of the afternoon.
`spec/operator_button_audit.md:283` and `spec/visual_style_rrw.md:11` are
deliberate historical references ("Reclassified from Primary Outline to
Secondary in 18R Item 3"); they take the inline escape rather than an edit.

```python
"""Guard the two documentation conventions that only prose enforces.

Same idea as the ``EVENT_SCHEMAS`` strict-mode gate in
``app/services/audit.py``: the rule lives in code, so drift fails a
test rather than waiting for someone to notice it.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.lifecycle_display import DISPLAY_LABELS

REPO = Path(__file__).resolve().parents[2]

# Live prose only — archived docs are a historical record, not a contract.
LIVE_DOCS = sorted(
    p
    for p in list((REPO / "spec").rglob("*.md")) + list((REPO / "docs").rglob("*.md"))
    if "archive" not in p.parts
)

# Terminology CLAUDE.md declares superseded (spec/ui_elements.md §6 carries
# the canonical .btn roles).
RETIRED_TERMS = ("Primary Outline", "Alert Outline", "Danger Outline")
# Deliberate historical references carry this marker on the same line.
TERM_ESCAPE = "<!-- retired-term-ok -->"

# `| `enum` | Label |` rows in a lifecycle table.
ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*\*{0,2}([A-Za-z]+)\*{0,2}\s*\|")


def test_lifecycle_tables_match_the_display_label_mapping() -> None:
    """Every live spec table must agree with ``DISPLAY_LABELS``."""
    wrong: list[str] = []
    for doc in LIVE_DOCS:
        for n, line in enumerate(doc.read_text().splitlines(), 1):
            m = ROW.match(line)
            if not m:
                continue
            enum, label = m.group(1), m.group(2)
            if enum not in DISPLAY_LABELS:
                continue
            if label != DISPLAY_LABELS[enum]:
                rel = doc.relative_to(REPO)
                wrong.append(
                    f"{rel}:{n}: `{enum}` documented as "
                    f"{label!r}, mapping says {DISPLAY_LABELS[enum]!r}"
                )
    assert not wrong, "lifecycle display-label drift:\n  " + "\n  ".join(wrong)


def test_retired_button_terminology_is_absent_from_live_docs() -> None:
    """The pre-19B button names must not be prescribed anywhere live."""
    hits: list[str] = []
    for doc in LIVE_DOCS:
        rel = str(doc.relative_to(REPO))
        for n, line in enumerate(doc.read_text().splitlines(), 1):
            if TERM_ESCAPE in line:
                continue
            for term in RETIRED_TERMS:
                if term in line:
                    hits.append(f"{rel}:{n}: {term!r}")
    assert not hits, (
        "retired button terminology (superseded by the canonical .btn "
        "roles in spec/ui_elements.md §6):\n  " + "\n  ".join(hits)
    )
```

**What breaks if it is not done.** The `expired → "Closed"` contradiction has
stood for three months and survived a deliberate whole-folder sweep. The specs
are the input an agent reads before writing code; a spec that states the wrong
display label is an instruction to write the wrong display label. The cost is
not the stale word — it is that `spec/` stops being trustworthy at exactly the
points where it has quietly diverged, and nobody can tell which points those
are.

**Do not extend this to spelling.** A British-spelling check would be the
third obvious candidate and it should be **rejected**. It cannot distinguish
prose from identifiers — `color`, `gray`, `catalog` and `normalize` are CSS
token names, primitive family names and function names in this repository, and
`-ize` is valid Oxford spelling — so it would need an allowlist that grows
with every new token. More to the point, the convention **is not written down
anywhere in the repository**, and `CLAUDE.md` uses both spellings itself. The
cheap fix, if the convention is wanted, is one line in `CLAUDE.md` stating it.
A checker for an unstated preference would be tuned forever and then ignored.

### R2 — Make the review pass routine instead of episodic

**What to do.** Add a fresh-context reviewer alongside the existing
`spec-writer` agent and run it on each PR's diff before merging. The
infrastructure already exists — `.claude/agents/` — so this is a file, not a
system.

```markdown
---
name: diff-reviewer
description: Reads a PR diff cold and checks it against the specs. Run before merging.
tools: Read, Grep, Glob, Bash
---
You review one diff with no prior context about why it was written.
Assume the tests pass — they do, and they are not what you are for.

Read the diff (`git diff main...HEAD`). Then, for each changed area:

1. Identify which `spec/` document governs it. Read that section.
   Report anything the diff does that the spec does not describe, and
   anything the spec requires that the diff omits.
2. Report claims in the commit message or PR body that the diff does
   not support — "also updates X" when X is untouched, "per spec Y"
   when Y says something else.
3. Report scope the diff carries beyond its stated purpose: unrelated
   fixes, drive-by renames, changes to files the stated purpose does
   not reach. `CLAUDE.md` forbids bundling these.
4. Report inconsistency with sibling modules — a new route in
   `routes_operator/` importing across slices, a service returning a
   shape unlike its neighbours, a template using inline styles where
   `base.html` defines a class.
5. Where the diff changes a user-visible string, enum, or button role,
   check whether a `spec/` document states the old value.

Report findings as: file:line, what you expected from the spec, what
the diff does. State your confidence. Report nothing if nothing is
wrong — a clean pass is a useful result.

You will not catch: rendering, layout, or in-browser JS behaviour.
Those need the dev slot, not a reader.
```

**What it will and will not catch.** Of the last 30 fix commits, **six (20%)
were documentation corrections** of exactly the kind steps 1 and 5 target, and
**nine (30%) were logic bugs that landed with regression tests** — several
discovered by review-like activity rather than by the suite (`2fdfe57e` from
the 17-May assessment; the case-insensitive-email P0 at `ab043317`, found by a
Codex pass and fixed with 265 lines of new tests across four files, which
existed only because a fresh reader thought of the case). It will **not** catch
the remaining **fifteen (50%)**, which are browser-only defects — caption
selectability, a 4 px misalignment, Space toggling a card — touching only
templates and `tools/`. Those need the Azure dev slot, and the practice already
uses it. The honest claim is that this closes the documentation-drift class
and adds a second reader on logic, not that it replaces manual verification.

**What breaks if it is not done.** The review pass this project already
benefits from is episodic — the Codex campaign was one cluster on 2026-06-05,
and the codebase assessments are periodic snapshots, not per-change. Between
them, a diff goes from written to merged with nothing reading it. That is the
structural gap the audit suspected, and unlike the merge-gate hypothesis this
one survives contact with the evidence. What the evidence adjusts is its size:
the highest-frequency defect class is one no reviewer could catch either.

---

## 5. Carry to the RA platform

**Set up at project start — generalises:**

- **The "convention as failing test" idiom.** Not this specific test — the
  pattern of deriving a documentation check from the code constant it
  documents, so the check cannot go stale. RRW's `EVENT_SCHEMAS` gate and the
  proposed `DISPLAY_LABELS` gate are the same move. Any project with a
  code-facing enum and a user-facing label needs it, and it is far cheaper to
  add when there are three specs than thirty.
- **A fresh-context diff reviewer, from the first PR.** Retrofitting means it
  first runs against a large surface it has no history with. Run from the
  start, each pass is one small diff against one small spec.
- **A stated merge policy, written down rather than held in the head.** The
  substantive finding of §1 is that RRW's stratification policy is sound and
  followed — but it exists only as the author's judgement. One paragraph in
  `CONTRIBUTING.md` ("wait for the Postgres job when the diff touches
  `alembic/`, `app/db/`, or any service that queries; merging ahead of it is
  fine for docs and dev tooling") costs nothing and survives a second
  contributor or a six-month gap. This is the cheap version of branch
  protection and probably the right one at this scale.

**Specific to RRW — do not carry:**

- The lifecycle enum/label divergence (`ready → "Activated"`, `expired →
  "Closed"`) is a consequence of a naming decision RRW chose not to undo. A new
  platform should name the enum correctly and never need the mapping.
- The retired pre-19B button vocabulary is RRW's own migration debt.
- The SQLite-for-tests / Postgres-for-production split is what makes migration
  portability a live hazard here, makes the `ci-postgres` job load-bearing, and
  makes the stratification policy necessary in the first place. A project
  testing against its production dialect inherits none of this and should not
  import the ceremony that manages it.
- The twin `CLAUDE.md` / `AGENTS.md` files kept in sync by hand ("No automation
  enforces this yet"). They are byte-identical today, but this is a second
  unenforced convention. A symlink, or a single file, avoids it — cheap at
  project start, awkward later. **(Closed 2026-09-04 in #2092 by a third check
  in `tests/unit/test_doc_conventions.py` — the retrofit, not the cheap
  version. The advice stands unchanged for a new project.)**

---

## 6. Limitations

- **One of the four database-touching PRs could not be checked.** #2003's
  `CI - Postgres` run did not appear in the three pages of `pull_request`
  workflow runs retrieved, so its merge time could not be compared against a
  CI completion. The three-for-three result in §1 is three of four, not four
  of four.
- **The merged-before-CI figures cover 23 of the last 30 merged PRs.** Seven
  (#2055–#2061) fell outside the run pages retrieved. The nine early merges
  are a floor, not a total — though since all nine proved to be docs/tooling,
  a higher figure would not change the conclusion.
- **The database-touching scan covers 244 merges (2026-06-07 → 2026-09-04),
  not the full history.** That window is dominated by UI, tooling and
  documentation segments; a migration-heavy stretch earlier in the project
  would test the stratification policy harder than this sample does.
- **CI could not be made to fail on demand.** Running the deliberate
  violations through the real CI gate would have required pushing a branch,
  which the audit's terms exclude. The local suite is a faithful stand-in for
  the `test` job (same `pytest`, same `ruff`), but the `postgres` job was not
  exercised; no Postgres 16 was available in the audit container. The V4b
  result (`JSONB` → `UnsupportedCompilationError`) is SQLite-specific and
  would not reproduce on the Postgres job — a dialect import that works on
  Postgres would pass there, which if anything strengthens finding 4.
- **The "last 30 fix commits" classification is by files touched and commit
  message, not by reading each diff.** The 50% / 20% / 30% split is a
  well-grounded shape, not a precise measurement; the boundary cases are
  commits touching both templates and Python.
- **Whether a reviewer "would plausibly have caught it by eye" is a judgement,
  not a measurement.** For the documentation class it is supported by the
  Codex P0 (`ab043317`) — a real defect a fresh reader found and 2,697 tests
  did not. For the browser class it is supported by the absence of any JS
  runtime in the suite, a gap the project has itself filed (`5eebec53`, "file
  the template-JS runtime-test gap in deferred_consolidated"). Neither is
  proof.
- **Frequency counts exclude `guide/archive/`,** on the grounds that archived
  documents are a historical record rather than a live contract. A different
  choice would raise every count in §2 without changing any conclusion.
- **`tests/unit/test_doc_conventions.py` does not exist in the repository.**
  It was written and run against a scratch copy; the output quoted in R1 is
  real, but nothing from this audit has been committed beyond this document.

---

# Appendix A — Benchmark against current practice (2026-09-04)

**What this is.** The audit above judged the practice against itself: what is
enforced here, what recurs here. This appendix judges it against the outside
— specifically **loop engineering**, the discipline named in June 2026, and
the accumulated 2026 evidence on **vibe coding** and the **spec-driven
development** movement that defines itself against it.

**Evidentiary standard — weaker than the audit body, deliberately flagged.**
Every claim in §§1–6 was demonstrated by running something. Nothing in this
appendix can be. It rests on secondary sources: practitioner essays, vendor
guides and trade reporting. Several primary sources (Osmani's own Substack,
IBM's explainer) were unreachable from this container's network egress, so
the loop-engineering summary below is assembled from secondary accounts of
them. **Treat the external figures as reported, not verified** — see
"Limitations of this appendix" at the end. Claims about RRW itself carry the
audit's original standard, and are cross-referenced to the section that
established them.

---

## A.1 The benchmark: loop engineering

The term crystallised in June 2026 — Peter Steinberger arguing the skill had
moved from prompting agents to designing their loops, Addy Osmani naming and
structuring the practice the next day. It sits, in Osmani's framing, "one
floor above the harness": you stop hand-writing prompts and start designing
the loop the agent runs inside — what it does between tool calls, when it
checks its own work, how it decides it is finished.

The practice reduces to four pillars, ordered by blast radius:

| # | Pillar | Prevents |
|---|---|---|
| 1 | **Idempotent tools** | a retry corrupting state |
| 2 | **Stop conditions** | a bug looping forever |
| 3 | **Maker–checker split** (a real critic) | confidently wrong output |
| 4 | **Context hygiene** | slow quality rot |

Two claims from that literature matter most here. First: **self-critique does
not count** — models are poor judges of their own work, so the grader must be
split from the generator. Second, the stop condition is not "the agent
believes it is finished" but "**the verifier passes**". The stated threshold
for bothering at all: *if the work has a machine-checkable definition of done
and runs long enough to matter, stop optimising the model and start building
the cage.*

---

## A.2 How RRW scores, pillar by pillar

| Pillar | RRW | Verdict |
|---|---|---|
| Idempotent tools | Largely **not applicable** — no autonomous loop mutates state unattended. The one place it bites is `alembic upgrade head` on every push to `main`, which is idempotent by design. | N/A, honestly |
| Stop conditions | **Not applicable for the same reason.** Nothing here runs unbounded. | N/A, honestly |
| Maker–checker split | **Just closed** (§4 R2, shipped in #2087) after being the audit's live gap. | Level, newly |
| Context hygiene | Was `CLAUDE.md` at 266 lines against a ~100-line guideline, one rule stated 3× and another 4× (§3). **Closed 2026-09-04 in #2092**: 183 lines / 1,631 words, the duplicated section deleted, the 50-module inventory replaced by a pointer. | Was **Behind**; now level |
| Machine-checkable done | `pytest` (2,699), `ruff`, dual-dialect CI, Alembic round-trip, plus the drift gate from R1. | **Ahead** |

**The honest framing is that RRW is not running the kind of loop the
discipline is about.** Its loop is human-verified: an agent proposes, CI
checks what it can, and a person merges. Pillars 1 and 2 exist to stop an
*unattended* loop destroying something; RRW's loop stops every few minutes at
a human. Scoring those two as gaps would be manufacturing findings, which
this audit's own terms forbid.

That framing also explains the §1 result. Loop engineering says the stop
condition should be "the verifier passes, not the agent believes it is
finished". RRW's stop condition is a person's judgement of what the diff
touches — and §1 measured that judgement being applied correctly across 244
merges. What #2088 did was write that stop condition down. In loop-engineering
terms, that is exactly the right move for a human-verified loop: make the
condition explicit and inspectable rather than mechanising it prematurely.

**The one place the benchmark bit hard was pillar 4.** Context hygiene is
last by blast radius but it is not optional, and at the time of writing it was
the pillar RRW measurably failed: the instruction file was 2.6× the guideline,
carried duplicated rules, and until #2087 carried a claim about its own CI that
had been false for months. The literature's phrasing — *loops die of context
bloat before they die of anything else* — described a real exposure, since that
file is loaded into every agent session in the repository.

**Closed 2026-09-04 (#2092).** `CLAUDE.md` went 266 → 183 lines and 2,692 →
1,631 words. The measurements that drove it: "Stack summary" restated **15 of
its 16** claim-bearing phrases from earlier in the same file; "Architecture at
a glance" listed 50 module filenames that `spec/architecture.md` already
carries at the right altitude, and listed them *incompletely*, which is worse
than a pointer because it implies completeness; the two longest index entries
ran to 95 and 88 words. The twin-file convention §5 cites below as unenforced
is now a test. It remains above the ~100-line guideline, deliberately — the
remaining lines are normative or index, and cutting further would cost more
than the bloat did.

---

## A.3 The benchmark: vibe coding, and what replaced it

Karpathy's term (early 2025) for loosely prompting a model and shipping what
comes back. The 2026 reporting on it is uniformly bad, and worth quoting
because RRW is an AI-authored codebase and therefore squarely in the
population being measured:

- code churn **up 41%**; duplication **up 4×**; refactoring down from 25% of
  changed lines (2021) to **under 10%** (2024);
- **95%** of developers report feeling productive while producing measurably
  lower-quality code; in one controlled study, sixteen experienced developers
  in million-line codebases were **19% slower** with AI tools while reporting
  feeling **20% faster**;
- roughly **45%** of AI-generated samples introduced a common OWASP
  vulnerability; March 2026 alone saw **35 CVEs** attributed to AI-generated
  code;
- the qualitative failure: debugging code *nobody fully wrote or owns*.

The counter-movement that went mainstream in 2026 is **spec-driven
development** — specifications as the source of truth, code as a generated or
verified secondary artifact, with the implementing role separated from the
verifying one. Its central claim is worth reading twice against §3 of this
audit: **SDD catches architectural violations and API contract drift that unit
tests structurally cannot.**

That is, almost word for word, the conclusion Investigation C reached from
RRW's own defect history — arrived at independently, from 30 fix commits,
without knowing the movement existed.

---

## A.4 How RRW scores against the vibe-coding failure modes

**RRW is not a vibe-coded codebase, and the evidence for that is specific.**
`spec/` predates the SDD movement's mainstreaming and functions exactly as SDD
prescribes: a `spec-writer` subagent exists to keep specs matched to code;
route/service/model layering is stated and enforced by review; changes land as
small reviewable slices with a stated no-bundling rule; 2,699 tests run on
every PR against two dialects. On the "code nobody owns" failure mode, the
mitigation is unusually strong — commit messages here routinely carry the
*reasoning*, not just the change, and §2's frequency evidence was reconstructable
three months after the fact precisely because of that.

Three qualifications, in descending confidence:

1. **The browser-only blind spot is real and unmitigated by any of this.**
   §4 R2 measured ~50% of recent fix commits as defects no test and no diff
   reader could catch — caption selectability, a 4px misalignment, a keypress
   toggling a card. The project has itself filed the gap (`5eebec53`, the
   template-JS runtime-test gap). Against the SDD claim that specs catch what
   unit tests structurally cannot, this is the class **neither** catches: the
   verifier is a human looking at the Azure dev slot. It is the one part of
   RRW's loop with no machine-checkable definition of done, and it is where
   the defects actually are.

2. **Duplication and churn are not measured here.** The vibe-coding figures
   above are exactly the metrics RRW does not track. `guide/codebase_assessment_*.md`
   tracks LOC and file sizes, not churn or duplication ratio. Whether RRW's
   4× duplication figure is 1× or 4× is simply unknown — and unlike most
   claims in this document, that one could be measured cheaply.

   **Measured 2026-09-04** (`tools/code_metrics.py`, now a standard item in
   the assessments). **Duplication**, production code: 15.8% of lines sit in
   a duplicated block of ≥6 lines, 6.5% at ≥10, 3.0% at ≥15, 1.1% at ≥25.
   Read ≥10 as the headline — the short blocks are import and decorator
   boilerplate, and spot-checking the ≥10 hits found real shared scaffolding
   (`_setup_reviewers.py` and `_setup_reviewees.py` share 40 ten-line
   windows, each ~47% duplicated). Tests run roughly 2.5× that rate, which
   is normal for table-driven integration tests and not obviously worth
   fixing. **Churn**: across all 2,085 first-parent merges, 74.3% of the
   71,862 deleted Python lines were younger than 14 days — but the same
   share of *all* lines in those files at that moment was 77.0%, a **ratio
   of 1.0×**. Deletions here are age-blind, marginally older than ambient:
   the code being deleted was young because the whole codebase was young,
   not because recent work is being specifically rewritten. Surviving `app/`
   code has a median line age of 109 days.

   > **Corrected 2026-09-04, same day.** This paragraph originally read
   > "92.1% … 82.0% … ratio of 1.1×", from a 120-merge sample. Sampling
   > turned out to be the defect: deletions per merge are heavy-tailed and
   > the ratio never settles at any sample size (1.4× / 1.4× / 0.9× / 1.0× /
   > 0.8× / 1.0× / 1.1× / 1.1× / 1.1× at 60 / 120 / 100 / 200 / 300 / 500 /
   > 700 / 1000 / 400). `tools/code_metrics.py` now walks the full history by
   > default, which is deterministic. The conclusion is unchanged; only the
   > figures are. See `guide/codebase_assessment_04sep.md` §6.

   **The bare 74% figure would have been alarming and wrong**, which is why
   the tool reports the baseline beside it and the convention in
   `guide/README.md` says never to quote one without the other. On the
   evidence, RRW does not exhibit the churn pattern the vibe-coding
   literature describes. The duplication finding is real but modest, and the
   two sibling roster slices are the one place a shared helper would pay.

3. **Security posture is documented but not continuously checked.**
   `docs/security_posture.md` is thorough, and §1's inventory found no
   automated security scanning in CI. Against a reported ~45% OWASP-vulnerability
   rate in AI-generated code, "documented" and "checked on every PR" are
   different things. This is a candidate finding for a future audit, not a
   recommendation here — the audit's three-recommendation budget was spent,
   and two of the three were withdrawn or unspent for good reasons.

---

## A.5 Verdict

Measured against the practice as it stands in September 2026, RRW is **ahead
on the thing that is hardest to retrofit and behind on the thing that is
cheapest to fix.**

Ahead: it was doing spec-driven development before the term went mainstream,
and it has a machine-checkable definition of done that most AI-authored
codebases do not. The maker–checker split it lacked is now closed. Its
human-verified loop is a deliberate and defensible shape, not an immature
version of an autonomous one.

Behind: the browser-only defect class, which is both the largest measured
category of real defects here and the one no layer of the current practice
catches. Context hygiene was the other half of this verdict — a 266-line
instruction file with duplicated rules, loaded into every session — and was
closed the same day (#2092, see A.2). It is left in the table above as the
record of what the benchmark found.

Level, and worth stating plainly: nothing in the current discipline suggests
RRW should be running autonomous loops. The threshold — *a machine-checkable
definition of done, and long enough to matter* — is not met by a solo project
whose slices are sized to be reviewed in one sitting.

---

## Limitations of this appendix

- **No claim here was verified by running anything.** That is the difference
  between this appendix and §§1–6, and it is the reason it is an appendix.
- **The external figures are reported, not checked.** The churn, duplication,
  OWASP and CVE numbers come from secondary trade reporting; the "19% slower"
  study is cited second-hand. Primary sources for the loop-engineering
  material (Osmani's Substack, IBM's explainer) were unreachable from this
  container, so that section is assembled from secondary accounts. Any of
  these could be wrong or quoted out of context, and none should be repeated
  as fact without checking the primary source.
- **"Loop engineering" is three months old at the time of writing.** Its
  vocabulary may not survive, and benchmarking against a term that new risks
  measuring a fashion rather than a practice. The four pillars are used here
  because each maps to a failure mode with an independent basis, not because
  the label is settled.
- **The comparison population is not RRW's population.** The vibe-coding
  figures describe teams shipping loosely-prompted code, often at commercial
  scale. RRW is one author, one reviewer-of-record, and a spec folder. Where
  the figures are used above, they are used to name a *risk class*, not to
  assert RRW sits at the reported rate.
- **A.4's claim that RRW "is not a vibe-coded codebase" is a judgement**, not
  a measurement. It is supported by the artefacts named, and it is exactly the
  kind of claim a second reader should be sceptical of when the person making
  it has been working inside the repository all day.

**Sources.** Loop engineering: [ADTmag](https://adtmag.com/articles/2026/07/01/loop-engineering-emerges-as-developers-put-ai-coding-agents-on-repeat.aspx),
[MindStudio](https://www.mindstudio.ai/blog/what-is-loop-engineering-ai-coding-agents),
[explainx.ai](https://explainx.ai/blog/what-is-loop-engineering-ai-agents-2026),
[Tosea](https://tosea.ai/blog/loop-engineering-ai-agents-complete-guide-2026),
[heyuan110](https://www.heyuan110.com/posts/ai/2026-07-05-loop-engineering/).
Vibe coding: [The New Stack](https://thenewstack.io/vibe-coding-could-cause-catastrophic-explosions-in-2026/),
[Keyhole Software](https://keyholesoftware.com/vibe-coding-trends-2026/),
[GIANTY](https://www.gianty.com/vibe-coding-what-works-and-what-breaks-for-dev/).
Spec-driven development: [Augment Code](https://www.augmentcode.com/guides/what-is-spec-driven-development),
[thebcms](https://www.thebcms.com/blog/spec-driven-development/),
[MarkTechPost](https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/).
