# Codebase assessment — 2026-09-05

**As of** the close of the **development-practice arc** — the audit of
2026-09-04 and everything it set in motion, ending with Segment 19A closed and
archived and its drift sweep's findings actioned. No functional surface changed
in this window. What changed is the machinery that keeps the documentation true.

**Since the prior snapshot (2026-09-04, `codebase_assessment_04sep.md`):** one
arc, in four movements — the two missing Tier-1 specs (**#2101**, closing
Segment 19A Part 1 four months after a sweep flagged them); the practice written
down as `rrw_sdd_in_practice.md` and distilled to `constitution.md`
(**#2099–#2105**); **Segment 19A Item 3** (**#2109 → #2111**), which made the
phase rule's exit checkable on both halves; and **Item 2** (**#2112 → #2115**)
plus its follow-through as **19C Item 7** (**#2116 → #2118**), which gave the
whole-folder sweep a cadence and then ran one.

**Taken at** `eff2661f` on `claude/read-only-repo-s3r5u5` — the branch head, one
docs-currency commit ahead of `main` at `47be6bda`. Window `814372a7..eff2661f`:
**23 merges, 31 non-merge commits, 2026-09-04 → 2026-09-05**, PRs **#2096–#2118**
(#2096 is the prior snapshot itself).

**This document stands alone.** It archives alongside
`guide/codebase_assessment_04sep.md`, which it supersedes. Authority for ship
state is `docs/status.md`; the functional contract audited against is
`spec/rrw_functional_spec.md` and the per-surface specs under `spec/`.

**Context that shapes the numbers:** a single author directing AI agents,
pre-deployment, no pilot yet. Twenty-three merges in a calendar day is normal
here and should not be read against a team cadence. This window is also unusually
narrow: one arc, no product work.

---

## 1. What's in the box

Review Robin Web runs 360-style review cycles end to end. An **operator** creates
a **session**, imports **reviewer**, **reviewee** and **relationship** rosters
from CSV, designs one or more **instruments** (the questionnaire, its response
fields and its display fields), and lets the **assignment engine** fan those
instruments across the roster into **assignments**. Activating the session locks
setup and opens the **reviewer surface** at `/me/`, where each reviewer answers
their assigned instruments page by page. Responses flow back through
**visibility policies** that decide who may see what, in what form, and when:
reviewees read their **results**, observers read a cross-cohort **collation**,
and the operator monitors completion, sends reminders, and pulls **extracts** as
CSV — which the **rehydrate** path can read back to rebuild a session. Every
mutation writes an **audit event** against a per-type schema allowlist. It is a
server-rendered FastAPI + Jinja monolith on SQLAlchemy 2.x and Postgres.

**New since the prior snapshot** — all of it infrastructure for documentation
correctness, none of it product:

- **The two Tier-1 specs (#2101, 2026-09-05).** `spec/permissions.md` (278
  lines) — the authorization contract: the gate catalogue in `app/web/deps.py`,
  a per-route matrix (128 of 128 session-scoped routes verified gated), the
  ownership invariants and their status codes. `spec/email_template_editor.md`
  (324 lines) — the `/sessions/{id}/setup-invite` page contract,
  `email_template_overrides` resolver, merge tags, and two ship-state facts
  stated plainly: the send path writes outbox rows and transmits nothing, and
  the responses-received toggle has no consumer. Writing them surfaced and fixed
  five drifts in neighbouring specs.
- **`app/web/spec_registry.py` (192 LOC, #2109)** — the window's only new
  production module, and it ships no behaviour. `SPEC_COVERAGE` maps 27 routing
  modules to the 22 live specs that govern them; `INFRASTRUCTURE_MODULES` holds
  the 3 with no user-facing contract; `SPEC_PENDING` / `EXPECTED_PENDING` (empty)
  is the sanctioned way to declare a surface shipping ahead of its spec.
  `routing_modules()` walks the FastAPI route table recursively — the plan's
  one-liner returned 2 modules of 30 on FastAPI 0.141, which would have made the
  test pass vacuously. `tests/unit/test_spec_coverage.py` (94 LOC) derives three
  checks from it.
- **`tools/close_check.py` (770 LOC, #2110)** — reads a plan's `Doc impact`
  manifest at the level being closed and verifies each committed path exists, is
  live, and was edited inside the segment's window; plus reasoned waivers and a
  warn-only `Status` check. `--archived` reports across the archive in ~3 s;
  `--stale` lists live docs by age and answers whether a sweep is due.
- **The sweep cadence (#2112 → #2115)** — `guide/sweep_template.md` (179 lines)
  and the first sweep under it, `guide/sweep_2026-09-05_spec-docs.md` (209
  lines), whose eight findings were then closed as 19C Item 7.
- **The practice documents** — `rrw_sdd_in_practice.md`, `constitution.md`
  (six articles), `docs/practice-audit-2026-09-04.md` Appendix A, and the
  `segment-plan` skill with `guide/segment_plan_template.md`.

**Unchanged this window:** every product *surface*. No route added or removed,
no template touched, no migration, no schema change, no service logic. Six files
under `app/` did change, and the distinction is worth being exact about: five are
comment- or docstring-only (three stale code comments corrected in #2103, plus
the `_preview_surface.py` segment misattribution), and one is a single
operator-visible string — the `$deadline` merge-tag description in
`app/services/email_templates.py`, corrected from "Session deadline
(YYYY-MM-DD)" to "Session deadline as YYYY-MM-DD HH:MM (UTC)" because that is
what the editor actually renders. Total: 212 insertions, 12 deletions.

## 2. Size (LOC)

Physical lines, git-tracked files only, area classification pinned in
`guide/assessment.json`.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 225 (214 prior) | **109,990** | +6,728 (+6.5%) |
| `tests` | 255 (254 prior) | **87,924** | +94 (+0.1%) |
| `production` | 198 (197 prior) | **55,704** | +200 (+0.4%) |
| `templates` | 59 | **22,242** | unchanged |
| `tooling` | 8 (7 prior) | **10,278** | +799 (+8.4%) |
| `migrations` | 77 | **6,772** | unchanged |

**Test-to-production ratio: 1.58**, flat (1.582 prior). The +94 test lines are
`test_spec_coverage.py`; no product test moved, because no product code moved.

**Tests:** 2,703 passed, 17 skipped, `ruff check .` clean. Both CI tracks green
on every PR in the window (`test` on SQLite, `postgres` round-tripping the
Alembic chain against `postgres:16`).

**Biggest production files — all ten unchanged:**

| LOC | File | Δ |
| --- | --- | --- |
| 1,247 | `app/web/routes_operator/_instruments.py` | unchanged |
| 1,056 | `app/services/session_lifecycle.py` | unchanged |
| 1,025 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,000 | `app/services/csv_imports.py` | unchanged |
| 984 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 981 | `app/web/views/_instruments.py` | unchanged |
| 974 | `app/services/responses/_core.py` | unchanged |
| 967 | `app/services/audit.py` | unchanged |
| 964 | `app/services/instruments/_response_fields.py` | unchanged |
| 954 | `app/services/validation.py` | unchanged |

The shape is a plateau, not a long tail: ten files between 954 and 1,247, then a
drop. Nothing moved, so the split pressure is exactly where §9 left it.

**Where the window's growth landed.** Almost entirely in `docs` (+6,728) and
`tooling` (+799), and both are new files rather than accumulation: 14 new
documents, one new tool. Production's +200 is `spec_registry.py` (192) plus eight net lines
across five files, all comment or docstring except the one merge-tag
description string noted in §1. **This is the first window in the series where the
production delta is smaller than the tooling delta** — the work was about the
repository, not the product.

**Package shape.** `app/` unchanged at 198 files: `services/` 11 sub-packages,
`web/routes_operator/` 20 route modules + `_shared.py`,
`web/routes_reviewer/` 6 + `_surface/`, `web/views/` 9. `tools/` grew from 7
files to 8.

## 3. Functional-spec compliance

Rows are checked against code. **Two rows changed this window, and the method of
checking changed with them.**

Every routing module is now mechanically proven to have a governing spec:
`tests/unit/test_spec_coverage.py` asserts set equality between the live route
table (30 first-party modules) and `SPEC_COVERAGE` ∪ `INFRASTRUCTURE_MODULES`,
and that all 22 mapped paths are live non-archived files. That is a stronger
guarantee than a hand-audited table for the *existence* question, and no
guarantee at all for the *adequacy* one — see the note below.

| Functional area | Spec | Code status |
| --- | --- | --- |
| Session lifecycle (5 live states) | `spec/lifecycle.md` | ✓ shipped — `app/services/session_lifecycle.py` |
| Sessions lobby + Session Home | `spec/sessions_overview.md`, `spec/session_home.md` | ✓ shipped |
| Quick Setup card | `spec/quick_setup_card_spec.md` | ✓ shipped — `_quick_setup.py` |
| Setup pages (5) | `spec/setup_pages.md` | ✓ shipped — `_setup_*.py` slices |
| Roster CSV + friendly tag labels | `spec/csv_contracts.md` | ✓ shipped 2026-08-20 |
| Assignment engine | `spec/assignments.md` | ✓ shipped — `app/services/assignments/` |
| Instruments (Bands 1/2/3) | `spec/instruments.md` | ✓ shipped — `instruments/` (9 modules) |
| Validate page | `spec/validate_page.md` | ✓ shipped — `validation.py` |
| Reviewer surface `/me/` | `spec/reviewer-surface.md` | ✓ shipped — `routes_reviewer/` |
| Reviewee results (3 modes) | `spec/visibility_policy.md`, `spec/participant_model.md` | ✓ shipped |
| Observer collation + cohorts | `spec/participant_model.md` | ✓ shipped |
| Extracts + Extract data tab | `spec/csv_contracts.md`, `spec/extract_data.md` | ✓ shipped |
| Rehydrate | `spec/rehydrate.md` | ✓ shipped — `session_rehydrate.py` |
| Audit events + envelope schema | `spec/architecture.md` | ✓ shipped — `EVENT_SCHEMAS` strict gate |
| Sys-admin + three-tier roles | `spec/permissions.md`, `docs/security_posture.md` | ✓ shipped |
| Light/dark mode | `spec/visual_style_rrw.md` | ✓ shipped 2026-08-21 |
| Two-tier semantic colour tokens | `spec/color_tokens.md` | ✓ shipped 2026-08-23 |
| Theme customizer (developer) | `guide/theme_customizer.md` | ✓ v1 shipped 2026-09-04 |
| **Permissions model** | **`spec/permissions.md`** | **✓ shipped 2026-09-05 (#2101) — was ⚠ drift; the spec is now written and the per-route matrix verified** |
| **Email template editor** | **`spec/email_template_editor.md`** | **✓ shipped 2026-09-05 (#2101) — was ⚠ drift; spec written, including the two "shipped but inert" facts** |
| **Spec + doc drift gates** | `constitution.md` Art. II, `rrw_sdd_in_practice.md` §6.1 | **✓ shipped 2026-09-05 (#2109 → #2115) — coverage gate, close check, sweep cadence** |
| Operator theming (in-app tweaker) | `guide/theme_customizer.md` Stretch | ⏸ planned — `guide/deferred_consolidated.md` Part A |
| Email dispatch / invitations | `guide/segment_14B_email_infrastructure.md` | ⛔ blocked — `email_send.py` has the SMTP backend and writes outbox rows; no live dispatch caller. Gated on institutional Azure provisioning (decision 2026-09-05) |
| Blob storage | `spec/blob_storage.md`, `guide/segment_18Q_blob.md` | ⏸ planned — awaiting institutional storage account |

**The prior snapshot's two ⚠ drift rows are both closed.** They were the same
pair the 19aug snapshot named and the 04sep one carried unchanged; they had been
open since 2026-05-11.

**Doc-drift work this window.** The first cadenced sweep ran
(`guide/sweep_2026-09-05_spec-docs.md`), reading 13 of 64 in-scope live docs and
filing eight findings, all now closed — seven actioned, one declined with a
reasoned waiver. The archive-wide honour rate measured by `close_check.py
--archived` is **87 of 103 live committed paths (84%), 22 of 33 plans fully
honoured, 8 committed paths no longer existing**.

**What the new gates do not cover, stated because the table now looks stronger
than it is.** The coverage test detects a routing module with *no* spec. It
cannot detect a spec that exists and says too little — neither Tier-1 gap above
would have tripped it, because both surfaces had sections in
`spec/operator_ui_concept.md` and lacked only a dedicated contract. Adequacy
remains a human judgement made at a sweep.

## 4. Strengths

- **A four-month documentation gap closed, and the mechanism that let it happen
  was closed with it.** `spec/permissions.md` and `spec/email_template_editor.md`
  were flagged 2026-05-11 and written 2026-09-05. The same arc shipped the
  reason it will not recur silently: a routing module with no spec now fails the
  suite, and a plan that drops a committed spec edit now fails `close_check.py`.
- **The gates are derived, not hand-maintained.** `test_spec_coverage.py` reads
  the live FastAPI route table; `test_doc_conventions.py` reads `DISPLAY_LABELS`.
  Neither has an allowlist that must be groomed, which is the property that made
  the practice audit reject a spelling check.
- **Verification caught three errors that would otherwise have shipped as
  green.** The plan's route-enumeration expression returned 2 modules of 30 on
  this FastAPI version (a test written to it would have passed against an almost
  empty set); the recorded 85% honour baseline counted merge artifacts; and the
  close check reported a false pass the moment a plan file carried a second item.
  Each was found by exercising the check against the failure it claims to catch,
  not by reading it.
- **The plateau held for a third consecutive window.** No production file grew,
  and the largest is 1,247 LOC — below the 1,300 ceiling the 18O splits
  established, with no split queued.

## 5. Weaknesses

- **The largest structural risk is unchanged and unaddressed: email dispatch has
  never run.** `email_send.py` has an SMTP backend and writes `email_outbox` rows
  that nothing transmits. Reminders — the one participant-facing gap an
  operator's own broadcast cannot cover — depend on it. It is blocked on
  institutional Azure provisioning, a decision recorded 2026-09-05, and the cost
  is that a whole subsystem reaches its first real execution after deployment
  rather than before.
- **`close_check.py` has a known blind spot that is not fixed.** On a
  segment-level manifest, C3 asks whether a committed path was touched inside the
  *segment's* window — so on a long-lived segment an older item's edit satisfies a
  newer item's bullet. Observed live: 19C read green while one of its Item 7
  commitments was outstanding. The item-level analogue was fixed; this one needs
  design thought (dating a bullet from the heading of the item its `(Item n)` tag
  names is the obvious candidate, not an established answer). Recorded in 19C's
  `## Status`; **no plan.**
- **Two of the first sweep's own eight findings were wrong.** Both came from the
  mechanical dead-reference pass, and both failed identically: the scan sees that
  a path is absent, not why a document names it. One was a dated provenance note;
  one named specs that had never existed. They were caught at build, before any
  document was mis-edited — but they were filed, and the sweep's own rule says a
  finding is verified before filing. The ledger now records the lesson; whether
  the next sweep applies it is untested.
- **The sweep's cadence numbers are unmeasured.** 8 weeks / 500 merges was
  derived from one observed gap (93 days, 1,120 merges). The first sweep was run
  early, on 18 days and 151 merges, to validate the template — so neither trigger
  has fired in anger. **Planned to revisit** after two or three real cycles.
- **A skipped test has gone 104 days unread, and it may be hiding a data-loss
  path.** `test_reviewer_summary.py:146` (§6) was skipped in May pending work
  that has since shipped; nobody re-ran it. The cost is that the extract's
  handling of shim-resolved RTD responses is unverified either way. **No plan** —
  it is filed in §6 and §8 as the next thing to check.
- **51 of 64 in-scope live documents have not been read by any sweep.** They were
  covered only by the four mechanical passes, which see broken references and
  absent specs but not a paragraph that quietly stopped being true. The sweep
  says so in its §7 rather than implying coverage; it remains a gap.

## 6. Bugs and regressions

**No known product bugs at `eff2661f`, with one qualification below.** What was
checked to say that: the full suite (2,703 passed, 17 skipped) on both dialects;
`ruff check .`; every skip read individually; and the window's `app/` diff, which
is comment-only apart from one string (§1) and so introduced no new surface to
regress.

**The qualification, and it is a real one.** The 17 skips are not
environment-gated, and none is an `xfail`. Fifteen are `@pytest.mark.skip`
markers recording behaviour retired by Wave 5 PR 5.3 and the 18J legacy-card
work, where the assertion no longer describes a shipped surface; one
(`test_sys_admin_outbox_child.py:113`) notes that a fixture combination does not
generate invitations and that outbox content is covered elsewhere. Those sixteen
are fine. **The seventeenth is not:** `tests/integration/test_reviewer_summary.py:146`, skipped 2026-05-24 in
18J Wave 2 PR iii-b2, reads *"response saved via the shim-resolved RTD path no
longer flows into the extract; the extract needs an iii-b3/b4 update"*. PR iii-b4
subsequently shipped. So either the gap was fixed and the skip is 104 days stale,
or the extract still drops those responses and a data-loss path has been silently
skipped since May. **Nobody has re-checked, and this assessment did not resolve
it** — doing so means unskipping and running it, which is work, not measurement.
It is filed here as the highest-value single thing to check next, and it is
exactly the class of unread claim this window's tooling was built to prevent.

Caught and fixed **in the practice tooling** during the window, all before merge:

- The FastAPI 0.141 route-table walk (see §4) — `routing_modules()` now raises
  below a 100-route floor so a future framework change fails by name.
- The item-window false pass in `close_check.py` — an item's window now opens at
  the later of its `### Doc impact` and its own `## Item <n>` heading, ordered by
  ancestry rather than date.
- A `git diff --stat <date>..HEAD` in the sweep template that cannot work (a bare
  date is not a revision), caught by running every entry-point command before
  writing it down.
- The `_preview_surface.py` docstring attributing itself to Segment 18Q — the
  file was created 2026-05-28 in PR #1530, and 18Q is the unrelated blob-storage
  deferral. The 2026-08-18 sweep had filed this against the *spec*, which was
  right all along.

## 7. Estimated size upon completion

Current: **55,704** production, **22,242** templates, **87,924** tests,
**10,278** tooling.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | nothing (unblocked) |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |

**Projected feature-complete v1: ~57.4–58.6k production, ~22.9–23.6k templates.**

**Reconcile against 04sep.** That snapshot projected **~57.2–58.4k production,
~22.9–23.6k templates**. This one is **+0.2k production, templates unchanged** —
and the entire movement is the current total having grown by 200 LOC
(`spec_registry.py`). **No scope was discovered, shipped, or cut**: the four
remaining work items and their ranges are identical, because the window did no
product work. Templates unchanged because nothing touched them. Excludes anything
past v1.

## 8. Bottom line

The product stood still for a day while the repository learned to check its own
documentation. Two specs that had been missing since May are written, the phase
rule that governs when specs get written is now enforced on both halves — a
derived test for surfaces with no spec, a script for plans that drop a
commitment — and the whole-folder sweep has a trigger, a fixed shape, and a
ledger that carries findings forward. Production grew 200 lines, all of it a
registry that ships no behaviour. The one live thread is unchanged and unmoved:
**email dispatch has never executed**, and it stays blocked on institutional
provisioning.

**Recommended next moves, in order:**

1. **Unskip `test_reviewer_summary.py:146` and find out which it is.** It is the
   only item here that might be a live defect rather than a plan — the extract
   either drops shim-resolved RTD responses or it does not, and nobody has known
   which since May. Cheap to answer (unskip, run, read), and the answer either
   deletes a stale marker or opens a bug. It goes first because a possible
   data-loss path outranks any amount of feature work.
2. **Segment 20 (operator polish + documentation).** It is the only unblocked
   feature work left, and it is the natural consumer of everything this window
   built — it will be the first segment planned, built and closed entirely under
   the new template, close check and sweep cadence, which is also the cheapest
   way to find out whether they hold under real feature work rather than
   documentation work.
3. **Fix the `close_check.py` segment-level blind spot** (§5) before Segment 20
   closes, not after. A check that reads green while a commitment is outstanding
   is worse than no check, and Segment 20 will be a multi-item segment — exactly
   the shape that triggers it.

Held below the cut deliberately: **run the second sweep on its real trigger**,
not early. The cadence numbers are the one part of this window's work with no
evidence behind them, and the only way to get that evidence is to let a trigger
fire on its own — which means waiting, not doing.

**Settling 04sep's proposals.** Its move #1 (write the two missing specs) —
**shipped** (#2101). Move #2 (make the drift class mechanically enforced beyond
lifecycle labels) — **shipped**, further than proposed: coverage gate, close
check, and sweep cadence rather than a single test. Move #3 (a codebase
assessment cadence) — **carried**, unactioned; the assessment is still run on
request rather than on a trigger, and the sweep cadence built this window is the
obvious model for it.

## 9. Proposed file splits — watchlist

**No split is queued, and no production file changed size this window.** The
watchlist is carried verbatim because the evidence for it is unchanged.

- **`app/web/routes_operator/_instruments.py` (1,247 LOC, unchanged).** Third
  consecutive flat window, after receding from the 17aug high of 1,317. The seam
  if it grows: carve the `/save` payload-parsing blocks into a `_save.py`
  sibling, leaving the thin route in place — mirrors the 18N/18O per-concern
  carves. Revisit only past ~1,400.
- **`app/services/session_lifecycle.py` (1,056 LOC, unchanged).** No natural
  seam; the state machine is cohesive and splitting it would scatter the
  transition table. Watch, do not plan.
- **`app/services/instruments/_instrument_crud.py` (1,025 LOC, unchanged).**
  Three concerns in one module (lifecycle, group/unit-of-review, column-widths);
  past ~1,200 the column-widths helpers are the cleanest carve.

**Watchlist tripwire: ~1,400 for `_instruments.py`, ~1,200 for the other two.**

One addition to watch, not to split: **`tools/close_check.py` at 770 LOC**
carries two distinct jobs — the per-segment close check and the `--stale`
sweep-cadence report — sharing `REPO`, `_git` and `last_touched_ever` and nothing
else. It is the second-largest hand-written `.py` in `tools/` (behind
`theme_customizer.gen.py` at 847; the two largest files in the folder,
`theme_customizer.html` at 4,175 and `theme_preview.html` at 3,701, are
generated output and not split candidates). If it passes ~1,000, the `--stale`
half is the clean carve.
