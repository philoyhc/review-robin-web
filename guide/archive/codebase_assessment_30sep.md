# Codebase assessment — 2026-09-30

**As of** the close of Segment 19T, advanced instruments: seventeen items and
12A, closed and archived 2026-09-30. No segment plan is open in `guide/`; the
two queued segments, 14B and 20, both wait on the institutional Azure
deployment, which `docs/nus_azure_status_v7.md` (2026-10-01) shows mostly
provisioned and held on two external decisions.

**Updated 2026-10-01** to reflect the NUS Azure status v7, the Codex read's
update for it, and the fix of the two doc drifts §3 found — tables, window and
SHA re-taken together at `36e4e6a8`. Only `docs` moved; every code area is
identical to the first writing at `df4ecae3`.

**Since the prior snapshot** (`guide/archive/codebase_assessment_22sep.md`,
`ed8a69e7`), four arcs shipped:

- **19R closed and 19S, the post-assessment register** (PRs #2542 → #2593,
  2026-09-22 → 2026-09-23). The prior snapshot's own reads answered — Prepare
  halved, four index-currency gates, `spec/csv_contracts.md` §3.2 rewritten
  against the code — then a tags-and-owners run the author added.
- **The practice record re-taken** (PRs #2594 → #2596, 2026-09-23).
  `rrw_sdd_in_practice.md` rewritten as one text against a re-measured history.
- **19T Items 1–14, the instrument builder** (PRs #2597 → #2685, 2026-09-24 →
  2026-09-29). Band 3's rows became tables, visibility moved into Band 2's card,
  and response fields gained branching: Show and Require conditions, numeric
  ranges, and a second level.
- **19T Items 15–17, catching up** (PRs #2686 → #2698, 2026-09-30). The Guide,
  a register of seven small fixes, and the instrument intro laid out as two
  columns.

**Numbers taken at `36e4e6a8`, 2026-10-01** — `main` at `0b970eeb` plus this
amendment's drift-fix commits. Window `ed8a69e7..36e4e6a8`: **161 merge commits,
405 non-merge commits, PRs #2542–#2702** (160 numbered) across 2026-09-22 →
2026-10-01, ten calendar days. Everything after `17675383`, the 19T close, is
documentation: the Codex read and its update, the Azure status, this snapshot,
and the drift fixes.

**This document stands alone** and archives
`guide/archive/codebase_assessment_22sep.md` alongside it. Authority lives
elsewhere: `docs/status.md` is the ship-state record (As of 2026-09-30,
1,160 lines), `spec/rrw_functional_spec.md` and its siblings are what §3 audits
against, and `guide/app_responsiveness.md` owns every performance figure quoted
here.

**An independent cold read exists and should be read first:**
`guide/codex_assessment_30sep.md`, taken at `17675383` against its own 21
September predecessor and updated 2026-10-01 for the Azure status. I built this window, so under `constitution.md` III I am
the maker, not a checker. Its size figures reproduce exactly at the same tree;
two of its figures differ from mine by definition, and one it could not take I
could — all three are in §2.

**Development context:** single author, AI agents building, the author checking
each change in a browser against a local run with fake auth,
pre-deployment with an institutional pilot pending. 161 merges in ten days is
not a team velocity figure. **Most of this window was built while waiting on
NUS IT**: the deployment that would put the work in front of users is not the
project's to hurry, and the builder work filled the wait. Read §5 and §8 in that
light. The question is not whether to have built it, but what to build while the
wait lasts.

## 1. What's in the box

Review Robin Web runs structured peer review end to end. An **operator** creates
a **session**, imports **reviewers**, **reviewees**, **relationships** and
**observers** from CSV, defines **instruments** (what gets asked) with **rule
sets** (who reviews whom), and **generates assignments** — the reviewer ×
reviewee × instrument pairs. A **Validate** page runs its registered rules over
the setup; **Prepare** materializes invitations; the session **activates**,
reviewers answer on their own surface, and the operator watches **Invitations**
and **Responses** roll up. Afterwards **reviewees** see their results and
**observers** see a collation, each under a visibility policy resolved per
audience and phase. Configuration round-trips through CSV, every mutation writes
an audit event, and the whole thing is a server-rendered FastAPI + Jinja monolith
on Postgres with no JS build step.

**New since the prior snapshot:**

- **Response fields can branch** (19T Items 10–14, PRs #2638 → #2685). A
  response field may govern the fields below it: an Integer, Decimal or List
  parent's condition opens them (**Show**) or makes them required while it holds
  (**Require**, stored as `response_fields.branch_mode`); numeric conditions take
  ten spelled-out operators and inclusive or exclusive ranges stored as
  `low to high`; a governed field may itself be a parent, **one level down**, and
  a third level is refused by name. Evaluation lives in
  `app/services/responses/_branching.py` (536 LOC) and `_branch_rule.py` (100),
  **the window's only new production modules**. Two migrations landed the shape
  inert before any write path: `63b1bb107eb0` (the self-reference and condition)
  and `c4e9a1d27b58` (the mode). A closed branch holds no value; answers below a
  parent lock its condition and membership; the save hold, the reviewer surface,
  the counts, clone, Replicate, the settings CSV and the extract all walk the
  chain.
- **The builder became row-based before it branched** (19T Items 7–9, PRs
  #2623 → #2637). Visibility is edited in Band 2's "Who can see what you wrote"
  card; display and response fields are Band 3 tables with an Active checkbox
  and ▲ ▼; the response pills and ✓ retired. Branching was then added to one row
  model rather than kept in step across pills, rows and a preview.
- **Required fields counted per assignment** (19T Item 11, PRs #2649 → #2656).
  A governed field is required only while its branch is open, so the static
  required count became per-assignment, and the rollups route a branching
  instrument to a Python path.
- **Prepare halved** (19S Item 3, #2559). The per-pair ORM insert is a bulk Core
  insert and the self-review recompute a projected bulk `UPDATE`: **26.7 s →
  13.1 s**, queries 134 → 58, at 200 × 200 on a loopback `postgres:16`.
- **Tags and owners** (19S Items 6, 7, 9, 10, PRs #2561 → #2592). Tags at
  creation and on Session Home, one typeahead on every tag box
  (`partials/_tag_typeahead.html`), and Owners on Create and on a Session Home
  card of its own (`app/services/session_owners.py`, `spec/session_owners.md`).
- **Four gates on the indexes** (19S Items 2, 5, 8): `tests/unit/test_index_currency.py`
  checks Done ordering, archived-plan pointers, `docs/status.md`'s As of, and a
  `Blast radius` date; a cited pytest node id must resolve.

**Unchanged this window:** the participant `/results` and `/collation`
contracts, the audit envelope schema, the permission model, the transaction
boundary, and the email pipeline (still nothing sends). No new dependency, no
frontend framework, no service split.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 271 (262 prior) | **156,095** | +10,183 (+7.0%) † |
| `tests` | 402 (363 prior) | **141,957** | +12,226 (+9.4%) |
| `production` | 207 (205 prior) | **66,446** | +2,905 (+4.6%) |
| `templates` | 62 (60 prior) | **31,561** | +2,400 (+8.2%) |
| `tooling` | 18 | **16,800** | +356 (+2.2%) |
| `migrations` | 81 (79 prior) | **7,027** | +110 (+1.6%) |

† **The `docs` counter changed this snapshot, and the prior is rebased to
match.** `guide/assessment.json` put all of `guide/**` in `docs`, which counted
the assessments' own `codebase_assessment_*.json` sidecars — measurement output,
not documentation — as **28,816 lines, 16% of the area**. The area now excludes
them. The 22 September baseline is rebased from its own per-file map (262 files,
145,912 LOC rather than 269 / 170,435), so the delta above compares like with
like. At `df4ecae3` the old counter read 184,291 against the new one's 155,475 —
the Codex read's 183,995 at `17675383` is the old counter before its own
document — and its "2.77× production" ratio is **2.34×** without the sidecars
(2.35× at `36e4e6a8`).

**Test-to-production is 2.14**, from 2.04. Tests grew 9.4% against production's
4.6%. My read: branching explains most of it — one feature crossing persistence,
save validation, response entry, completeness, extracts, clone and the settings
CSV, each pinned separately — and the Codex read's caution is right that the
next tests should be justified by the failure they detect, not the states the
builder can reach.

**Tests: 5,109 passed, 16 skipped, 0 xfails** (was 4,636 / 16 / 0; re-run at `c0bf5bf5`; `36e4e6a8` changed spec prose only), `ruff check .`
clean, `node` present so `tests/integration/test_inline_scripts_parse.py` ran. The
16 skips are the same 16 as on 22 September — fifteen Wave 5 PR 5.3 scope
retirements and the opt-in CSS parity dump. Both CI tracks, SQLite and
`postgres:16` with the full `downgrade base + upgrade head` round-trip, were
green on the 19T close (#2698's head, `c4475061`).

**Endpoints and schema: 190 route declarations over 81 migrations** (was 188 /
79). 187 are `@router.*` (121 POST, 64 GET, 1 PATCH, 1 DELETE) and 3 are
`@app.get` in `app/main.py`; the Codex read's 187 is the router count, the same
definitional split the prior snapshot recorded.

| LOC | File | Δ |
| --- | --- | --- |
| 1,300 | `app/services/validation.py` | unchanged |
| 1,299 | `app/web/routes_operator/_instruments.py` | +20 |
| 1,275 | `app/web/views/_instruments.py` | +226 |
| 1,269 | `app/services/responses/_core.py` | +160 |
| 1,254 | `app/services/csv_imports.py` | +8 |
| 1,144 | `app/services/assignments/_generate.py` | +25 |
| 1,111 | `app/web/routes_operator/_quick_setup.py` | +100 |
| 1,109 | `app/web/routes_operator/_operations.py` | unchanged |
| 1,107 | `app/services/session_lifecycle.py` | unchanged |
| 1,084 | `app/web/routes_operator/_shared.py` | +23 |

**The Python plateau held; the template did not.** Thirteen production modules
are at or above 1,000 LOC (twelve on 22 September — `app/services/instruments/_band2.py`
crossed, at 1,013, +351). No module in the top ten moved more than 226, against
five that moved over 200 last window. The window's size went elsewhere:
**`app/web/templates/operator/instruments_index.html` grew 5,642 → 7,202 (+1,560)**
and is now 31% larger than `base.html` (5,499, +179), and its integration test
`tests/integration/test_instrument_builder_routes.py` grew +1,316 to 9,290. The
largest single unit of UI logic in the product is one template's inline script,
and it is where the next builder change will be expensive.

**Where the growth landed:** production churn is **+2 files, −0**. The two new
modules (`_branching.py`, `_branch_rule.py`) took 636 of +2,905; the other 2,269
went onto existing modules, led by `_band2.py` (+351), `views/_instruments.py`
(+226), `session_owners.py` (+181) and `responses/_core.py` (+160). The service
layer took branching's rules; the template took its authoring.

**Package shape:** `app/services` 98 modules (was 96), `app/web` 69 (of which
`app/web/views` 23 and `app/web/routes_operator` 22), `app/db/models` 21.

**Duplication and churn** (`python3 tools/code_metrics.py` at `df4ecae3` — the code, and so both
figures, unchanged at `36e4e6a8` — the standing items
`guide/README.md` requires):

| | ≥10-line blocks | prior |
| --- | --- | --- |
| `app/` | 3,318 / 53,341 = **6.2%** | 6.3% |
| `tests/` | 13,831 / 113,438 = **12.2%** | 13.0% |

Churn — Python lines deleted within 14 days of being written, over all 2,688
merges on `main` — is **62,119 of 85,224 (72.9%)** against a same-share baseline
of 61.5%, a **ratio of 1.2×** (was 1.1×). Both sit below the thresholds for
acting. The Codex read could not measure churn from its shallow checkout and
said so rather than guessing; this clone has full history. The ratio's rise is
small, and my read is that it is the builder rewriting its own weeks-old rows
(Items 1, 8, 9 each replaced the prior item's controls), which is what the
metric exists to notice.

The duplication that exists is where it was: the roster route modules at **47% /
42% / 34%** (`_setup_reviewers.py`, `_setup_reviewees.py`,
`_setup_relationships.py`), and, new to the tests' list,
`test_instrument_builder_routes.py` leading by absolute duplicated lines
(1,628).

## 3. Functional-spec compliance

Every row checked against code — a route registered, a service function
present and called, a test covering it — at `df4ecae3` (the code is unchanged at
`36e4e6a8`), not against the spec's description of itself. **Bold rows changed this window.**

| Area | Spec | Status |
| --- | --- | --- |
| Lifecycle (five states) | `spec/lifecycle.md` | ✓ shipped — `activate_session`, `revert_session_to_draft`, `expire_session` in `session_lifecycle.py`; unchanged |
| **Assignments engine** | `spec/assignments.md` | ✓ shipped — `replace_assignments` inserts in bulk since 19S.3 (`db.execute(insert(Assignment), …)`, 2026-09-22) |
| Validate page | `spec/validate_page.md` | ✓ shipped — 22 rules in `REGISTERED_RULES` (22 on 22 September); unchanged |
| **Instruments** | `spec/instruments.md` | ✓ shipped — Band 3 display- and response-field tables, visibility edited in Band 2 (19T.7–9, 2026-09-26); the overview's drift fixed 2026-10-01, below |
| **Response-field branching** | `spec/instruments.md`, `spec/reviewer-surface.md`, `spec/csv_contracts.md` §3.3 | ✓ shipped 2026-09-27 → 2026-09-29 — `MAX_BRANCH_DEPTH = 2` in `_branching.py`, enforced on Save and in both settings-CSV phases; a third level refused in `test_two_level_branching_authoring.py` |
| Setup pages | `spec/setup_pages.md` | ✓ shipped — routes unchanged; the roster CSV column `PhotoLink` renamed `ProfileLink` (19T.5) |
| **Operations pages** | `spec/operations_pages.md` | ✓ shipped — SQL rollups in `monitoring.py`, now counting a required governed field per assignment (19T.11) |
| Workflow card | `spec/workflow_card.md` | ✓ shipped — Prepare creates the invitations; `_workflow.py` unchanged |
| **Session owners** | `spec/session_owners.md` | ✓ shipped 2026-09-23 — `set_owners` on Create; `owners/add`, `owners/{uid}/remove`, `owners/lock` on Session Home; the spec itself new this window |
| **Session tags + typeahead** | `spec/sessions_overview.md` | ✓ shipped 2026-09-22 → 2026-09-23 — `session_tags.set_tags` on Create and Session Home; `partials/_tag_typeahead.html` on three pages |
| Participant model | `spec/participant_model.md` | ✓ shipped — `require_reviewee_in_session` / `require_observer_in_session`; unchanged |
| Visibility policy | `spec/visibility_policy.md` | ✓ shipped — `resolve_mode` over the 3 × 2 grid |
| **Reviewer surface** | `spec/reviewer-surface.md` | ✓ shipped — branch cells close and open live; the intro as two columns (19T.17, 2026-09-30) |
| **CSV contracts + round-trip** | `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` | ✓ shipped — `session_config_io` reads and writes `branch_*`; §3.2 rewritten against the code (19S.4) |
| **Extracts** | `spec/extract_data.md` | ✓ shipped — exports state each branch condition (19T.10, 19T.13) |
| Audit | `spec/architecture.md` | ✓ shipped — `EVENT_SCHEMAS`, 148 event types, strict in tests |
| Permissions / identity | `spec/permissions.md`, `spec/audience_and_identity_model.md` | ✓ shipped — code unchanged; Easy Auth headers, `ALLOW_FAKE_AUTH` false in deployed envs |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped — render only; nothing sends |
| Previews hub | `spec/preview_hub.md` | ✓ retired (19Q.1) — the spec is a retirement notice |
| Email dispatch | `spec/email_infra_options.md` | ⛔ blocked — `invitations.py` writes `status="queued"` and nothing in `app/` calls a transport; Segment 14B, needs institutional Azure |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off — `rehydrate_enabled: bool = False`; the routes answer 404 |
| Blob storage | `spec/blob_storage.md` | ⏸ stub, not built — no storage client in `app/`; plan at `guide/segment_18Q_blob.md` |
| Operator theming | `spec/visual_style_rrw.md` | ⏸ planned — `guide/deferred_consolidated.md` Part A |

**No `⚠ drift` at `36e4e6a8`; there was one at `df4ecae3`, and it is fixed.**
`spec/instruments.md`'s overview — the Band 3 bullet, the band shorthand table and
the layout diagram — described Band 3 as the response-field table alone, while
the code has had a display-field table in its left column since 19T Item 8
(2026-09-26). The detailed "Display-field table" section further down was
correct; the summary above it was not swept when the table landed. All three
now name both tables (`c0bf5bf5`). A spec-writer check of that fix found the
Band 2 bullet and diagram line stale the same way — a preview row alone, where
19T Item 17 put the intro columns above it, and "Name and Email always" where a
group row shows Name only — fixed in `36e4e6a8`.

**One design record was behind its result, and is fixed.**
`guide/archive/advanced_instruments.md` called Item 6's second level "logged as 19T Item
14", and `guide/README.md`'s row for it said "the first five are built", though
19T Item 14 closed 2026-09-29. The Codex read found it and the audit confirmed
it; both now say every item shipped (`c0bf5bf5`).

The gates still cover the mechanical half — every anchored backticked path,
every `§N` pointer, every cited pytest node — and still cannot tell whether a
summary paragraph describes the tables below it.

## 4. Strengths

- **A rules language was added without a new seam.** Branching is conditions,
  modes, ranges and two levels, and its business rules sit in two new service
  modules (636 LOC); the view layer supplies shape, the template authors. The
  architectural split that absorbed six segments last window absorbed a
  domain-model change this one.
- **Storage landed before behavior, twice.** `63b1bb107eb0` shipped the branch
  columns inert before any write path, and `c4e9a1d27b58` stored the mode before
  Require was enabled (Codex on #2671 asked for exactly that order). Each
  migration was live and round-tripping on `postgres:16` before code could write
  it.
- **The feature was carried to every surface, not stopped at the builder.**
  Branch shape travels through clone, Replicate, both settings-CSV phases, the
  reviewer surface, completeness, the summary, the results and the extract. A
  branch that the builder can author and the export cannot describe does not
  exist in this tree.
- **The prior snapshot's user-facing finding was acted on the next day, with a
  measured result.** 19S Item 3 halved Prepare and recorded that its own premise
  was wrong — the insert was the larger half, not the smaller — rather than
  claiming the planned figure.
- **Gates that read no Python kept growing.** The window added four
  index-currency checks and a resolvable-pytest-node check (19S Items 2, 5, 8),
  and `tools/close_check.py` ran at every one of 19T's item closes and at the
  segment's. They check that records point at things that exist; §5 is the
  reminder of what they cannot check.

## 5. Weaknesses

- **`operator/instruments_index.html` is 7,202 lines and one change away from
  unreadable.** It holds layout, staged state, validation, preview rebuilding,
  row movement, branching and lock behavior in one inline script, and it grew
  28% in nine days. The Codex read's proposal — the next builder change extracts
  one complete interaction with its view contract and tests, rather than
  splitting markup, script and tests separately — is right. No plan; there is
  no builder change queued.
- **The builder's browser behavior is checked by hand, and only by hand.** The
  builder is client-side staging before one save; tests prove the posted payload
  and the parsed script, not that keyboard and pointer sequences produce them.
  The author checks each change in a browser against a local run, and headless
  Chromium in the sandbox drove the rows, the "+" / X / ✓ sequence and the tag
  and owner scripts too, finding three defects on main (19T Item 1,
  `guide/archive/segment_19T_advanced_instruments.md`).
  `guide/post_azure_todo_checklist.md` items 5 and 6, the tags, owners and 19T
  surface, were checked locally by the author on 2026-10-01, bar item 5's
  Safari and screen-reader rows. *Corrected 2026-10-01:* this bullet first
  said no person had used the window in a real browser, on a record that said
  the author runs nothing locally; the author always has. **What is
  unverified is narrower:** nothing repeats those checks, so an edit to the
  builder's script can break a sequence that only the next hand check would
  catch, and what only a deployment shows (real Easy Auth, the live app on
  Postgres, the gateway, the deployed configuration) has not been seen. That
  waits on the NUS deployment, whose remaining path
  `docs/nus_azure_status_v7.md` holds on two external decisions: a runner VM SKU that Southeast Asia can actually allocate
  (repeated `SkuNotAvailable`, awaiting Microsoft Support) and the production
  hostname, which NUS is deciding for a family of applications. The private Web
  App, PostgreSQL, Key Vault, Application Insights, Easy Auth v2 and the
  gateway's reachability to the private endpoint are in place; none of that is
  application evidence yet.
- **Prepare is still 13 seconds with no feedback.** Halved, not solved; the
  third materialization is still in it, and whether 13 s wants another pass or a
  progress indicator is recorded as unsettled in `guide/app_responsiveness.md`.
- **The complexity is combinatorial now.** Active and inactive fields, Show and
  Require, numeric and list operators, saved responses, two levels, three
  audiences. The two-level limit is the useful product boundary; nothing but
  judgment keeps the next request from moving it.
- **The records went stale faster than the work, again.** Both drifts §3
  found — a spec overview and a design record, each a state behind — survived
  item closes that ran their own checks, and both were found by a cold read
  rather than a gate. They are fixed; the pattern the prior snapshot named is
  not.
- **Nothing sends email.** Unchanged, and still the gap between ready and
  shippable; Segment 14B waits on institutional Azure.

## 6. Bugs and regressions

**No known open bugs at `36e4e6a8`.** What I checked, again on 2026-10-01: 0 open issues and 0 open
pull requests on GitHub; 0 xfails; the 16 skips read and confirmed as the same deliberate set as on
22 September; the 19T plan's item Status blocks, whose every read finding is
recorded as fixed; and both cold reads of this window.

Worth remembering — the first three now have a guard, the fourth is a record:

- **A lobby expander's Enter archived the session** (#2579). An implicit form
  submit hit the archive button; `tests/integration/test_lobby_enter_does_not_submit.py`
  pins the disabled first submit and the keydown guard (the key press itself
  was checked by hand in Chromium).
- **A rejected Relationships row consumed its pair** (19S Item 4, #2555): a
  later row for the same pair in the same file was then refused as a
  duplicate. Found by rewriting `spec/csv_contracts.md` §3.2 against the code.
- **A hidden governed field under Require could never be satisfied** (19T Item 13
  read, #2676): its R was grayed, so the rollups would have owed it forever. A
  hidden governed field is now never required.
- **The intro's measured split had five defects before it was retired** (19T
  Item 17 reads, #2693): Lock measuring pre-edit text, DOM order off the visual
  order, focus lost on every placement, a scrollbar loop, a breakpoint swallowed
  by the loop guard. All were fixed, then the author replaced the split with a
  fixed layout (#2695), which made them moot and retired their tests — a record
  that a measured layout was harder to get right than it looked.

## 7. Estimated size upon completion

**Current: production 66,446, templates 31,561** at `36e4e6a8` (unchanged since `df4ecae3`).

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | institutional Azure deployment concluded |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |
| **Projected floor** | **68,126–69,406** | **32,231–32,961** | |

Excludes anything past v1 and every entry in `guide/deferred_consolidated.md`
Parts A and C.

**Reconciliation — templates overtook their floor for a fourth consecutive
window; production reached the top of its range.** The 22 September snapshot
projected **65,221–66,501** production and **29,831–30,561** templates.
Production is **66,446**, inside the top of that range — but none of the named
work started, so the range was reached by unnamed work, not delivered by the
items. Templates are **31,561**, past the top by 1,000, almost all of it
`instruments_index.html`. The named items carry forward unchanged because all
five are still unstarted and three are blocked;
the floor moves only by what this window added. As the last three snapshots
said, it is a floor and not a forecast.

## 8. Bottom line

Review Robin Web is feature-complete for a pilot, and this window made its
instrument model substantially more expressive — branching with two modes,
ranges and two levels, carried to every surface — without a new seam in the
Python and with 5,109 tests green. It also made the builder's one template the
largest UI unit in the product, its interaction checked by hand in a browser
and repeated by nothing. The one
live thread is unchanged — **nothing sends email, and nothing has been
deployed** — but on 2026-10-01 it is better
described: most of the NUS foundation is provisioned, and what blocks the rest
is a regional capacity problem and a naming decision, neither of them the
project's to make.

**Recommended next moves, at most three:**

1. **While the wait lasts, make what has been checked stay checked, and keep
   the NUS path ready.** The wait is NUS IT's, and nothing here shortens it.
   - **The NUS path.** Keep the project-side runner, gateway, secrets and
     migration work in `docs/nus_azure_status_v7.md` ready for the day its two
     blockers clear, without guessing the hostname or retrying the VM.
   - **Repeatable browser checks for the builder.** The author's local checks
     settle a change once; nothing re-runs them when a later edit touches the
     same script. Turning the checklist rows a headless browser can settle
     into committed tests protects what has been checked, and adds no
     interaction. Prepare's 13 s (§5) is the other candidate of that kind.
   - **The builder-script extraction still waits** for its trigger (move 3),
     and goes better once those tests exist: a refactor of an untested script
     is checked only by hand.

   First because the window's value lives in client-side staging that only a
   hand check covers, and because the deployment is the one part of the
   product nobody has seen working. The updated Codex read reaches the same
   order on the deployment.
2. **Freeze instrument scope until a real instrument needs more.** Two levels,
   two modes and ranges already multiply across authoring, entry, completeness,
   summaries, results, clone and round-trip. The next rules-language feature
   should arrive with a case it is for.
3. **Make the next builder change pay for one extraction.** Whatever change the
   pilot asks of the builder, extract the interaction it touches from
   `instruments_index.html` — markup, script contract and tests together. Third
   because it has no trigger yet, and should not be scheduled without one.

**Settling the 22 September proposals.** Move 1, *close 19R and deploy*: 19R
closed (#2544); deployment did not happen and is repeated above. Move 2, *fix
Prepare before the pilot*: **half done** — 19S Item 3 halved it (#2559), and 13 s
without feedback remains in §5. Move 3, *re-take the bench*: **not done**; no
page bench was re-taken this window, and the prior's reason (the next question
is a query question, best asked of real data) still argues for doing it after
deployment rather than before. Its §9 watchlist is settled below.

## 9. Proposed file splits — watchlist

**Still no split queued. The Python watchlist barely moved; the candidate that
matters is a template.**

- **`app/web/templates/operator/instruments_index.html` (7,202 LOC, +1,560).**
  **New to this list, and first on it.** Not a size-only split: the seam is one
  interaction at a time — branch-row authoring or preview reconstruction are
  the Codex read's candidates — extracted with its view contract and its tests,
  when a pilot-driven change touches it.
- **`app/services/validation.py` (1,300 LOC, unchanged).** Carried; the
  `_check_*` registry still carves into a `_rules/` sub-package. Revisit past
  ~1,450.
- **`app/web/routes_operator/_instruments.py` (1,299 LOC, +20).** Eighth
  effectively flat window. **101 LOC from its ~1,400 tripwire.** Seam unchanged:
  the `/save` payload parsing into a `_save.py` sibling.
- **`app/web/views/_instruments.py` (1,275 LOC, +226).** New to this list.
  Branch render shapes landed here; if the builder changes again, branch shaping
  is its own adapter.
- **`app/services/responses/_core.py` (1,269 LOC, +160).** New to this list, and
  not a split candidate by size: branch rules already left for `_branching.py`
  and `_branch_rule.py`.
- **`app/services/session_lifecycle.py` (1,107 LOC, unchanged).** Fourth window
  inside 100 of its ~1,200 tripwire with no natural seam. **Watch; do not plan.**

`app/services/csv_imports.py` (+8), `_operations.py` (unchanged) and
`app/services/instruments/_band1.py` (0 this window after +363 last) **leave the
active list**: none moved enough to watch.
