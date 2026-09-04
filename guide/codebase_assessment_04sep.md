# Codebase assessment — 2026-09-04

**As of** the close of **Segment 19C** — all six items shipped, the last two
being the two-tier semantic colour-token migration (Item 6) and the developer
theme customizer (Item 5, v1) — followed by a **development-practice audit and
its follow-through**, which is the first arc in this project's history to change
how the repo is *worked on* rather than what it does.

**Since the prior snapshot** (`codebase_assessment_19aug.md`), five arcs:

- **19C Item 1 — friendly tag labels via roster CSV headers** (PRs #2005 →
  #2013, 2026-08-20). The roster CSV header becomes the sole carrier.
- **19C Items 3–4 then Item 2 — Danger Zone, button refinements, light/dark
  mode** (PRs #2014 → #2031, 2026-08-20 → 08-21). Browser-local theming.
- **19C Item 6 — two-tier semantic colour tokens** (PRs #2047 → #2062,
  2026-08-23). 79 primitives under 103 role-named semantic tokens.
- **19C Item 5 — theme customizer** (PRs #2032 → #2083, 2026-08-22 → 09-04).
  A three-part designer in `tools/`, app-agnostic.
- **Development-practice audit + follow-through** (PRs #2085 → #2095,
  2026-09-04). `docs/practice-audit-2026-09-04.md` and everything downstream.

**Numbers taken at** `814372a7` on `main`; window `88b93c8..814372a7` —
**91 merge commits, 108 non-merge commits, 17 calendar days** (2026-08-19 →
2026-09-04), PRs **#2005–#2095**.

**Amended 2026-09-04, same day.** The churn figure in §2 was re-taken after the
§8 move #1 fix landed (`tools/code_metrics.py` now walks the full history rather
than a sample); §5, §6 and §8 follow it. The pinned SHA is unchanged and still
describes the tree the numbers came from: the only merge on `main` between
`814372a7` and the amendment (#2096, this document itself) touches **zero
Python files**, so the re-taken churn figure is identical at both commits. All
other numbers are as originally taken.

**Counting convention changed this snapshot, deliberately.** `guide/assessment.json`
now pins the area classification. Auto-detection had put `tools/*.html` — two
generated dev-tooling gallery pages — into `templates`, producing a phantom
**+38.1%** there, and `tools/*.py` into `production`. `tools/README.md` is
explicit that these "operate *on* the repo but aren't part of the app or its
test suite". `tooling` is now its own area. **The deltas below remain
comparable**: `tools/` did not exist at `88b93c8`, so the prior figures
contained none of it either.

**This document stands alone.** It archives alongside
`codebase_assessment_19aug.md`. Authority for ship-state is `docs/status.md`;
the functional spec audited against is `spec/rrw_functional_spec.md` plus the
per-surface specs in `spec/`.

**Development context:** one author working through AI coding agents, no local
dev loop, pre-pilot. A cadence of ~5 merges/day is normal here and should not be
read against a team norm.

---

## 1. What's in the box

An operator creates a **review session**, loads a **reviewer** roster, a
**reviewee** roster and optionally an **observer** roster, then defines
**instruments** — the question sets — and an **assignment rule** that decides
who reviews whom. Validation gates the session; activation opens the
participant surface at `/me/`, where reviewers answer per-reviewee instrument
pages and submit. The operator watches coverage, closes the response window,
and **releases responses**, at which point reviewees read their own results at
`/me/sessions/{id}/results` under a per-instrument visibility policy (Raw /
Anonymized / Summarized) and observers read cohort-scoped collations at
`/me/sessions/{id}/collation`. Everything mutating writes an `audit_events`
row; the whole session round-trips out through **extracts** and back in through
**rehydrate**. Server-rendered FastAPI + Jinja on SQLAlchemy 2.x and Postgres,
with no frontend framework and no JS build step.

**New since the prior snapshot**

- **Friendly tag labels via roster CSV headers** (#2005 → #2013, 2026-08-20).
  Reviewer / reviewee / relationship tag friendly labels round-trip through the
  roster CSV header as a `ReviewerTag1.<label>` suffix — now the sole carrier.
  `field_labels.*` retired from the Settings CSV and silently ignored in old
  bundles. New `app/services/field_label_csv.py` (109 LOC), the window's only
  new production module.
- **Light/dark mode** (#2014 → #2031, 2026-08-20 → 08-21). `localStorage["rrw-theme"]`
  plus `data-theme` on `<html>`, a no-FOUC inline script, and a chrome toggle
  pill; the settings-card placement was considered and retired. Browser-local by
  design — no column, no migration. `error.html` themed too.
- **Danger Zone + button refinements** (19C Items 3–4). The Danger-Zone card
  takes the lock card's amber infill; **Delete Data** is now gated behind the
  lifecycle lock like Delete session.
- **Two-tier semantic colour tokens** (#2047 → #2062, 2026-08-23). `base.html`
  migrated off the flat colour-named palette onto **79 descriptive primitives**
  under **103 role-named semantic tokens** (`--btn-primary-bg`, `--surface-card`,
  `--status-warning-*`, …), consumed exclusively by every component and template
  inline style; all flat tokens retired. Independent slots by default, `@coupled`
  for deliberate coupling. Every slice value-preserving. Catalogue:
  `spec/color_tokens.md`.
- **Theme customizer** (#2032 → #2083). `tools/theme_customizer.gen.py` →
  `tools/theme_customizer.html`: **Part A** previews the real component gallery,
  **Part B** edits tokens (OKLCH seeds, per-primitive pickers with live repaint,
  AA contrast badges, per-theme semantic remaps), **Part C** click-to-reflect
  from a rendered element back to its token and co-users. App-agnostic — it
  parses primitives and clusters out of `base.html`. Surfaced real `base.html`
  fixes as a side effect (nav chrome → `--surface-page`; `sky-*` → `--blue-cyan-*`,
  `danger-*` → `--red-warm-*`).
- **Development-practice audit** (#2085 → #2095). `docs/practice-audit-2026-09-04.md`
  plus: `tests/unit/test_doc_conventions.py` (three checks — lifecycle tables must
  match `DISPLAY_LABELS`, retired button names absent from live prose, `CLAUDE.md`
  and `AGENTS.md` byte-identical), `.claude/agents/diff-reviewer.md`, a
  `CONTRIBUTING.md` merge policy, `new_project_practices_setup.md`,
  `tools/code_metrics.py`, and a `CLAUDE.md` trim from 266 to 183 lines.

**Unchanged this window:** the assignment engine, the response/submit path, the
reviewee results and observer collation bodies, extracts, rehydrate, the audit
subsystem, the sys-admin surfaces, and the whole email track. Production Python
moved **+110 LOC net**; this was a presentation-layer and practice window.

---

## 2. Size (LOC)

Physical lines, git-tracked files only, areas per `guide/assessment.json`.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 214 (204 prior) | **103,262** | +10,015 (+10.7%) |
| `tests` | 254 (251 prior) | **87,830** | +467 (+0.5%) |
| `production` | 197 | **55,504** | +110 (+0.2%) |
| `templates` | 59 (58 prior) | **22,242** | +434 (+2.0%) |
| `tooling` | 7 | **9,479** | — (new area, baseline) |
| `migrations` | 77 | **6,772** | unchanged |

**Test-to-production ratio: 1.58** — identical to the prior snapshot's 1.58.
Flat is the expected reading of a window that added 110 lines of production code.

**Tests: 2,700 passed, 17 skipped**, `ruff check .` clean. Both CI tracks green
on `main` at the pinned SHA — the SQLite `CI` job and the `ci-postgres` job that
round-trips the Alembic chain and re-runs the whole suite against `postgres:16`.
The 17 skips are all deliberate legacy markers, not failures; see §6.

**Biggest production files**

| LOC | File | Δ |
| --- | --- | --- |
| 1,247 | `app/web/routes_operator/_instruments.py` | unchanged |
| 1,056 | `app/services/session_lifecycle.py` | unchanged |
| 1,025 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,000 | `app/services/csv_imports.py` | +60 |
| 984 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 981 | `app/web/views/_instruments.py` | unchanged |
| 974 | `app/services/responses/_core.py` | unchanged |
| 967 | `app/services/audit.py` | unchanged |
| 964 | `app/services/instruments/_response_fields.py` | unchanged |
| 954 | `app/services/validation.py` | unchanged |

The shape is a **plateau, not a long tail**: nine of the top ten sit between 954
and 1,056, with one outlier at 1,247. Nothing moved except `csv_imports.py`
(+60, the friendly-label carrier). No file crossed a tripwire, and no split is
queued — see §9. My read: the plateau is the signature of the 18N/18O per-concern
carves holding, not of files being trimmed to a target.

**Where the window's growth landed.** Almost entirely outside production code.
`docs` took +10,015 (the practice audit and its appendix, the theme-customizer
and semantic-token plans, `new_project_practices_setup.md`); `tooling` is 9,479
LOC of new dev-only harness, 83% of it the two generated HTML gallery pages.
Production gained exactly **one** new module — `app/services/field_label_csv.py`
at 109 LOC — and the net was +110. This is the first window in the series where
production was essentially static by intent rather than by pause.

**Package shape:** `routes_operator/` 22 modules, `routes_reviewer/` 7,
`services/` 39 top-level plus `instruments/` 9 and `responses/` 3, `views/` 19,
`db/models/` 21. Unchanged from the prior snapshot except `services/` +1.

**Duplication and churn** — new standard items this snapshot
(`python3 tools/code_metrics.py`, added #2094):

| | `app/` | `tests/` |
| --- | --- | --- |
| duplicated, blocks ≥6 lines | 15.8% | 31.7% |
| **duplicated, blocks ≥10 lines** | **6.5%** | **16.7%** |
| duplicated, blocks ≥15 lines | 3.0% | 9.7% |
| duplicated, blocks ≥25 lines | 1.1% | 4.1% |

Read the ≥10 row; the ≥6 row is import and decorator boilerplate. The ≥10 hits
are real shared scaffolding — `_setup_reviewers.py` and `_setup_reviewees.py`
share 40 ten-line windows and are ~47% duplicated each, the one place a shared
helper would pay. Tests at ~2.5× production is normal for table-driven
integration tests.

**Churn: 1.0×** (deleted lines younger than 14 days, against the ambient age of
the same files at that moment), computed across **all 2,085 first-parent merges**
on `main` — 71,862 deleted Python lines. 74.3% of them were under 14 days old,
but so were 77.0% of *all* lines in those files at the moment of deletion:
deletions here are age-blind, and marginally *older* than ambient. Surviving
`app/` code has a median line age of **109 days**. On this evidence the codebase
does not exhibit the churn pattern the 2026 AI-authored-code literature
describes. **The bare 74% would have suggested the opposite**, which is why the
convention in `guide/README.md` forbids quoting it without the ratio.

---

## 3. Functional-spec compliance

Every row checked against code — a route registered, a service function present,
a test covering it — not against the spec's own claims. **Bold rows changed this
window.**

| Functional area | Spec | Code status |
| --- | --- | --- |
| Session lifecycle (5 live states) | `spec/lifecycle.md` | ✓ shipped — `app/services/session_lifecycle.py` |
| Sessions lobby + Session Home | `spec/sessions_overview.md`, `spec/session_home.md` | ✓ shipped |
| Quick Setup card | `spec/quick_setup_card_spec.md` | ✓ shipped — `_quick_setup.py` |
| Setup pages (5) | `spec/setup_pages.md` | ✓ shipped — `_setup_*.py` slices |
| **Roster CSV + friendly tag labels** | `spec/csv_contracts.md` | **✓ shipped 2026-08-20 (#2005→#2013) — `field_label_csv.py`** |
| Assignment engine | `spec/assignments.md` | ✓ shipped — `app/services/assignments/` (5 modules) |
| Instruments (Bands 1/2/3) | `spec/instruments.md` | ✓ shipped — `instruments/` (9 modules), 54 route refs |
| Validate page | — (in functional spec) | ✓ shipped — 19 route refs, `validation.py` |
| Reviewer surface `/me/` | `spec/participant_model.md` | ✓ shipped — `routes_reviewer/` (7 modules) |
| Reviewee results (3 modes) | `spec/visibility_policy.md` | ✓ shipped |
| Observer collation + cohorts | `spec/participant_model.md` | ✓ shipped — 29 route refs |
| Extracts + Extract data tab | `spec/roundtrip_coverage.md` | ✓ shipped |
| Rehydrate | `spec/rehydrate.md` | ✓ shipped — `session_rehydrate.py`, 6 route refs |
| Audit events + envelope schema | `spec/architecture.md` | ✓ shipped — `audit.py`, `EVENT_SCHEMAS` strict gate |
| Sys-admin + three-tier roles | `docs/security_posture.md` | ✓ shipped — 17 route refs |
| **Light/dark mode** | `spec/visual_style_rrw.md` | **✓ shipped 2026-08-21 (#2014→#2031) — 12 `data-theme` refs in `base.html`** |
| **Two-tier semantic colour tokens** | `spec/color_tokens.md` | **✓ shipped 2026-08-23 (#2047→#2062)** |
| **Theme customizer (developer)** | `guide/theme_customizer.md` | **✓ v1 shipped 2026-09-04 (#2032→#2083) — `tools/`** |
| Operator theming (in-app tweaker) | `guide/theme_customizer.md` Stretch | ⏸ planned — `guide/deferred_consolidated.md` Part A |
| Email dispatch / invitations | `guide/segment_14B_email_infrastructure.md` | ⛔ blocked — `email_send.py` has the SMTP backend and outbox rows; no live dispatch caller. Unchanged this window |
| Blob storage | `spec/blob_storage.md`, `guide/segment_18Q_blob.md` | ⏸ planned — awaiting institutional storage account |
| Permissions model | *no spec* | ⚠ drift — code is ahead; `spec/permissions.md` still unwritten |
| Email template editor | *no spec* | ⚠ drift — code is ahead; `spec/email_template_editor.md` still unwritten |

**Doc-drift work this window.** The practice audit found and fixed a live drift
the Segment 19A sweeps had missed: `expired → "Closed"` landed 2026-06-01, and
three specs still documented the label as "Expired" three months later. That
class is now mechanically enforced (`test_doc_conventions.py`). **Still open:**
the two missing specs above — the same pair the prior snapshot named as its
move #3, which did not ship.

---

## 4. Strengths

- **A 91-PR window moved production by 110 net lines without a regression.**
  Two visual-system migrations (dark mode, then a full palette re-architecture
  touching every component) landed value-preserving, with the suite green at
  every slice. That is the 11-slice discipline in `guide/archive/semantic_tokens.md`
  doing its job.
- **The per-concern carves are holding.** Nine of the top ten production files
  sit in a 100-line band (954–1,056), and the one outlier has *receded* across
  two consecutive windows (1,317 → 1,247). File size stopped being the live risk
  it was at 18N.
- **Conventions moved from prose to checks.** Three now fail the suite rather
  than waiting to be noticed: the `EVENT_SCHEMAS` audit gate (pre-existing), and
  this window's lifecycle-label and retired-terminology checks plus the
  twin-file identity check. `CLAUDE.md` shrank 266 → 183 lines in the same arc,
  which is the rarer half — most instruction files only grow.
- **The codebase does not show the AI-authored-code failure pattern.** Measured,
  not asserted: duplication 6.5% at ≥10-line blocks, churn ratio 1.0×, median
  surviving line age 109 days. §2 has the method; the numbers are reproducible
  from `tools/code_metrics.py`.
- **Dual-dialect CI is load-bearing and green.** Every PR round-trips the whole
  Alembic chain in both directions against `postgres:16` and re-runs 2,700 tests
  there. For a project whose default test dialect is SQLite, this is the check
  that makes migrations safe, and it has never been quietly disabled.

---

## 5. Weaknesses

- **Email is the long pole and has not moved in three snapshots.** `email_send.py`
  ships an SMTP backend and the outbox writes rows, but nothing dispatches.
  Invitations, reminders and result notifications all depend on it, and a pilot
  that cannot email participants is a pilot that runs on broadcast links. It was
  the prior snapshot's recommended move #1 and the one before that's as well.
  **Plan exists (`guide/segment_14B_email_infrastructure.md`); no code this window.**
- **Two functional areas have no spec at all.** `spec/permissions.md` and
  `spec/email_template_editor.md` were named as move #3 last snapshot and remain
  unwritten. Code is ahead of documentation in both, which is the exact drift
  direction the new `test_doc_conventions.py` gate *cannot* catch — it verifies
  agreement, not coverage.
- **Roughly half of recent defects are invisible to every automated layer.** The
  practice audit classified 30 fix commits: ~50% were browser-only (a 4px
  misalignment, a keypress toggling a card, a caption that was selectable),
  catchable by neither the test suite nor a diff reader. The project has filed
  the gap itself (`5eebec53`, template-JS runtime testing) and deferred it. The
  verifier for that class is a human on the Azure dev slot, and it is the one
  part of the loop with no machine-checkable definition of done.
- **`tooling/` is now 9,479 LOC with no test coverage and no lint gate on its
  generated output.** The two HTML files are generated artefacts (83% of the
  area) and regenerating them is a manual step after any `base.html` change; a
  stale customizer silently designs against the wrong palette. Filed as a
  known cost, no plan.
- **The duplication finding is real and unaddressed.** `_setup_reviewers.py` and
  `_setup_reviewees.py` are ~47% duplicated against each other. The shared helper
  is obvious and nobody has written it. Below the action threshold in
  `guide/README.md`, so this is a note, not a task.

---

## 6. Bugs and regressions

**No known open bugs at `814372a7`.** What I checked to say that: both CI tracks
green on the pinned SHA; all 17 skips read and classified; the window's merge log
scanned for `fix:` commits and their follow-ups; the practice audit's own defect
census (30 fix commits) reviewed. There is no issue tracker in the repo to check.

**The 17 skipped tests are all deliberate legacy markers**, not silenced
failures — 8 from the Wave 5 PR 5.3 model change (every instrument now defaults
to Full Matrix, so legacy unpinned-instrument gates retired), one from an 18J
RTD-shim extract path awaiting a follow-up, and the rest fixture-shape guards.
Each carries a written reason at the skip site.

**Caught and fixed this window, worth remembering:**

- **`expired → "Closed"` documented wrongly in three specs for three months**
  (#2086). Survived a deliberate whole-folder documentation sweep. Now
  mechanically enforced.
- **`.gitignore` silently swallowed new agent config** (#2087). `.claude/` was
  ignored wholesale while one file inside it was tracked as an exception, so a
  newly added agent file produced no `git status` output at all and would never
  have committed. Narrowed to `.claude/*` + `!.claude/agents/`.
- **The theme-preview harness lifted the wrong `<style>` block** (#2031),
  blanking light mode — a generated-artefact failure of exactly the kind §5
  flags as an ongoing `tooling/` cost.

**One defect introduced this window, found and fixed same-day.**
`tools/code_metrics.py` (#2094) shipped with a **sample-dependent** churn ratio
and a default sample of 40. Sweeping the sample size did not find a floor above
which it settles — the ratio read 1.4× / 1.4× / 0.9× / 1.0× / 0.8× / 1.0× /
1.1× / 1.1× / 1.1× at 60 / 120 / 100 / 200 / 300 / 500 / 700 / 1000 / 400 —
so the first attempted fix, raising the default to a "stable floor" of 300, was
itself wrong. **Sampling was the defect, not the sample size:** deletions per
merge are heavy-tailed, so the figure is decided by whichever few large merges
the sample lands on. The action threshold written into `guide/README.md` in
#2095 is ~1.5×, which sat inside that noise band and would have fired spuriously
on the very run meant to establish the trend.

The tool now walks every merge by default — deterministic 1.0×, ~76s, which is
the right cost for a number quoted once per snapshot. `--churn-sample N` remains
for iterating on the tool and warns that its output must not be compared against
a threshold or another snapshot. §2's figure is the deterministic one.

---

## 7. Estimated size upon completion

Current: **55,504** production, **22,242** templates, **87,830** tests,
**9,479** tooling.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | SMTP credentials / institutional relay |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | 19C closed (it is) |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| The two missing specs | 0 | 0 | — |

**Projected feature-complete v1: ~57.2–58.4k production, ~22.9–23.6k templates.**

**Reconcile against 19aug.** That snapshot projected **~56.5–57.5k production +
~22–22.5k templates**. This one projects slightly higher on both. The reason is
not scope discovery — it is that 19aug's projection was made when `tools/` did
not exist and its production figure would, under auto-detection, have absorbed
tooling code. Measured on the now-pinned classification, the remaining named work
is unchanged and the range shifts up ~0.7k production / ~0.9k templates because
**Operator theming (Stretch) moved from unscheduled to a named, unblocked item**
when its editor-core dependency shipped this window. Excludes anything past v1.

---

## 8. Bottom line

Segment 19C closed completely, taking the app's entire visual system with it —
dark mode, a two-tier token architecture, and a designer tool to drive both —
while production Python moved 110 net lines. The window then did something this
project had not done before: audited its own working practice with evidence,
found the merge discipline sound and the documentation discipline not, and
mechanised the difference. The one live thread is **email**, unmoved for three
snapshots and the only thing standing between this codebase and a pilot that can
actually reach its participants.

**Recommended next moves**

1. **Start Segment 14B email dispatch.** Third snapshot as the top
   recommendation. Everything else on the v1 list is polish or blocked on an
   institutional dependency; this is blocked on nothing but a decision. The
   outbox, the SMTP backend and the templates already exist — what is missing is
   the caller.
2. **Write `spec/permissions.md` and `spec/email_template_editor.md`.** Cheap,
   and #1 makes the second one load-bearing rather than tidy. The new
   documentation gate verifies agreement but cannot detect *absence*, so these
   two stay invisible to automation until written.

**Only two this time, deliberately.** The third slot went to the churn-metric
fix, which shipped the same day (§6). Nothing else in the body clears the
bar: the duplication figure is under the threshold `guide/README.md` sets, and
acting on an under-threshold metric is the make-work that convention exists to
prevent.

**Settling 19aug's proposals.** Move #1 (start 14B email) **did not ship** —
carried forward as #1 again, now for the third consecutive snapshot. Move #2
(archive Segment 18S) **shipped** — `guide/archive/segment_18S_security.md`.
Move #3 (close the Segment 19 spec coverage gap) **did not ship** — carried
forward as #2. Its §9 watchlist held: `_instruments.py` unchanged at 1,247,
`session_lifecycle.py` unchanged at 1,056, no split queued.

---

## 9. Proposed file splits — watchlist

**No split is queued, and the pressure was flat this window** — no production
file changed size except `csv_imports.py` (+60).

- **`app/web/routes_operator/_instruments.py` (1,247 LOC, unchanged).** Held for
  a second consecutive window after receding from the 17aug high of 1,317. The
  seam if it grows again is unchanged: carve the `/save` payload-parsing blocks
  into a `_save.py` sibling, leaving the thin route in place — mirrors the
  18N/18O per-concern carves. Revisit only past ~1,400.
- **`app/services/session_lifecycle.py` (1,056 LOC, unchanged).** Flat after
  +10 last window. No natural seam identified; the state machine is cohesive and
  splitting it would scatter the transition table. Watch, do not plan.
- **`app/services/instruments/_instrument_crud.py` (1,025 LOC, unchanged).**
  New to the watchlist by virtue of the plateau, not by growth. Lifecycle +
  group/unit-of-review + column-widths are three concerns in one module; if it
  passes ~1,200 the column-widths helpers are the cleanest carve.

**Watchlist tripwire: ~1,400 for `_instruments.py`, ~1,200 for the other two.**
