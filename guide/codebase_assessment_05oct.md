# Codebase assessment — 2026-10-05

**As of** the end of a five-day stabilization arc that opened with the
30 September assessment: browser tests, two corpus sweeps worked to an empty
register, and a folder-by-folder retirement pass that ended with
`docs/status.md` archived (#2826). No segment plan is open in `guide/`; the
two queued segments, 14B and 20, still wait on the institutional Azure
deployment, which `docs/nus_azure_status.md` shows held on the same two
external decisions as on 1 October.

**Since the prior snapshot** (`guide/archive/codebase_assessment_30sep.md`,
`36e4e6a8`), four arcs shipped:

- **Browser tests and the post-assessment register** (PRs #2703 → #2717,
  2026-10-01). The builder's hand checks became committed Chromium tests, and
  the register the assessment opened was worked through the same day.
- **The 2026-10-01 corpus sweep and its register** (PRs #2718 → #2763,
  2026-10-01 → 2026-10-02). 242 findings; the behavior half shipped as some
  thirty small fixes and retirements, the documentation half as one PR per
  area.
- **The 2026-10-03 corpus sweep and its register** (PRs #2764 → #2810,
  2026-10-03 → 2026-10-04). About 236 findings, a different kind: fewer
  drifts, more provenance, and thirteen code defects, one of which lost data.
- **The retirement pass** (PRs #2811 → #2826, 2026-10-04 → 2026-10-05). Each
  folder read for files to retire, combine or reorganize: four specs folded,
  three tool generators, eight dead tests, nine uncalled functions, and the
  two history logs.

**Numbers taken at `2d7e5b5f`**, `main` at #2826, before this snapshot's own
documents. Window `36e4e6a8..2d7e5b5f`: **124 merge commits, 293 non-merge
commits, PRs #2703–#2826** (124 numbered) across 2026-10-01 → 2026-10-05,
five calendar days.

**This document stands alone** and archives
`guide/archive/codebase_assessment_30sep.md` alongside it. Authority lives
elsewhere: `spec/` (indexed by `spec/README.md`) is the contract, with
`spec/rrw_functional_spec.md` and its siblings what §3 audits against;
`guide/todo_master.md` holds the open work. The status file this series used
to cite as ship-state was archived on 2026-10-05, so this is the first
snapshot that names none. **A corpus sweep ran beside it at the same
commit**, `guide/sweep_2026-10-05_corpus.md`, with its register
`guide/findings_2026-10-05_corpus.md`; §3, §5 and §6 lean on it.

**Development context:** single author, AI agents building, the author
checking each change in a browser against a local run with fake auth,
pre-deployment with an institutional pilot pending. 124 merges in five days
were almost all corrections, retirements and documentation, not features,
built while the deployment waits on NUS IT.

---

## 1. What's in the box

Review Robin Web runs structured peer review end to end. An **operator**
creates a **session**, imports **reviewers**, **reviewees**, **relationships**
and **observers** from CSV, defines **instruments** (what gets asked) with
**rule sets** (who reviews whom), and **generates assignments**. A
**Validate** page runs its registered rules over the setup; **Prepare**
materializes invitations; the session **activates**, reviewers answer on
their own surface, and the operator watches **Invitations** and
**Responses** roll up. Afterwards **reviewees** see their results and
**observers** a collation, each under a visibility policy resolved per
audience and phase. Configuration round-trips through CSV and every mutation
writes an audit event, in a server-rendered FastAPI + Jinja monolith on
Postgres with no JS build step.

**New since the 30 September snapshot:**

- **Browser tests** (PRs #2706 → #2711, 2026-10-01). `tests/browser/`, Python
  Playwright against a live `uvicorn`: 45 tests in 11 files over the builder's
  rows, card, branching and save, the reviewer-side branch rows, the Owners
  card, the tag typeahead and the Data shaper's buttons. CI's `test` job
  installs Chromium and sets `RRW_REQUIRE_BROWSER=1`, so a missing browser
  fails rather than skips.
- **Accepting is session-wide** (#2722). Per-instrument Open and Close
  retired; `routes_operator/_instruments.py` fell 97 lines.
- **Three columns retired by migration.** `d81f3c6a2e47` drops
  `observer_tag` (#2725); `…16ffeb59a` drops
  `responses_visible_when_closed` (#2771); `e2a7c4f9b130` sets the reviewer's
  released-window cell to off, the reviewer's visibility now Raw or off
  (#2726).
- **Who counts, and who is a self-review** (#2727, #2765, #2774, #2778).
  Inactive people keep their pairs, excluded; `is_self_review` and group
  answer copies are re-derived on every relationship change.
- **Duplicate and Replicate copy what they owe** (#2750, #2759, #2766,
  #2773). Observers and cohort rules on Duplicate; a copied instrument's
  set-up, its own rule set, visibility policies, and a default sort that
  names its own fields. The last added `app/services/instruments/_field_refs.py`
  (197 LOC), **the window's only new production module.**
- **Corrections that were defects** (selected): the lobby expander's Save no
  longer wipes a draft's schedule and toggles (#2782); a taken session code
  is a 422, not a 500 (#2748); long codes and names no longer hang Duplicate
  (#2751); Settings CSV refuses a repeated shape name or `field_key` with a
  400 (#2783) and imports a type in any case (#2793); scheduled-trigger
  failures no longer fail Session Home (#2757, #2758); the sort-order error
  now renders a banner (#2819).
- **Retired surfaces and code.** The entity-stats extract
  (`entity_stats_extract.py`, #2770), the `?validated=1` promotion and the
  Validate page's unread fields (#2760), Workflow card State 3 (#2767),
  `responses_visible_when_closed`'s route (#2771), nine uncalled functions
  and a deprecated attribute shim (#2820, #2821), three theme generators
  (#2817), and four layout primitives no markup used (#2763).
- **The records reshaped** (#2811 → #2826). Four specs folded into their
  neighbors; `docs/status.md` and its history archived; `guide/todo_master.md`
  holds open work only, and a segment's close deletes its entries;
  `constitution.md` Article I now says the archived plan records that a
  spec settled.

**Unchanged this window:** the instrument model (no rules-language feature;
the prior snapshot's freeze held), the participant `/results` and
`/collation` contracts, the audit envelope schema, the transaction boundary,
and the email pipeline. Nothing sends. No new dependency except Playwright
in the `dev` extra.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`
(unchanged since 30 September, so every delta compares like with like).

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 279 (271 prior) | **159,532** | +3,437 (+2.2%) † |
| `tests` | 435 (402 prior) | **149,099** | +7,142 (+5.0%) |
| `production` | 207 | **67,504** | +1,058 (+1.6%) |
| `templates` | 62 | **31,637** | +76 (+0.2%) |
| `tooling` | 15 (18 prior) | **11,043** | −5,757 (−34.3%) |
| `migrations` | 84 (81 prior) | **7,157** | +130 (+1.9%) |

† **Archiving moves lines; it does not remove them.** `docs` counts
`docs/archive/` and `guide/archive/`, so the retirement pass, which archived
the status pair (about 770 KB) and folded four specs, shows here as growth.
The live corpus a reader faces shrank from 68 files to 58 (§3).

**Test-to-production is 2.21**, from 2.14. Tests grew 5.0% against
production's 1.6%. My read: most of it is regression tests pinning the
sweeps' defects, one per fix, plus the 45 browser tests; the ratio rises
because production barely moved, not because the tests ran ahead.

**Tests: 5,331 passed, 1 skipped, 0 xfails** (was 5,109 / 16 / 0), run at
`2d7e5b5f` with `node` and Chromium present, so the inline-script parse and
the browser tests ran; `ruff check .` clean. The one skip is the opt-in CSS
parity dump. **The fifteen Wave 5 skips are gone:** #2818 retired eight that
tested nothing still shipped and restored six. Both CI tracks, SQLite with
the browser tests and `postgres:16` with the full `downgrade base + upgrade
head` round-trip, were green on #2826.

**Endpoints and schema: 185 route declarations over 84 migrations** (was 190
/ 81). 182 are `@router.*` (115 POST, 65 GET, 1 PATCH, 1 DELETE) and 3 are
`@app.get` in `app/main.py`. The net five went with Open / Close, the
retired extract and the `responses_visible_when_closed` toggle.

| LOC | File | Δ |
| --- | --- | --- |
| 1,396 | `app/services/responses/_core.py` | +127 |
| 1,360 | `app/services/validation.py` | +60 |
| 1,269 | `app/services/assignments/_generate.py` | +125 |
| 1,267 | `app/web/views/_instruments.py` | −8 |
| 1,257 | `app/services/csv_imports.py` | +3 |
| 1,202 | `app/web/routes_operator/_instruments.py` | −97 |
| 1,183 | `app/web/routes_operator/_quick_setup.py` | +72 |
| 1,147 | `app/web/routes_operator/_operations.py` | +38 |
| 1,108 | `app/services/instruments/_instrument_crud.py` | +154 |
| 1,099 | `app/web/routes_operator/_shared.py` | +15 |

**The plateau held, with the order reshuffled.** Thirteen production modules
are at or above 1,000 LOC, as on 30 September, but not the same thirteen:
`session_lifecycle.py` fell out (1,107 → 994, B20's trigger guard moved
elsewhere and dead paths left) and `_instrument_crud.py` came in (954 →
1,108, Replicate's copying). No file moved more than 154. The largest unit
of UI logic is still `operator/instruments_index.html` at **7,167**
(−35), against `base.html` at 5,370 (−129, dead CSS deleted).

**Where the growth landed:** production churn is **+1 file, −1**. The window
added `_field_refs.py` and deleted `entity_stats_extract.py`; the net +1,058
went onto existing modules, led by `_instrument_crud.py` (+154),
`responses/_core.py` (+127, B2's excluded group members),
`assignments/_generate.py` (+125) and `_quick_setup.py` (+72). This is what
a correction window looks like: no new seams, small additions on the seams
the defects lived in.

**Package shape:** `app/services` 98 modules (unchanged; one in, one out),
`app/web` 69 (of which `app/web/views` 23 and `app/web/routes_operator`
22), `app/db/models` 21.

**Duplication and churn** (`python3 tools/code_metrics.py` at `2d7e5b5f`):

| | ≥10-line blocks | prior |
| --- | --- | --- |
| `app/` | 3,197 / 54,202 = **5.9%** | 6.2% |
| `tests/` | 14,045 / 119,583 = **11.7%** | 12.2% |

Churn, Python lines deleted within 14 days of being written over all 2,815
merges on `main`, is **63,128 of 91,804 (68.8%)** against a same-share
baseline of 56.7%: a **ratio of 1.2×**, unchanged. The duplication that
exists is where it was: the roster route modules at **47% / 42% / 34% /
35%** (`_setup_reviewers.py`, `_setup_reviewees.py`,
`_setup_relationships.py`, `_setup_observers.py`), and
`test_instrument_builder_routes.py` first among tests by absolute lines
(1,681).

## 3. Functional-spec compliance

Every row checked against code at `2d7e5b5f`, a route registered, a service
function present and called, a test covering it, and cross-checked against
the corpus sweep's nine reads at the same commit. **Bold rows changed this
window.** A `⚠ drift` row names the sweep finding that carries it.

| Area | Spec | Status |
| --- | --- | --- |
| **Lifecycle (five states)** | `spec/lifecycle.md` | ✓ shipped. Per-instrument Open / Close retired; accepting is session-wide (#2722). ⚠ drift: a failed Activate demotes `validated` → `draft` unstated (B8); the lobby's narrower edit gate unlisted (B2) |
| Assignments engine | `spec/assignments.md` | ✓ shipped. Inactive pairs kept and excluded (#2727); `is_self_review` re-derived on relationship edits (#2774). ⚠ drift: the combinator enum is `ALL_OF` / `ANY_OF` / `PIPELINE`, not `NONE_OF` (B15) |
| **Validate page** | `spec/validate_page.md` | ✓ shipped. 22 rules (unchanged); verdict fields retired (#2760). ⚠ drift: it commits a derived cache the spec says it never writes (B12) |
| **Workflow card** | `spec/workflow_card.md` | ✓ shipped. State 3 retired (#2767); Prepare shows "Preparing…" and takes one click (#2715) |
| **Instruments** | `spec/instruments.md` | ✓ shipped. Replicate copies the set-up, its own rule set and the visibility policies (#2759, #2766). ⚠ drift: the card's Save is not atomic (A16) |
| Response-field branching | `spec/instruments.md`, `spec/reviewer-surface.md` | ✓ shipped. `MAX_BRANCH_DEPTH = 2`; unchanged; the browser tests drive it |
| **Setup pages** | `spec/setup_pages.md` | ✓ shipped. ⚠ drift: the no-match count line (C1), live editor rows on a closed session (C3) |
| Operations pages | `spec/operations_pages.md` | ✓ shipped. SQL rollups in `monitoring.py`; unchanged |
| Session owners / tags | `spec/session_owners.md`, `spec/sessions_overview.md` | ✓ shipped. Unchanged; covered by the browser tests since #2710 |
| **Participant model** | `spec/participant_model.md` | ✓ shipped. `observer_tag` retired (#2725); observers see what reviewers see (#2798) |
| **Visibility policy** | `spec/visibility_policy.md` | ✓ shipped. The reviewer's cells are Raw or off (#2726). ⚠ drift: legacy rows that fail the per-cell rule (A17) |
| **Reviewer surface** | `spec/reviewer-surface.md` | ✓ shipped. Prev / Next on a closed surface (#2723); the self-review row marked (#2799); absorbed the role navigator spec (#2815) |
| **CSV contracts + round-trip** | `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` | ✓ shipped. Four Settings-import defects fixed (#2783, #2788, #2792, #2793). ⚠ drift: the Settings export does not round-trip byte-stable (D2) |
| **Extracts** | `spec/extract_data.md` | ✓ shipped. Entity-stats extract retired (#2770); Zip all (#2769, #2800). ⚠ drift: a no-instrument metadata extract drops zero-response entities (D5) |
| Audit | `spec/architecture.md` | ✓ shipped. `EVENT_SCHEMAS`, 152 event types (was 148), strict in tests |
| **Permissions / identity** | `spec/permissions.md`, `spec/audience_and_identity_model.md` | ✓ shipped; every route's gate matches the matrix. ⚠ drift: any admin can grant admin through Invite (F1) |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped; render only |
| **Email dispatch** | `spec/email_infra_options.md` | ⛔ blocked. Submit now queues the responses-received confirmation (#2753); nothing in `app/` calls a transport. Segment 14B, needs institutional Azure |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off. `rehydrate_enabled` defaults to `False`; the routes answer 404 |
| **Blob storage** | `guide/blob_storage_candidates.md` | ⏸ not built; the spec moved to `guide/` as candidates (#2813) |
| Operator theming | `spec/visual_style_rrw.md` | ⏸ planned. `guide/deferred_consolidated.md` Part A |

**Doc drift: two sweeps closed, a third found 156 more.** The 2026-10-01
and 2026-10-03 registers (242 and about 236 findings) were each worked to
nothing open within a day or two. The 2026-10-05 sweep at this commit found
156 on a corpus ten files smaller; its rows are in
`guide/findings_2026-10-05_corpus.md`. Fewer are provenance, more are detail
the window's own behavior changes left behind. The functional spec carries
26 of them.

## 4. Strengths

- **A correction window that subtracted.** Some sixty behavior fixes and
  retirements moved production by **+1,058 LOC**, and the window removed
  five routes, three columns, one production module, three generators
  (tooling −34%), fifteen permanent skips and nine uncalled functions. My
  read: the retirements were traced before they were made (each of #2820 and
  #2821 named every caller it checked), which is why none needed a revert.
- **What was checked by hand is now checked on every PR.** The prior
  snapshot's first move asked for exactly this. 45 Chromium tests drive the
  builder's staging script, the reviewer's branch rows, the Owners card and
  the typeahead, and CI fails rather than skips without a browser.
- **The registers close.** Two corpus sweeps, 242 and about 236 findings,
  each worked to an archived register with nothing open, the code defects
  first and each with a regression test. The process the series has argued
  for (find, register, decide, fix) ran at scale twice in a week.
- **The schema moved only by retirement.** All three migrations drop or
  narrow something already retired in code, and each round-tripped on
  `postgres:16` before merge.

## 5. Weaknesses

- **The sweeps still find real defects, and this one found a privilege
  bug.** Any admin can create an admin through Invite, past the super-admin
  rule Promote enforces (F1). The test that pins invite-as-admin runs as a
  super-admin, so it could not see the gap. A wider point: two sweeps had
  passed over the same code. Fourteen medium defects came with it, among
  them a non-atomic Instrument Save and legacy visibility rows that fail
  every Save of their card. No plan yet; the register is a day old.
- **The documentation corpus is heavier than the code.** `docs` is 159,532
  lines against 67,504 of production, and three full reads in five days each
  found more than 150 findings. Archiving shrinks what a reader faces (68 → 58
  files) but not the maintenance load the specs carry in detail. The
  functional spec, technology-neutral by design, is the weakest file in two
  consecutive sweeps (26 findings this time), because it restates behavior
  the per-surface specs own and drifts when they change. Filed in the
  register; no plan to shrink it.
- **`operator/instruments_index.html` is 7,167 lines.** It is now covered by
  browser tests, which was the stated precondition for extracting from it,
  but no builder change has arrived to carry the extraction. Watch, as §9
  says.
- **Prepare is still about 13 seconds**, now with a "Preparing…" label
  rather than none (#2715). The feedback gap closed; the time did not.
- **Nothing sends email, and nothing is deployed.** Unchanged. The NUS
  status names the same two external blockers as on 1 October: a runner VM
  SKU awaiting Microsoft Support and the production hostname.

## 6. Bugs and regressions

**Known open bugs at `2d7e5b5f`: one high and fourteen medium**, all in the
2026-10-05 register §1, none yet fixed. The high one is the admin-mint path
(F1). The medium ones cover:

- the Instrument card's partial Save (A16) and legacy visibility rows (A17);
- a reminder after a token regenerate that mails the pre-regenerate link
  (G's Gc1; related to the `regenerate_token` stub in `guide/todo_master.md`);
- Activate's unstated demotion (B8) and the lobby's narrower gate (B2);
- the roster no-match count line (C1) and closed-session editor rows (C3);
- the Settings round trip (D2), the phantom email override (D12), dropped
  short response rows (D18) and unchecked CSV text lengths (D11);
- the unstyled Owners Remove button (E7) and the dark pending-row contrast;
- the practice kit's CI step (I2) and the test fixture's schema drop on
  `DATABASE_URL` (H12).

Also checked: 0 open issues and 0 open pull requests on GitHub, 0 xfails,
one deliberate skip.

Worth remembering from the window, each now with a guard:

- **The lobby expander's Save wiped a draft's schedule and toggles** (#2782).
  Renaming a draft reset `scheduled_activate_at`, the invite and reminder
  offsets, the release window and both roster toggles. Found by the
  2026-10-03 sweep and reproduced before it was fixed.
- **Duplicate and rehydrate hung on a 64-character code** (#2751).
  `_unique_code` could not make room for its suffix.
- **A taken session code answered 500** (#2748). The unique constraint was
  enforced only by the database.
- **Fifteen tests had been skipped since Wave 5** (#2818). Eight tested
  nothing still shipped and were deleted; six failed only because the page
  now renders every instrument's card, and were restored with a
  card-scoped helper.

## 7. Estimated size upon completion

**Current: production 67,504, templates 31,637** at `2d7e5b5f`.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| The 2026-10-05 register's code defects | +300–600 | +50–150 | rulings on about half of them |
| Segment 14B, email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20, operator polish and documentation | +200–500 | +300–600 | institutional Azure deployment concluded |
| Blob storage (18Q) seam and first consumers | +400–700 | +50–150 | an institutional storage account |
| Operator theming (stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |
| **Projected floor** | **69,484–71,064** | **32,357–33,187** | |

Excludes anything past v1 and every entry in `guide/deferred_consolidated.md`
Parts A and C.

**Reconciliation: production grew by about a third of what the named work
would add, with none of it started.** The 30 September snapshot projected
**68,126–69,406** production and **32,231–32,961** templates. Production is
**67,504**, below the floor by 622, and templates **31,637**, below by 594,
for the first time in five snapshots. None of the five named items started;
the window's +1,058 was corrections. The new first row is this snapshot's
own register, sized from the defects' locations rather than a plan. The
other five carry forward unchanged. It is a floor, not a forecast.

## 8. Bottom line

Review Robin Web spent five days correcting and subtracting rather than
building. Two full corpus sweeps were worked to empty registers, the
builder's hand checks became 45 browser tests, and the records lost their
two largest files, all on a test suite now at 5,331 with one deliberate
skip. A third sweep at this commit still found a privilege bug and fourteen
medium defects, so the code is not as settled as the closed registers
suggested. The one live thread is unchanged: **nothing sends email, and
nothing is deployed**, held by the same two external decisions as on
1 October.

**Recommended next moves, at most three:**

1. **Fix the register's defects before anything else, the privilege bug
   first.** F1 is a single missing guard, `requires_super_admin` on an
   invite that sets the admin flag, and it is the only finding that widens
   who can do what. Then the data paths a pilot would hit: the Instrument
   Save (A16, A17), the reminder link (Gc1) and the Settings round trip
   (D2, D12). First because each is reachable through ordinary use, and the
   deployment this window waited on will put real operators in front of
   them.
2. **Rule the 30 open decisions in one sitting, then let the sweep cadence
   resume.** Three corpus reads in five days found diminishing provenance
   and more behavior; the remaining register needs the author's choices,
   not another read. The next sweep should come from `close_check --stale`
   (eight weeks or 500 merges), not from a fresh window.
3. **Shrink the functional spec to what only it says.** It drifts with every
   per-surface change because it restates them (26 findings, G19 the
   restatements). Pointing at the surface specs where it now repeats them
   would cut the next sweep's largest single file. Third because it is
   maintenance, not correctness.

**Settling the 30 September proposals.** Move 1, *make what has been checked
stay checked, and keep the NUS path ready*: **browser tests shipped**
(#2706 → #2711, 45 tests in CI); the NUS path is ready on the project side
and still blocked outside it. Move 2, *freeze instrument scope*: **held**. No
rules-language feature landed, and the window removed a per-instrument
control rather than adding one. Move 3, *make the next builder change pay
for one extraction*: **not triggered**. No builder change arrived;
`instruments_index.html` is 35 lines smaller.

---

## 9. Proposed file splits — watchlist

**Still no split queued.** The watchlist reshuffled; nothing passed a
tripwire.

- **`app/web/templates/operator/instruments_index.html` (7,167 LOC, −35).**
  First on the list. Its precondition, browser tests over the script, is now
  met; the trigger, a pilot-driven builder change, is not. Extract one
  interaction at a time with its view contract and tests.
- **`app/web/routes_operator/_instruments.py` (1,202 LOC, −97).** Moved
  away from its ~1,400 tripwire. **The A16 fix and this seam are the same
  cut:** making the card's Save atomic means validating the whole payload
  before any service writes, which is the `/save` parsing that the planned
  `_save.py` sibling would hold. If A16 is fixed by reordering in place, the
  split stays unneeded.
- **`app/services/responses/_core.py` (1,396 LOC, +127).** Now the largest
  production module. B2's excluded-group-member rules landed here;
  branching's rules already left for `_branching.py`. Watch past ~1,500.
- **`app/services/validation.py` (1,360 LOC, +60).** Carried; the `_check_*`
  registry still carves into a `_rules/` sub-package. Revisit past ~1,450.
- **`app/services/assignments/_generate.py` (1,269 LOC, +125).** New to this
  list. Prepare's include rules and the group-answer copy grew it; Generate
  and Prepare are the seam if it continues.
- **`app/services/instruments/_instrument_crud.py` (1,108 LOC, +154).** New
  to this list: Replicate's copying. The copy path is self-contained and
  would leave as `_replicate.py` if it grows again.

`app/services/session_lifecycle.py` (994, −113) and
`app/web/views/_instruments.py` (1,267, −8) **leave the active list**.
