# Codebase assessment — 2026-10-16

**As of** the end of an eleven-day arc that opened with the 5 October
assessment. Two findings registers were worked to empty, and one of their
findings became Segment 19U, the session-state guard. Five small plans then
shipped and closed in `guide/`: operator pages, UX refinements, ProfileLink,
participant info and Quick Setup update. Then came Accounts, and an audit of
what participants see. No plan is in progress. Segment 21 (the domain
retrofit, `guide/segment_21_domain_retrofit.md`) and the two `docs/` files it
rests on are speculative and on hold (author, 2026-10-16). 14B and 20 still
wait on the institutional Azure deployment.

**Since the prior snapshot** (`guide/archive/codebase_assessment_05oct.md`,
`2d7e5b5f`), five arcs shipped:

- **The registers and the session-state guard** (PRs #2827 → #2917,
  2026-10-05 → 2026-10-09). The 2026-10-05 register and the 2026-10-07 sweep's
  register were each closed with nothing open. Finding Bc4 became Segment 19U.
- **Chips and the operator pages** (PRs #2918 → #2960, 2026-10-09 →
  2026-10-11). Session Home got one lock. Three chip types got one look each.
  Band 3 fields and the self-review and send-on-submit checkboxes became
  chips, and the filled-amber button was retired.
- **What a participant is shown of themselves** (PRs #2961 → #2995,
  2026-10-11 → 2026-10-12). The ProfileLink column and a reviewer-identity
  level on the visibility grid. A per-type choice of which own-entry fields a
  reviewer, reviewee or observer sees. The Observers row editor saves its
  cohort rule with the row.
- **Quick Setup all-or-nothing and the browser checklist run** (PRs #2996 →
  #3024, 2026-10-12 → 2026-10-14). Every file is checked before any is saved.
  Upload cards report problems by kind. The author ran a 45-step browser
  checklist against seed files.
- **Accounts, session tables and the participant audit** (PRs #3025 → #3081,
  2026-10-14 → 2026-10-16). Accounts became a Setup-style table filtered in
  SQL. The three session tables sort alike. The database refuses an illegal
  visibility cell. Archived sessions are off limits to participants
  everywhere. Thirteen of the participant audit's fixes followed.

**Numbers taken at `3d8adb38`**, `main` at #3081, before #3082 (the `guide/`
retirement pass: prose and seven comment repoints) and before this
snapshot's own documents. Window `2d7e5b5f..3d8adb38`: **255 merge commits,
733 non-merge commits, PRs #2827–#3081** (255 numbered), 2026-10-05 →
2026-10-16, twelve calendar days.

**This document stands alone** and archives
`guide/archive/codebase_assessment_05oct.md` alongside it. Authority lives
elsewhere: `spec/` (indexed by `spec/README.md`) is the contract, and
`spec/rrw_functional_spec.md` and its siblings are what §3 audits against.
`guide/todo_master.md` holds the open work. **A bug sweep ran beside it at
the same commit.** Six code-reading agents, each writing scratch tests
against the suite, produced `guide/findings_2026-10-16_bugs.md`. §5 and §6
lean on it.

**Development context:** a single author, with AI agents building. The
author checks each change in a browser against a local run with fake auth.
The app is not yet deployed; an institutional pilot is pending. Unlike the
prior window, this one built features. Its plans were small, opened and
closed inside the window, without a segment number.

---

## 1. What's in the box

Review Robin Web runs structured peer review end to end. An **operator**
creates a **session** and imports **reviewers**, **reviewees**,
**relationships** and **observers** from CSV. They define **instruments**
(what gets asked) with **rule sets** (who reviews whom) and **generate
assignments**. A **Validate** page runs its registered rules over the setup,
and **Prepare** materializes invitations. The session **activates**, reviewers
answer on their own surface, and the operator watches **Invitations** and
**Responses** roll up. Afterwards **reviewees** see their results and
**observers** a collation. What each sees comes from a visibility policy
resolved per audience and phase. Configuration round-trips through CSV, and
every mutation writes an audit event. It is a server-rendered FastAPI + Jinja
monolith on Postgres, with no JS build step.

**New since the 5 October snapshot:**

- **One lock for every session write** (19U, #2881 → #2885).
  `app/services/session_guard.py` (89 LOC) holds `lock_session` and
  `require_state`. Roster, relationship, assignment, instrument, visibility,
  schedule and lifecycle services now re-read the session row under a row
  lock before testing its state; ten modules import it directly (seven
  services, three in `app/web`).
  `app/services/unit_of_work.py` (108 LOC, #2834) gives a multi-service
  request one commit, which is how the Instrument card's Save became all or
  nothing. `app/services/scheduled_events/_fired.py` (174 LOC, #2874)
  records each auto-send by its position, so a sent entry never refires.
- **What a participant sees of themselves** (#2964 → #2992).
  `app/services/participant_info.py` (216 LOC) stores one selection per
  participant type on the session row. Migration `c4a8e2f6d1b3` adds the
  three columns. The views `_reviewer_self.py` and `_participant_self.py`
  render the line on `/summary`, the pre-open page, `/results` and
  `/collation`. Migration `b7e3d91a4c62` adds the reviewer-identity level to
  the visibility grid. A ProfileLink that is not a web address renders `•••`,
  never an `href` (#2969).
- **Quick Setup checks everything first** (#2999, #3000, #3006). The
  incoming-set checks became pure functions in `app/services/csv_imports.py`.
  Quick Setup checks every file and saves all or none.
  `app/web/views/_upload_problems.py` (109 LOC) is the one source of "kinds
  of problem, with counts" for Quick Setup and the four Setup upload cards.
- **Accounts at scale** (#3027 → #3045). `app/services/account_listing.py`
  (300 LOC) filters, counts and pages the Workspace users table in SQL,
  measured at 1,000 and 5,000 accounts (#3032). It replaced a read of every
  row into Python. `app/web/views/_accounts.py` (253 LOC) shapes the table,
  its row expander (all or nothing across the selected rows) and the
  Overview card. Owner adds and revokes serialize on the user row (#3039).
- **Session tables and the visibility grid** (#3046 → #3056).
  `app/web/views/_sessions_table.py` (183 LOC) gives the lobby, Archive and
  Sessions Diagnostics one sort. Migration `e5c1a9d3b7f2` adds
  `ck_view_policy_cell`, so the database refuses an illegal cell. The audit
  card that hunted for illegal cells, `app/web/views/_visibility_audit.py`,
  was deleted: **the window's only deleted production module.**
- **The participant audit** (#3058 → #3073), recorded in
  `guide/archive/participant_surface_check.md`. `return_to` names a session
  only to a viewer who can see it. A refused write keeps what was typed
  (`app/web/views/_refused_write.py`, 142 LOC). Participant pages lose
  operator words. Every email names the deadline, the help contact and the
  zone. Archived sessions answer 404 to participants on every path.
- **Chips** (#2926 → #2960, #3074 → #3078). Cycle, on/off and fixed-switch
  chips, plus a status-colored on/off chip for Severity on the audit log and
  Validate. All of it went into `base.html`'s inline stylesheet.

**Unchanged this window:** the instrument model (no rules-language feature),
the assignment engine's rules, the audit envelope schema, the email pipeline
(nothing sends), Rehydrate (still gated off) and the dependency set. Of the
six migrations, two add columns, two rewrite legacy rows (`14db60023e88`,
`4cc450a87931`), one indexes and one adds a check constraint; none drops a
column.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`
(unchanged since 30 September, so every delta compares like with like).

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 315 (279 prior) | **170,039** | +10,507 (+6.6%) |
| `tests` | 515 (435 prior) | **169,364** | +20,265 (+13.6%) |
| `production` | 219 (207 prior) | **73,736** | +6,232 (+9.2%) |
| `templates` | 65 (62 prior) | **32,689** | +1,052 (+3.3%) |
| `tooling` | 15 | **11,911** | +868 (+7.9%) |
| `migrations` | 90 (84 prior) | **7,642** | +485 (+6.8%) |

**Tests now nearly equal docs**, 169,364 against 170,039. **Test-to-production
is 2.30**, from 2.21. My read: two things drove it. The browser tests nearly
tripled, from 45 tests in 11 files to **127 in 33** (+3,100 lines in
`tests/browser/`). And every register fix and plan rung brought its
regression test. Production grew faster than in any of the last three
windows, so the ratio's rise is the tests running ahead, not production
standing still.

**Tests: 6,233 passed, 4 skipped, 0 xfails** (was 5,331 / 1 / 0). They ran
at `3d8adb38` with `node` and Chromium present (`RRW_REQUIRE_BROWSER=1`), so
the inline-script parse and the browser tests ran. `ruff check .` is clean.
One skip is the opt-in CSS parity dump. The other three are the row-lock
tests in `tests/integration/test_owner_add_lock.py`, which need Postgres and
run in the `ci-postgres` job. Both CI tracks were green on #3081.

**Endpoints and schema: 192 route declarations over 90 migrations** (was
185 / 84). 189 are `@router.*` (117 POST, 70 GET, 1 PATCH, 1 DELETE) and 3
are `@app.get` in `app/main.py`. `EVENT_SCHEMAS` registers **155** event
types (was 152).

| LOC | File | Δ |
| --- | --- | --- |
| 1,624 | `app/services/csv_imports.py` | +367 |
| 1,409 | `app/services/responses/_core.py` | +13 |
| 1,362 | `app/services/validation.py` | +2 |
| 1,347 | `app/web/views/_instruments.py` | +80 |
| 1,275 | `app/services/assignments/_generate.py` | +6 |
| 1,269 | `app/web/routes_operator/_instruments.py` | +67 |
| 1,208 | `app/services/session_lifecycle.py` | +214 |
| 1,192 | `app/services/instruments/_instrument_crud.py` | +84 |
| 1,185 | `app/web/routes_operator/_operations.py` | +38 |
| 1,140 | `app/web/routes_operator/_shared.py` | +41 |

**The plateau broke at the top.** `csv_imports.py` grew 1,257 → 1,624 and is
now the largest production module by 215 lines. Quick Setup's incoming-set
checks (#2999), the problem kinds (#2997), the comma refusal (#2878) and
19U's gates (#2882, #2885) all landed in it. `session_lifecycle.py`
re-entered the top ten (994 → 1,208), with 19U's lock-and-re-read and the
participant audit's archived gates (#3068). Every other file in the top ten
moved fewer than 85 lines. Among templates, `operator/instruments_index.html`
fell to **6,968** (−199; dead tables and the Help table went in #2943).
`base.html` rose to **6,113** (+743): fifty PRs in the window touched it,
most of them for chips in its inline stylesheet.

**Where the growth landed:** production churn is **+13 files, −1**. That is
different from the prior window's +1, −1. The thirteen new modules total
2,123 LOC. Eight are views (`_accounts.py` 253, `_reviewer_self.py` 198,
`_participant_self.py` 190, `_sessions_table.py` 183, `_refused_write.py`
142, `_participant_status.py` 119, `_upload_problems.py` 109 and
`_participant_chrome.py` 42). The rest are five services (`account_listing.py`
300, `participant_info.py` 216, `scheduled_events/_fired.py` 174,
`unit_of_work.py` 108, `session_guard.py` 89). About a third of the +6,232
went into new seams and two thirds onto existing ones, led by
`csv_imports.py` and `session_lifecycle.py`. My read: the fourth seam is
doing its job. The participant and Accounts work put their shaping in
`app/web/views/` rather than in routes or templates.

**Package shape:** `app/services` holds 103 Python files (was 98).
`app/web` holds 76 (was 69), of which `app/web/views` is 30 (was 23) and
`app/web/routes_operator` is 22 (unchanged). `app/db/models` holds 21
(unchanged).

**Duplication and churn** (`python3 tools/code_metrics.py` at `3d8adb38`):

| | ≥10-line blocks | prior |
| --- | --- | --- |
| `app/` | 3,193 / 59,190 = **5.4%** | 5.9% |
| `tests/` | 14,680 / 136,280 = **10.8%** | 11.7% |

Churn is the share of Python lines deleted within 14 days of being written,
over all 3,070 merges on `main`. It is **66,184 of 100,916 (65.6%)**, against
a same-share baseline of 51.0%: a **ratio of 1.3×** (was 1.2×). That is
consistent with a window whose plans built, checked in a browser and
revised: the UX refinements reversed one of their own items within a day
(#2934 → #2939). `routes_operator/_instruments.py` joined the roster route
modules in the duplication list (23%). The roster route modules themselves
fell to **42% / 39% / 34% / 28%** (`_setup_reviewers.py`,
`_setup_reviewees.py`, `_setup_relationships.py`, `_setup_observers.py`).

## 3. Functional-spec compliance

Every row was checked against code at `3d8adb38` (a route registered, a
service function present and called, a test covering it) and cross-checked
against the bug sweep's six reads at the same commit. **Bold rows changed
this window.** A `⚠ drift` row names the bug-register finding that carries
it.

| Area | Spec | Status |
| --- | --- | --- |
| **Lifecycle (five states)** | `spec/lifecycle.md` | ✓ shipped. Every transition decides under `session_guard.lock_session` (#2881). ⚠ drift: reviewer writes are not under the lock (L3); scheduled events fire only from Session Home (L4); archive has no `can_archive` gate (L5) |
| Assignments engine | `spec/assignments.md` | ✓ shipped; rules unchanged. ⚠ drift: a boundary edit doesn't reconcile group copies (E2); Prepare re-includes self-reviews switched off (E3) |
| Validate page | `spec/validate_page.md` | ✓ shipped. 22 rules (unchanged); severity chips remembered (#3078) |
| Workflow card | `spec/workflow_card.md` | ✓ shipped. Unchanged |
| **Instruments** | `spec/instruments.md` | ✓ shipped. The card's Save is all or nothing (#2834); Band 3 as chips (#2936, #2937). ⚠ drift: a field edit doesn't un-validate or audit (S1); the card offers a Band 1 rule the engine rejects (E1) |
| Response-field branching | `spec/instruments.md`, `spec/reviewer-surface.md` | ✓ shipped. `MAX_BRANCH_DEPTH = 2`; ↰ / ⑂ semantics settled (#2934, #2939, #2941) |
| **Setup pages** | `spec/setup_pages.md` | ✓ shipped. Problem kinds on upload (#3006); the Observers row editor carries its cohort rule (#2989) |
| **Quick Setup** | `spec/quick_setup_card_spec.md` | ✓ shipped. All or nothing across files (#3000); Observers on Home (#3002) |
| Operations pages | `spec/operations_pages.md` | ✓ shipped. ⚠ drift: Invitations reads "sent" after Regenerate all (O2) |
| **Session owners / tags** | `spec/session_owners.md`, `spec/sessions_overview.md` | ✓ shipped. The Owners card's own Lock retired (#2920); the session tables sort alike (#3050 → #3052). ⚠ drift: lobby Select all ticks hidden rows (O1) |
| **Participant model** | `spec/participant_model.md` | ✓ shipped. Own-entry selections for all three types (#2979, #2986, #2992); archived sessions off limits (#3073) |
| **Visibility policy** | `spec/visibility_policy.md` | ✓ shipped. Reviewer-identity level (#2965); `ck_view_policy_cell` (#3053) |
| **Reviewer surface** | `spec/reviewer-surface.md` | ✓ shipped. A refused write keeps the typed answers (#3066). ⚠ drift: Save after Submit keeps `submitted_at` (R1, author's call) |
| **CSV contracts + round-trip** | `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` | ✓ shipped; round-trips byte-identical. ⚠ drift: the Settings import skips phase-1 shape checks on rules, Band 2 state, offsets and field keys (S2, L1, S3) |
| Extracts | `spec/extract_data.md` | ✓ shipped. ⚠ drift: a non-Latin-1 session code 500s every download (R2); `NaN` breaks number formatting (R3) |
| Audit | `spec/architecture.md` | ✓ shipped. `EVENT_SCHEMAS`, 155 types, strict in tests |
| **Permissions / identity** | `spec/permissions.md`, `spec/audience_and_identity_model.md` | ✓ shipped; all 192 routes' gates match the matrix (bug-sweep P read). Accounts as a table (#3030). ⚠ drift: demote can orphan a session (P1) |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped; render only. The send-on-submit checkbox became a chip (#2946) |
| Email dispatch | `spec/email_infra_options.md` | ⛔ blocked. Nothing in `app/` calls a transport. Segment 14B needs institutional Azure |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off. `rehydrate_enabled` defaults to `False` |
| Blob storage | `guide/blob_storage_candidates.md` | ⏸ not built |
| Base path (`/reviewrobin`) | `docs/cordware_rrw_integration_spec_v0.2.md` | ⏸ on hold, speculative (author, 2026-10-16). Segment 21, outline only, to be reworked against the v0.2 spec |
| Operator theming | `spec/visual_style_rrw.md` | ⏸ planned. `guide/deferred_consolidated.md` Part A |

**Doc drift: two registers closed, no corpus sweep since 2026-10-07.** The
2026-10-05 register (156 findings) and the 2026-10-07 register were each
worked to nothing open by 2026-10-09 (#2917). No corpus sweep ran in the
second half of the window. The spec count held at 35 files, and
`spec/rrw_functional_spec.md` fell 2,596 → 2,575 lines. The 5 October
snapshot proposed shrinking it to what only it says (move 3), and that did
not happen.

## 4. Strengths

- **The gates held under an adversarial read.** The bug sweep's
  permissions read walked all 192 routes through their dependencies. It sent
  another session's ids to all 36 child-id routes, and every one answered
  404. It also fuzzed the reviewer's Save with foreign ids, keys, `NaN` and
  `1e309`, and crawled 18 operator pages for XSS. It found nothing that lets
  a stranger in. My read: one gate dependency per audience
  (`require_session_operator`, `require_reviewee_with_current_grant`,
  `require_observer_in_session`), and a matrix in the spec that a test
  checks, are why. The six defects it did find are at the edges: demote,
  clone, claim parsing.
- **An invariant moved from code to the schema.** `ck_view_policy_cell`
  (#3053) makes the database refuse a visibility cell the per-cell rule
  forbids. A whole diagnostic card that looked for such cells was deleted
  with it, along with its view module. That is the retire-rather-than-
  mechanize rule (`constitution.md`) applied to code.
- **The new code took the fourth seam.** Of the thirteen new production
  modules, eight are in `app/web/views/` (§2). The participant audit's
  fixes (P3's refused write, M6's role-aware statuses, the chrome) are view
  adapters rather than logic in templates. `routes_operator/` gained no
  module, though Accounts, participant info and the session tables all
  added routes.
- **What the author checked by hand, CI now checks.** 127 Chromium tests
  in 33 files (was 45 in 11), enough that the post-Azure checklist's items
  5 and 6 could be struck (in #3082). A 45-step browser checklist
  (#3013 → #3023) ran against committed seed files in
  `guide/browser_check_files/`.
- **Small plans closed inside the window.** Eight plan documents opened,
  shipped and archived between 2026-10-09 and 2026-10-16. Each one went
  scaffold first, and none needed a revert.

## 5. Weaknesses

- **Write paths that trust what they store.** Eight of the bug register's 46
  findings are one family. In four, a value is written unchecked and fails
  only when something later reads it: a page answers 500, or a field can
  never be answered, until someone replaces the value. They are S2, L1, S3
  and E1 (the Settings import storing rules, Band 2 state, offsets and field
  keys; the Band 1 card storing a rule the engine rejects). In a fifth, S7,
  a NUL byte passes the import's checks and Postgres refuses it with a 500.
  Three more change data without the bookkeeping the spec requires (S1, E2,
  S6). The read side's `TypeAdapter(Rule)` is the check.
  It is not run on write. My read: the 19U guard made every *state* check
  happen at write time, and *shape* checks have no equivalent seam. No plan
  yet; the register is new.
- **Production overran the projection by 2,672 lines** with only the first
  of its named items done (§7). The window's features came from plans opened
  inside it. That is legitimate, but it means the §7 projection was not
  forecasting the work that arrived. Its floor is a floor for the *named*
  scope only.
- **`csv_imports.py` is 1,624 lines and growing.** It grew 367 lines in one
  window, as the place every import rule lands, and it owns the phase-1
  checks that S2, S3 and L1 say are missing. No plan.
- **`base.html` is 6,113 lines.** It grows with every visual primitive
  (+743, fifty PRs), by the design `CLAUDE.md` states: one inline stylesheet,
  no asset pipeline. Extraction is post-Azure checklist item 4, gated on
  measuring the cost over the institutional network. Planned, not soon.
- **Nothing sends email, and nothing is deployed.** Unchanged. 14B and 20
  still wait on the institutional deployment. A shared-host direction under
  `cordware.nus.edu.sg` was proposed in the window and outlined as
  Segment 21; the author has put it on hold as speculative, so it is neither
  a dependency nor a plan here.

## 6. Bugs and regressions

**Known open bugs at `3d8adb38`: 8 high, 16 medium, 22 low**, all in
`guide/findings_2026-10-16_bugs.md` and none yet fixed. Most were reproduced by
a scratch test against the suite; the register marks which. The high ones:

- a Save after Submit releases an edited answer as submitted (R1, the
  author's call: the spec says Save never touches `submitted_at`);
- a non-Latin-1 session code makes every CSV download 500 (R2);
- a Settings import with an out-of-range offset makes Session Home 500 on
  every load (L1);
- the lobby's and Archive's Select all tick rows the filter hides, so bulk
  Delete and Purge act on unseen sessions (O1);
- the instrument card's field edit neither un-validates nor audits (S1);
- a Settings import's malformed rules or Band 2 state make three pages 500
  (S2);
- the Band 1 card offers, and stores, a rule the engine rejects (E1);
- a group-boundary change leaves one group holding different answers (E2).

Also checked: no open GitHub issues; one open pull request (#3082, prose);
0 xfails; four skips, all named in §2. The register's §4 lists what the six
reads tried and found sound.

Worth remembering from the window, each now with a guard:

- **Removing a user deleted every session they had created** (#2867), even
  ones another operator now owned, through an ORM `delete-orphan` cascade.
  Found by Codex on the sweep record's PR. Remove now refuses any user with
  history.
- **An owner add and a revoke could race** to leave a non-operator owning a
  session (#3039). They now serialize on the user row, with a Postgres-only
  test. P1 in the new register is the same invariant reached through demote.
- **Scheduled-event observers decided on a stale read** (#2877, Bc3), and an
  auto-send entry could refire after an offset edit shifted it (#2874, Bc1).

## 7. Estimated size upon completion

**Current: production 73,736, templates 32,689** at `3d8adb38`.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| The 2026-10-16 bug register | +400–900 | +50–150 | rulings on R1, R6, L4, L8, S4, P2 |
| Segment 14B, email dispatch, reminders, invitations | +900–1,400 | +200–400 | the institutional Azure deployment |
| Segment 20, operator polish and documentation | +200–500 | +300–600 | the institutional Azure deployment concluded |
| Blob storage (18Q) seam and first consumers | +400–700 | +50–150 | an institutional storage account |
| Operator theming (stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |
| **Projected floor** | **75,816–77,596** | **33,409–34,239** | |

This excludes anything past v1 and every entry in
`guide/deferred_consolidated.md` Parts A and C, and Segment 21, which is on
hold as speculative.

**Reconciliation: production passed the prior ceiling; templates stayed
inside the range.** The 5 October snapshot projected **69,484–71,064**
production and **32,357–33,187** templates. Production is **73,736**, above
the ceiling by 2,672. Templates are **32,689**, inside the range. Of the
named items, only the first (the 2026-10-05 register's defects) shipped. The
rest of the growth was **scope discovered**: eight plans opened inside the
window (Accounts, participant info, Quick Setup update, the session guard
and the participant audit among them), none of which the projection named.
The new first row is this snapshot's register. The other five carry forward
unchanged.

## 8. Bottom line

Review Robin Web spent eleven days building features in small plans, after
closing two findings registers. The session-state guard, Accounts at scale,
participant self-information and all-or-nothing Quick Setup each shipped
scaffold first with browser tests, and the suite reached 6,233 tests. A bug
sweep at this commit found the gates sound. It also found **eight high
defects**, most where a write path stores a value nothing has checked. The
live thread is unchanged: **nothing sends email, and nothing is deployed**.

**Recommended next moves, at most three:**

1. **Fix the register's high defects, starting with the write paths.** S2,
   L1 and E1 have one fix shape: run the reader's check on write, in phase 1
   of the import and on the card's Save. Doing them together gives that check
   a seam rather than three copies. Then O1, because it is the only finding
   where one click acts on data the operator cannot see. R1 needs the
   author's ruling first. These come first because a pilot operator reaches
   each of them through ordinary use.
2. **Rule the register's six author rows in one sitting** (R1, R6, L4, L8,
   S4, P2). R1 blocks the reviewer-surface fix and P2 is the only permissions
   question; the rest are small. The 2026-10-05 register's one-sitting ruling
   (#2852) is why its last row shipped the next day (#2865).
3. **Schedule the next corpus sweep from `close_check --stale`, and let
   it carry the functional-spec trim.** No sweep has read the specs since
   2026-10-07, and this window changed the participant model, visibility and
   permissions. The prior snapshot's move 3, shrinking
   `spec/rrw_functional_spec.md` to what only it says, did not happen. It
   belongs in that sweep rather than as a campaign of its own.

**Settling the 5 October proposals.** Move 1, *fix the register's defects,
the privilege bug first*: **shipped** (F1 in #2828; the register worked
through #2865 and archived 2026-10-07). Move 2, *rule the open decisions in one sitting*: **shipped**
(#2852, 2026-10-06). Move 3, *shrink the functional spec*: **not done**. It
fell 21 lines and is carried into move 3 above.

---

## 9. Proposed file splits — watchlist

**Still no split queued; one file crossed its tripwire.**

- **`app/services/csv_imports.py` (1,624 LOC, +367).** New to the top of the
  list. Three seams are visible: the per-kind row parsers, the
  incoming-set checks Quick Setup now calls as pure functions (#2999), and
  the apply step. The checks are the natural first cut, as `_incoming.py`.
  That is also where the shape checks S3 and S7 ask for would live. Cut it
  with the register's write-path fixes, not as a separate pass.
- **`app/web/templates/operator/instruments_index.html` (6,968 LOC, −199).**
  Shrinking without an extraction; the trigger (a pilot-driven builder
  change) has not arrived. E1 and E4 are both in its Band 1 script, and
  fixing them is a candidate carrier.
- **`app/services/session_lifecycle.py` (1,208 LOC, +214).** Back on the
  list after leaving it. The archived-session gates and 19U's
  lock-and-re-read both landed here. Watch past ~1,300.
- **`app/services/responses/_core.py` (1,409 LOC, +13).** Flat. R1, R3 and
  R4 all land in it; the number canonicalization R4 asks for would leave
  as `_numbers.py` if it grows.
- **`app/services/validation.py` (1,362, +2)**, **`assignments/_generate.py`
  (1,275, +6)** and **`instruments/_instrument_crud.py` (1,192, +84)** are
  carried. None moved toward a tripwire. E2's reconcile-on-boundary fix
  lands in `_instrument_crud.py`.

`app/web/routes_operator/_instruments.py` (1,269, +67) and
`app/web/views/_instruments.py` (1,347, +80) are watched but not listed.
Both grew by the chips, not by a new concern.
