# Codebase assessment — 2026-11-20

**As of** Apply Desk's first phase (AD1 → AD1Q, a whole application built
as a working scaffold on sample data). Review Robin learned to be driven by
another application (23A → 23F). The practice's machinery was made to
reach the packages (23H). **The deployment is unchanged**: Review Robin
is live on Azure since 2026-10-31, and per-row email has sent since
2026-11-05. Apply Desk is not deployed.

**Since the prior snapshot** (`guide/archive/codebase_assessment_06nov.md`,
`c912ae53`), 2026-11-06 → 11-20 (UTC), the window holds 405 PRs:

- **Apply Desk, AD1 → AD1Q** (187 PRs touch `applydesk/`, from 2026-11-12). It is
  `applydesk/`, a fourth package under the Cordware host. It has
  exercises with Form, Process, Panels, Gates, Evaluations, Emails,
  Dossiers, Extract data and an applicant's `/me` page, a status per stage
  with Publish and revert, and scratch exercises held in server memory
  that save until AD2 brings a database. It is governed by 65 numbered
  author rulings and `applydesk/spec/applications.md`.
- **Interoperability, 23A → 23F** (33 PRs touch the handoff and linked-session files):
  - a JSON handoff that creates a populated Review Robin draft;
  - status and results back, as CSVs keyed by application ID;
  - a Settings CSV in the bundle;
  - **linked sessions**: an application's profile takes nine locks
    (rosters, email, release, the instrument's structure and more), and
    Unlink makes the session native;
  - a re-send that keeps a linked draft current.
- **Instruments touch-up** (20J, 20K, 20M):
  - no Full Matrix while a Band 1 link is not set, and Validate refuses
    it (29 rules);
  - one response field per line on the reviewer surface;
  - where display fields sit.
- **Email, finished for now:** 14F closed, and 14C Item 4 added owner
  report emails.
- **Smaller pieces:**
  - 22J, the Setup routes' shared handler;
  - Residential's Support Logs (1D) and Unit scoping;
  - Utilities' photo proof of concept (U4) and interop tools;
  - 23H, the practice's reach over the packages.

**Numbers taken at `6003c8084`**, `main` at #4063: 405 first-parent
commits, PRs #3658 → #4063, 2026-11-06 → 11-20.
- **No edits from the reads.** This snapshot ran beside a corpus sweep at
  the same commit (`guide/sweep_2026-11-20_corpus.md`), whose seven
  verify reads stand in for a separate spec-vs-code audit. Two assessment
  reads ran by agents with no part in the window's builds:
  - a defect read of the window's `app/`, `cordware/` and `alembic/`
    changes (135 files, +7,283 / −1,645), with scratch tests (§6);
  - a read of the four packages, Apply Desk for the first time, with their
    suites and a route fuzz (§6).
- **Where the findings went:**
  - RRW's defects are rows of `guide/findings_2026-11-20_assessment.md`;
  - RRW's spec drift is in `guide/findings_2026-11-20_corpus.md`;
  - each package's findings, sweep and assessment together, are in its own `guide/findings_2026-11-20.md`.

**Development context:** a single author, with AI agents building. The
pace is about 29 PRs a day, almost all small. Every code PR has a Codex
review before merge, and each closing unit has one cold `diff-reviewer`
read (author's ruling, 2026-11-20).

---

## 1. What's in the box

**Review Robin** is unchanged in kind: sessions, rosters bound to the
directory, instruments, rules-generated assignments, Validate and
Activate, the reviewer surface, results and collation, extracts, and
per-row email. It is new in one respect: **another application can now
create, update, read and lock a session**.
- **Handoffs:** `app/services/handoffs.py` (695 LOC),
  `routes_operator/_handoffs.py` and `views/_handoffs.py`.
- **Linked sessions:** `linked_apps.py`, `linked_settings.py` and
  `linked_instruments.py`, with nine `Lock`s per profile. The contract is
  `spec/handoffs.md` and `spec/linked_sessions.md`.
- **Also new:** `due_actions.py` (the Workflow card's due prompts and the
  lobby's Due pill), `owner_reports.py` (an owner's email when a session
  changes), and `roster_actions.py` (22J's shared Setup bodies).

**The Cordware host** mounts five applications: Review Robin, Residential
Operations, Support Logs, Cordware Utilities and Apply Desk.

**Apply Desk** (`applydesk/`, 113 files):
- **Domain modules:** `stages.py` (1,654 LOC), `sample_data.py`,
  `scratch.py`, `scratch_panels.py`, `extract.py`, `handoff.py` and
  `process_save.py`.
- **Routes:** home, `/me` and operator modules.
- **Tests:** 681, browser files included.
- **No persistence yet.** The sample exercises are fixed. A scratch
  exercise lives in server memory (five per browser, eight idle hours).
- **Governance:** the rulings in `applydesk/guide/todo_master.md` stand
  above the spec until the AD1 → AD2 juncture (`rrw_sdd_in_practice.md`
  §6.1).

## 2. Size (LOC)

**Method.** Physical lines in git-tracked files, classified by
`guide/assessment.json`. On 2026-11-20 the file gained an `applydesk` area
(23H). The measurement reproduces the 6 November sidecar exactly at
`c912ae53` under the old classification: the same 1,610 files, with no
difference. Under the new one, `c912ae53` held one Apply Desk file (the
v0.6b handoff, 496 lines), which moves from `docs` to `applydesk`. The
deltas below compare like with like.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `tests` | 662 (636 prior) | **197,120** | +7,060 (+3.7%) |
| `docs` | 377 (354 prior) | **187,796** | +4,842 (+2.6%) |
| `production` | 264 (253 prior) | **87,300** | +4,267 (+5.1%) |
| `templates` | 79 (74 prior) | **36,669** | +861 (+2.4%) |
| `applydesk` | 113 (1 prior) | **32,297** | +31,801 |
| `residentialapps` | 162 (151 prior) | **31,076** | +7,305 (+30.7%) |
| `tooling` | 16 | **13,353** | +296 (+2.3%) |
| `migrations` | 105 (102 prior) | **8,406** | +119 (+1.4%) |
| `utilityapps` | 63 (32 prior) | **8,116** | +4,809 (+145%) |
| `cordware` | 25 | **6,218** | +391 (+6.7%) |

**Production grew by its new seams, not its old files.**
- **New files:** 11 production files carry 2,619 lines. Seven are
  interoperability (1,734); the others are `due_actions`, `owner_reports`,
  `owner_report_sender` and `roster_actions`.
- **Existing files:** they grew by the linked-session locks threaded
  through them. `_quick_setup.py` gained the handoff entry points (+355),
  and `_instrument_crud.py` and `views/_instruments.py` gained 20K/20M's
  layouts (+192, +164).
- **Ratios:** test-to-production is **2.26** (was 2.29). **The packages
  now total 77,707 lines against RRW's 123,969 production and templates**:
  Apply Desk is the largest after RRW.

**Tests: 9,820 passed, 12 skipped** (was 8,451 / 12), with 9,832
collected, at the pinned tree with `node` and Chromium present.
- `ruff check .`, `ruff format --check .` and `pyright` are clean.
- The skips are the Postgres-only tests and the opt-in CSS parity dump,
  as before.
- **The packages alone: 1,708 passed, 0 skipped** (`applydesk` 681,
  `residentialapps` 500, `utilityapps` 289, `cordware` 238), browser
  files included. On 2026-11-06 the three packages then present had 704.

**Test runtime:**

| Where | Measure | Time |
| --- | --- | --- |
| This container, 4 cores, `pytest -n auto` | full suite, wall | **278 s** (9,820 tests; was 246 s for 8,451) |
| CI on `main` at `6003c8084`, workflow `CI` | wall, three shards in parallel | **4m31** (was 2m34) |
| … `test (unit)` | tests; plus pyright 38 s | **2m24** (was 43 s) |
| … `test (integration)` | tests | 1m50 |
| … `test (browser)` | tests | 1m14 |
| CI, workflow `CI - Postgres` | wall, three shards | **4m02** (was 3m46) |
| … `postgres (unit)` | migrations both ways, then tests | 8 s + 1m52 |
| … `postgres (integration-a)` | tests | **3m11** |
| … `postgres (integration-b)` | tests | 1m57 |

**The `unit` shard has become CI's long pole.** It took 43 s on 6
November and takes 2m24 now, because the package suites ride in it:
Apply Desk's 681 tests and their browser files took 180 s alone in the
package read. Its install of Chromium's system packages (35 s) adds to
it. Locally the suite still has no long pole (slowest test 5.4 s). The
Postgres shards flipped: integration-a is now the slow one, after N8
re-cut them on 6 November (N2).

**Endpoints and schema: 213 routes in RRW over 105 migrations** (was 205
over 102).
- **New routes:** the eight are the handoff and linked-session routes:
  `/handoffs/new`, `/handoffs/sessions`, `/handoffs/{id}/status`,
  `results.csv`, `completion.csv`, `/handoffs/{id}/update`,
  `/sessions/{id}/unlink` and `/sessions/{id}/workflow/due-done`.
- **New migrations:** `response_layout` (20K), `display_layout` (20M) and
  `linked_app` (23E).
- **`EVENT_SCHEMAS`** registers **187** event types (was 173).
- **Validate** runs **29** rules (was 28).

| LOC | File | Δ |
| --- | --- | --- |
| 1,867 | `app/web/routes_operator/_quick_setup.py` | +355 |
| 1,519 | `app/services/instruments/_instrument_crud.py` | +192 |
| 1,431 | `app/web/views/_instruments.py` | +164 |
| 1,420 | `app/services/session_lifecycle.py` | +76 |
| 1,384 | `app/web/routes_operator/_instruments.py` | +90 |
| 1,323 | `app/services/assignments/_generate.py` | +17 |
| 1,274 | `app/services/invitations.py` | +156 |
| 1,262 | `app/web/routes_operator/_operations.py` | +43 |
| 1,254 | `app/services/instruments/_band2.py` | +111 |
| 1,215 | `app/services/audit.py` | +44 |

Templates: `operator/instruments_index.html` 7,638 (+419) and `base.html`
6,980 (+134). Apply Desk's largest files are `stages.py` (1,654) and its
Process template (1,536).

**Duplication** (`python3 tools/code_metrics.py`, blocks of 10+ lines):
`app/` **4.0%** (was 4.5%), `tests/` **9.6%** (was 9.9%). 22J's shared
handler lowered the Setup modules' share, but `_setup_relationships.py`
still reads 32% and `_setup_observers.py` 25%. The formatter's
one-parameter signatures keep counting there (6 November §2).

**Churn** is **51.8% against a 44.5% baseline, ratio 1.2×** (unchanged),
over all 4,050 PRs on `main` (3,823 merge commits, 227 squash-merged).

## 3. Functional-spec compliance

This section was checked by the sweep's seven reads at the pinned tree,
spec by spec. The rows that changed this window are in **bold**. Ids:
- **A–H** are rows of `guide/findings_2026-11-20_corpus.md`;
- **D** rows marked *assessment* are in `guide/findings_2026-11-20_assessment.md`.

Every drift in the 6 November table was closed by 14F's close and the
register's PRs (#3662 → #3679).

| Area | Spec | Status |
| --- | --- | --- |
| **Lifecycle** | `spec/lifecycle.md` | ✓ shipped. ⚠ "every transition is idempotent" holds for two (B4); a draft past End closes without expiring (B2); Release on `ready` by direct POST (B5) |
| Assignments engine | `spec/assignments.md` | ✓ shipped. ⚠ six small drifts (B11–B16) |
| **Validate page** | `spec/validate_page.md` | ✓ **29 rules**, key and severity matching the table |
| **Workflow card** | `spec/workflow_card.md` | ✓ shipped. ⚠ **the lobby's Due pill lights where the card shows nothing** (B1, assessment D1); the auto-send captions ignore the email lock (B3) |
| **Instruments** | `spec/instruments.md` | ✓ shipped: 20J, 20K, 20M and linked holds. Provenance to trim (B20) |
| Setup pages | `spec/setup_pages.md` | ✓ shipped: 22J and the linked roster lock |
| **Operations pages** | `spec/operations_pages.md` | ✓ shipped. ⚠ a drill-in promised and not built (B6) |
| **Handoffs, linked sessions** | `spec/handoffs.md`, `spec/linked_sessions.md` | ✓ **shipped** (23A → 23F). ⚠ one route missing from `permissions.md` (B19) |
| **Session owners** | `spec/session_owners.md` | ✓ owner reports match |
| Participant model / identity | `spec/participant_model.md`, `spec/audience_and_identity_model.md` | ✓ shipped. ⚠ **an operator-reviewer sees operator links on reviewer pages** (E2) |
| Visibility policy | `spec/visibility_policy.md` | ✓ shipped |
| **Reviewer surface** | `spec/reviewer-surface.md` | ✓ shipped: stacked responses, display layouts. ⚠ eight drifts (A1–A8) |
| CSV contracts, extracts | `spec/csv_contracts.md`, `spec/extract_data.md` | ✓ shipped. ⚠ D1 |
| **Visual style** | `spec/visual_style_rrw.md` | ✓ shipped. ⚠ **the Email Template pill never reads *Set up*** (E1); "one page per instrument" is stale (E3) |
| Settings inventory | `spec/settings_inventory.md` | ✓ schema and settings match the ORM |
| Email dispatch | `spec/email_infra_options.md` | ✓ per row; bulk off; scheduled waits on 14G |
| **Functional spec** | `spec/rrw_functional_spec.md` | ✓ at intent. ⚠ no word on linked sessions or owner reports (F1) |
| **Cordware host and identity** | `cordware/spec/` | ✓ five applications. ⚠ import-boundary exemptions (F5) |
| **Apply Desk** | `applydesk/spec/applications.md` | ⏸ **sample data, not deployed**. ✓ routes and limits match. ⚠ rulings 26/28 and 33–39 not yet folded, as ruled (its S1, S4) |
| Residential, Utilities | `residentialapps/spec/`, `utilityapps/spec/` | Residential ⏸ sample data, gated; Utilities ✓ deployed. ⚠ frozen drafts still leaned on (Residential S6, S8) |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off. No change |

**The drift is mostly the linked-session work's spec pass.** 23E and 23F
wrote their contracts into `spec/handoffs.md` and `spec/linked_sessions.md`
and kept them right. They also threaded the locks through a dozen other
specs, and those caught most but not all of the exceptions (B7, B8, B17,
E4) and gained segment provenance (B20).

The other drift is older prose the corpus had not read in full since 22
October, most of it in `reviewer-surface.md`, `visual_style_rrw.md` and
`assignments.md`.

**Spec corpus:** 37 files in `spec/` (was 35; `handoffs.md` and
`linked_sessions.md` are new), plus 2 in `cordware/spec/`, 2 in
`applydesk/spec/`, 4 in `residentialapps/spec/` and 2 in `utilityapps/spec/`.

## 4. Strengths

- **A second application, and the practice held.** Apply Desk was
  planned, built and reviewed through 17 segment plans inside the budget,
  with a measured blast radius each. Its 681 tests pass. A route fuzz of
  3,647 requests found only one class of 500, a 4,300-digit path
  number (Apply Desk S8).
- **Interoperability built contract-first and all-or-nothing.** The
  defect read traced the handoff end to end and found it sound:
  - a create discards its draft on any failure;
  - a re-send rechecks the link and editability under the session lock;
  - another operator's transfer answers 409;
  - every lock refuses its routes.

  The contract shipped as two specs the sweep found current.
- **Nothing new is unaudited.** Every new emitter is in `EVENT_SCHEMAS`.
  The three migrations survive both directions on Postgres. No root-path
  URL appears in 164 rendered package pages.
- **Code-level reading caught real defects before merge.** Codex found
  three in 23H alone, each reproduced, fixed with a test and re-reviewed.
  Cold reads did their job in the corpus sweep: the mechanical checks
  passed, and the narrative reads found what they could not.

## 5. Weaknesses

- **CI's unit shard has quadrupled** (§2): 43 s to 2m24, with packages
  riding in it. It is now the merge's long pole.
- **The linked-session locks leak at the edges** (B1, B3, B7, B8, B17,
  E4). Each lock is enforced where it was written. Derived signals miss
  it: the lobby's Due pill, the auto-send captions, the status strip, the
  lifecycle's governance rule. No test asks "does every surface that
  reads X honour lock Y".
- **Several user-facing promises the code does not keep**, each small:
  - the Email Template pill (E1);
  - a drill-in breakdown (B6);
  - the reviewer top bar for an operator-reviewer (E2);
  - idempotence (B4).
- **Apply Desk's scratch store is unbounded across browsers** (Apply Desk
  S10). It matters only if Apply Desk ships before AD2 replaces it.
- **Browser behavior stays the author's to check.** The Instruments
  page's script and Apply Desk's pages were checked to their hooks only.

## 6. Bugs and regressions

**RRW at the pinned tree: one medium, two low, none high.** These are the
defect read's D1 and the sweep's B2 and B3. Add the author decisions §8
names, and two notes.
- **D1 (medium, CONFIRMED):** the lobby's Due pill lights on a linked
  session whose Workflow card shows nothing due. The operator cannot
  clear it.
  - **Cause:** `due_actions` and `sessions_with_something_due` ignore
    `Lock.EMAIL`, which `build_due_lines` honours.
  - **How it arises:** a handoff's create can carry the activation time
    and the offsets that make an action due.
  - Reproduced by the defect read and found independently by the sweep's
    S1b (B1).
- **B2 (low, by trace):** a draft or validated session past End, read by
  a reviewer or the operator's Instruments page, writes
  `instrument.closed` and `session.deadline_reached` without expiring.
- **B3 (low, latent):** the auto-send captions promise sends the email
  lock forbids. They are off while `RRW_SCHEDULED_SEND` is off.
- **Notes (N1, N2):**
  - the lobby runs `due_actions` once per listed session (N+1 work);
  - a re-send that moves Start or End does not recheck the offsets
    against them;
  - the Postgres shards are uneven again (§2).

**The packages: three low code defects and three for the author**, all
in the packages' own registers:
- **Apply Desk:**
  - S8, a huge number in a path or `offset` answers 500, not 404;
  - S9, a list where a JSON string is expected answers 500, not 400;
  - S10, the scratch store's global cap and streaming body limit;
  - S11, `?said=` shows any text;
  - S12, the gate's bundle CSVs carry no formula guard.
- **Residential:** S11, Support Logs' `/unit?back=` lets `/.auth/…`
  through.

None is reachable in production by anyone but the platform super-admin.

**What was checked to say the rest is sound.**
- **The defect read:**
  - the three migrations, both directions;
  - every new emitter's registration;
  - the handoff's authorization, all-or-nothing create and locked
    re-send, and every linked lock against its routes;
  - owner reports (queued at the outermost commit, dropped on rollback);
  - the 6 November register's fixes (M1/L1, N5, L3, L4/N7, L2, N4);
  - 20J's staleness, 20K/20M's setters and round-trips, 22J's guards;
  - the host's token masking.
- **The package read:**
  - the four suites;
  - a route fuzz of every GET route under six identities, with no 5xx
    beyond Apply Desk S8, no leak, and every gate answering as its spec says;
  - a query fuzz of 49 routes × 80 keys × 6 values;
  - template escaping;
  - Apply Desk's scratch isolation across browsers;
  - Support Logs' `ContextVar` Unit;
  - the photo proof of concept;
  - Cordware's changes.

## 7. Estimated size upon completion

**Current: production 87,300, templates 36,669, `cordware` 6,218** at
`6003c8084`. The estimates are my judgment, from the plans and the nearest
shipped analogue.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| This register's defects and the author rows of §8 | +60–200 | +10–40 | rulings |
| 23G, a linked instrument Review Robin may extend | +300–600 | +40–120 | nothing |
| 14G, scheduled and bulk email, paced | +300–600 | +20–60 | an application mail permission |
| Blob storage (18Q) | +400–700 | +50–150 | a storage account |
| Operator theming (stretch) | +150–300 | +100–200 | nothing |
| **Projected floor** | **88,510–89,700** | **36,889–37,239** | |

Excluded: Apply Desk's AD2 and beyond, Residential's wiring and RA
Lifecycle (all their own areas), magic links, and everything in
`guide/deferred_consolidated.md`.

**Reconciliation.**
- **Production:** 6 November projected **83,673–84,903**; it is
  **87,300**, above the ceiling. That projection excluded the
  interoperability work, which then shipped at 1,734 lines of new files
  plus the locks threaded through existing ones. Without it, the window's
  growth sits inside the projection's range.
- **Templates:** projected **36,018–36,348**; it is **36,669**, above, by
  20K/20M's layouts and the linked-session chrome.
- **What the method missed:** a projection that excludes work the author
  then starts is not a floor. This one names 23G for that reason.

## 8. Bottom line

In two weeks and 405 PRs a second application went from nothing to
seventeen closed segments on sample data. Review Robin learned to be
driven by it, and the practice was extended to see it. The defect read
found **one medium in RRW, none high**, and the medium sits where those
two meet: a linked session's lock that one derived signal does not
honour.

**Recommended next moves, at most three:**

1. **Fix D1, and test the locks at their derived edges.**
   - Skip `Lock.EMAIL` in `due_actions`.
   - Rule whether a linked create may carry offsets at all.
   - Add one test that walks each `Lock` against every view that reads
     the thing it locks (the Due pill, captions, status strip). B1, B3,
     E4 and B17 are the same miss, so one test catches the next one.
2. **Take the author's rows in one sitting.** Five of them change what a
   user is told:
   - E1, fix the Email Template pill's predicate or retire it;
   - E2, which top-bar rule stands;
   - E3, rewrite "one page per instrument";
   - B4, narrow the idempotence principle;
   - B6, build or retire the drill-in.

   The rest of the corpus register is spec catch-up for one PR per area.
3. **Rebalance CI before the next package grows.**
   - Move the package suites out of `test (unit)`, into their own shard or
     the `integration` one.
   - Re-cut the Postgres shards (N2).

   A 2m24 unit shard gates every merge.

**Settling the 6 November proposals.**
- **Move 1, fix M1 with L1:** shipped (#3664).
- **Move 2, finish 14F's close as a contract catch-up:** shipped (#3670).
- **Move 3, rule on sending before activation:** settled by 14F's close
  (bulk off, per row only, 14G for the rest).

---

## 9. Proposed file splits — watchlist

**Watched now:**
- **`app/web/routes_operator/_quick_setup.py` (1,867, +355)**, still the
  largest file in `app/`. It now carries the handoff entry points beside
  Quick Setup. **Split candidate:** the handoff routes into
  `_handoffs.py`, which already holds their views' counterpart.
- **`app/services/instruments/_instrument_crud.py` (1,519, +192)**, grown
  by the layout setters. Watch if 23G adds more there.
- **The Setup route modules**, for duplication, not size (§2). 22J took
  the shared bodies; the signatures remain.
- **`app/web/templates/operator/instruments_index.html` (7,638, +419)**
  and **`base.html` (6,980)**, carried.
- **`applydesk/stages.py` (1,654)**, Apply Desk's largest module. It is
  the stage model and readiness rules on sample data, so it is the file
  AD2's persistence will cut into first.
