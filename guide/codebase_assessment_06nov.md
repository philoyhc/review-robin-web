# Codebase assessment — 2026-11-06

**As of** segment 14F's rungs 1 → 3d and the author's refinements after
them, with 14F open (rung 5 and its close to come) and its follow-ups
being collected. **Email sends for real**: per-row Send and Send reminder
go from the operator's own mailbox through delegated Graph, live on Azure
since 2026-11-05 (Cordware #181, RRW `3ab0bad8`), where the author's
browser and email tests passed. Bulk sending is built but off
(`RRW_BULK_SEND`), and scheduled email waits on 14G.

**Since the prior snapshot** (`guide/archive/codebase_assessment_03nov.md`,
`cc364ed0`), eight arcs shipped, 2026-11-04 → 11-06 (UTC):

- **The 3 November register, worked** (#3568 → #3573): M1's recheck made
  editable-only and invalidating, the packages' small fixes, the spec
  catch-up; archived with every row done, closed or ruled.
- **14E — a clock for timed actions** (#3577 → #3583). End closes the
  session; RRW's lifespan starts a clock whose pass fires activation,
  release and deadline events; auto-send off until mail can go on the
  clock (`RRW_SCHEDULED_SEND`).
- **22C → 22F — the language-level gates** (#3584 → #3615). pyright gates
  CI, then strict mode package by package, tests included, with no
  `type: ignore` left or honoured; SQLAlchemy 2.1; ruff's import, syntax,
  bugbear and simplify rules.
- **22G — System Status**, a third Admin tab (#3616 → #3622): the clock's
  own record, what is due next, sending, and this instance.
- **22H and 22I — format and speed** (#3621 → #3641). `ruff format` across
  the repository with E501 on and a format gate; CI's tests in three
  shards and Postgres's in three; the targeted test loop in `CLAUDE.md`.
- **14C Item 2 and 14F rungs 1 → 3d — email by hand** (#3642 → #3654).
  The host's Graph mailer and the dispatcher; Send a test to me; the
  Email settings toggles (all off by default); per-row Send and Remind
  sending, bulk off; the Share the session link card; the participation
  report (`reviewers.last_opened_at`, the Timestamps chip).
- **The author's refinements** (#3655 → #3657): the Invitations info card
  and the link card side by side and one height, headed info cards on both
  Operations pages, Extract data's cards in row-aligned pairs, and the
  scheduled-email fields muted under "Scheduled email under development."
- **Small fixes**: Band 1 pills on an untagged roster (#3647); the clock
  counting a busy session as busy (#3631); the recheck's "Stop and save"
  (#3575).

**Numbers taken at `c912ae53`**, `main` at #3657, before this snapshot's
own documents. Window `cc364ed0..c912ae53`: **2 merge commits, 94
non-merge**; `main`'s first-parent line holds 91 commits: 89
squash-merged PRs and the 2 merges, PRs #3567 → #3657, 2026-11-03 23:45 →
2026-11-06 03:09 UTC.

**This document stands alone** and archives
`guide/archive/codebase_assessment_03nov.md`. Authority lives elsewhere:
the contract is `spec/` (indexed by `spec/README.md`) plus
`cordware/spec/`, `residentialapps/spec/` and `utilityapps/spec/`;
`guide/todo_master.md` holds the open work. Three reads ran at the pinned
tree (`c5d03d49`, #3657's head before its squash, the same tree), each by
an agent with no part in the window's builds:
- a spec-vs-code audit (§3);
- a defect read of the window's `app/`, `cordware/` and `alembic/`
  changes, with scratch tests (§6);
- a read of the three non-RRW packages, with their suites and a route
  fuzz (§3, §6).

Nothing was edited by them. Every defect, drift and gap they reported is a
row of `guide/findings_2026-11-06_assessment.md`, the checklist the fixes
strike off.

**Development context:** a single author, with AI agents building. The
window ran at about 40 PRs a day, almost all small; every code slice had
a Codex review before merge, which found a real defect in most of 14F's
code PRs (§4).

---

## 1. What's in the box

An operator creates a review session and loads its rosters, each address
bound to a directory account where the institution's directory knows it.
Instruments define what reviewers answer; rules generate assignments;
Validate checks the whole and Activate opens it. Reviewers answer through
their own surface, reviewees and observers read what the visibility
policy grants, and the operator extracts the responses. A FastAPI + Jinja
monolith over SQLAlchemy, mounted at `/reviewrobin` by the Cordware host
beside Residential Operations, Support Logs and Cordware Utilities.

**New since the prior snapshot:**

- **Sending** (14F). `cordware/graph.py` gains `Mailer`, `GraphMailer`
  (`POST /me/sendMail`; no retry on 5xx or the network, one wait on a
  429), `FakeMailer` and `mailer_for`; `app/services/email_dispatch.py`
  (195 LOC) claims a `queued` row, sends it and stamps `sent` or
  `failed`; `email_test_send.py` (118) sends the composer's draft to the
  operator. Per-row Send and Remind dispatch at once; a Regenerate fails
  the rows still queued with the old link.
- **The clock** (14E). `scheduled_events/_clock.py` (283) runs a pass on
  RRW's lifespan under an advisory lock; `session_lifecycle.review_end`
  and `is_ongoing` make End the close; Validate's 28th rule,
  `session.end_passed`.
- **Operator email choices** (14C Item 2): three toggles in
  `users.preferences` (Sent Items, a copy to me, Reply-to the Help
  contact), read by `email_dispatch.send_options_for`.
- **Sharing instead of bulk**: the Share the session link card on
  Invitations (the stable `/me/sessions/{id}` link and Copy link); the
  Workflow card's bulk buttons disabled with a line pointing to it.
- **The participation report**: `reviewers.last_opened_at` (migration
  `a3d7f1c9e2b4`), stamped and audited (`reviewer.opened`) at most once
  per 30 minutes of a reviewer's use; the Timestamps chip adds
  LastOpened, LastSaved and LastSubmitted to Reviewer response metadata.
- **System Status** (22G): `services/system_status.py` (178) and its view
  (126) behind `/sys-admin/system`.
- **Typed throughout** (22C → 22F): `app/json_shapes.py` narrows JSON
  columns; `app/db/schema_head.py` names the migration head for System
  Status.

**Unchanged this window:** the reviewer surface and its forms, results and
collation, assignments generation, rosters and the directory seam,
Rehydrate, and Residential and Utilities beyond typing and formatting.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`
(unchanged); the measurement reproduces the 3 November sidecar exactly at
`cc364ed0` (1,610 files, no difference).

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `tests` | 636 (623 prior) | **190,060** | −3,481 (−1.8%) |
| `docs` | 355 (345 prior) | **183,450** | +3,056 (+1.7%) |
| `production` | 253 (245 prior) | **83,033** | +73 (+0.1%) |
| `templates` | 74 (73 prior) | **35,808** | +504 (+1.4%) |
| `residentialapps` | 151 | **23,771** | +3,289 (+16.1%) |
| `tooling` | 16 | **13,057** | +592 (+4.7%) |
| `migrations` | 102 (101 prior) | **8,287** | +47 (+0.6%) |
| `cordware` | 25 (24 prior) | **5,827** | +573 (+10.9%) |
| `utilityapps` | 32 | **3,307** | +235 (+7.7%) |

**Production is flat because two movements cancel.** By PR family over
the window's first-parent commits: 14E, 14C and 14F added **+1,614** net,
22G and the small fixes **+527**, and the lint, type and format work
(22C → 22H) took **−2,068**, of which the formatter's one pass (#3623)
was −2,953 in production alone. The same pass explains `tests` falling
and most of `residentialapps` and `utilityapps` rising (the formatter
splits long calls one argument per line). `cordware` grew by
`graph.py`'s mailer (408 → 630). **Test-to-production is 2.29** (was
2.33).

**Tests: 8,451 passed, 12 skipped, 0 xfails** (was 8,265 / 11 / 0), at
the pinned tree with `node` and Chromium present; `ruff check .`,
`ruff format --check .` and `pyright` are clean. The new skip is 14E's
Postgres-only advisory-lock test; the others are the CSS parity dump and
the Postgres-only lock and index tests, all run in `ci-postgres`. The
non-RRW packages alone: **704 passed, 0 skipped** (`cordware` 222,
Residential 354 with its browser files run, Utilities 128). Browser
tests: **236 in 53 files** (was 232 in 53).

**Test runtime** (new standard item, author 2026-11-06):

| Where | Measure | Time |
| --- | --- | --- |
| This container, 4 cores, `pytest -n auto` | full suite, wall | **246 s** (8,451 tests) |
| CI on `main` at `c912ae53`, workflow `CI` | wall, three shards in parallel | **2m34** |
| … `test (unit)` | tests; plus pyright 31 s | 43 s |
| … `test (integration)` | tests | **1m58** |
| … `test (browser)` | tests | 1m20 |
| CI, workflow `CI - Postgres` | wall, three shards | **3m46** |
| … `postgres (unit)` | migrations both ways, then tests | 5 s + 51 s |
| … `postgres (integration-a)`, `test_[a-q]*.py` | tests | 1m38 |
| … `postgres (integration-b)`, `test_[r-z]*.py` | tests | **2m54** |

The suite has no long pole: its slowest test takes 6.0 s
(`tests/browser/test_accounts_toolbar.py::test_the_role_dropdown_and_the_pager`)
and only two exceed 4 s, so local time scales with the count. The local
figure compares with `CLAUDE.md`'s 287 s for 8,381 tests, taken after 22H
on 2026-11-05: within run-to-run variance on a shared container, so a
baseline, not a gain. **The Postgres shards are
uneven**: integration-b takes 1.8 times integration-a and is the slowest
job in CI (N8). One outlier: #3657's PR run spent 10m18 in `test
(browser)` against 1m58 on `main` for the same tree; not reproduced.

**Endpoints and schema: 205 routes in RRW over 102 migrations** (was 202
/ 101): 202 `@router.*` (126 POST, 74 GET, 1 PATCH, 1 DELETE) and 3
`@app.get`. Added: `/settings/email-preference`,
`/sessions/{id}/setup-invite/send-test`, `/sys-admin/system`.
`EVENT_SCHEMAS` registers **173** event types (was 165); Validate runs
**28** rules (`session.end_passed`).

| LOC | File | Δ |
| --- | --- | --- |
| 1,512 | `app/web/routes_operator/_quick_setup.py` | +7 |
| 1,344 | `app/services/session_lifecycle.py` | +101 |
| 1,327 | `app/services/instruments/_instrument_crud.py` | −54 |
| 1,306 | `app/services/assignments/_generate.py` | −56 |
| 1,294 | `app/web/routes_operator/_instruments.py` | −40 |
| 1,267 | `app/web/views/_instruments.py` | −89 |
| 1,219 | `app/web/routes_operator/_operations.py` | +23 |
| 1,213 | `app/web/routes_operator/_setup_relationships.py` | +37 |
| 1,190 | `app/services/users.py` | −51 |
| 1,171 | `app/services/audit.py` | −56 |

A plateau, as on 3 November; the formatter moved each file a few dozen
lines either way. `session_lifecycle.py` grew by 14E's End. Templates:
`operator/instruments_index.html` 7,219 (+15), `base.html` 6,846 (+57).
Production churn is **+8 files, −0**: `email_dispatch.py`,
`email_test_send.py`, `scheduled_events/_clock.py`, `system_status.py`,
`views/_email_composer.py`, `views/_system_status.py`, `json_shapes.py`
and `db/schema_head.py`.

**Duplication** (`python3 tools/code_metrics.py`, blocks of 10+ lines):
`app/` **4.5%** (was 4.8%), `tests/` **9.9%** (unchanged). The Setup
route modules rose (`_setup_relationships.py` 27% → 32%,
`_setup_reviewers.py` 26% → 31%), but only formatting and typing touched
them: the formatter's one-parameter-per-line signatures make their shared
parameter lists count as 10-line blocks. A measurement shift, not new
copying. **Churn** is **61.8% against a 47.5% baseline, ratio 1.3×**
(unchanged), over all 3,457 merges. *Annotated 2026-11-06:* the walk reads
merge commits only, so this window's 89 squash-merged PRs (of 91) are
not in the figure, nor the 188 squash-merged since #3150 (N9). With
them counted (#3662), the walk reads **1.2×** at `aab086fe` (50.3%
against 40.8%, over 3,648 PRs).

## 3. Functional-spec compliance

Checked against code at the pinned tree by the spec-vs-code audit and,
for the packages, the package read. **Bold rows changed this window.**
Every drift the 3 November table named is closed (#3568 → #3573). New
drifts are below the table; ids are the register's.

| Area | Spec | Status |
| --- | --- | --- |
| **Lifecycle** | `spec/lifecycle.md` | ✓ shipped. End closes the session (14E). ⚠ End's floor claim with scheduled send off (D7); the already-shut close writes no `deadline_reached` (L4) |
| Assignments engine | `spec/assignments.md` | ✓ shipped. No change |
| **Validate page** | `spec/validate_page.md` | ✓ shipped. **28 rules**: `session.end_passed`. ⚠ the schedule form accepts Start == End, which it refuses (L3) |
| **Workflow card** | `spec/workflow_card.md` | ✓ shipped. ⚠ the bulk-off state and line are unspecified (D3); State 5's copy (D2) |
| Instruments | `spec/instruments.md` | ✓ shipped. Band 1 pills on an untagged roster |
| Setup pages | `spec/setup_pages.md` | ✓ shipped. No change |
| **Operations pages** | `spec/operations_pages.md` | ✓ shipped. The pair and the headings recorded (#3655). ⚠ still requires the "no email" note and names bulk the one pre-activation send (D1, D3) |
| **Sys Admin** | `spec/operator_ui_concept.md` | ✓ shipped. System Status. ⚠ the outbox intro (D1); "behind" for a database ahead (N6) |
| Participant model / identity | `spec/participant_model.md`, `spec/audience_and_identity_model.md` | ✓ shipped. The session link answers a stranger 404 |
| **Visibility policy** | `spec/visibility_policy.md` | ✓ shipped (`is_ongoing`). ⚠ §2.2 contradicts §3 (D6) |
| Reviewer surface | `spec/reviewer-surface.md` | ✓ shipped. 14E's end wording matches |
| CSV contracts | `spec/csv_contracts.md` | ✓ shipped. No change |
| **Extracts** | `spec/extract_data.md` | ✓ shipped. ⚠ the Timestamps chip undocumented (D5) |
| **Audit** | `spec/architecture.md` | ✓ shipped. **173 types**, `email.*` and `reviewer.opened` included. ⚠ "email_outbox: none does yet" (D1) |
| **Settings inventory** | `spec/settings_inventory.md` | ✓ shipped. ⚠ `RRW_BULK_SEND`, the email preferences, `last_opened_at`, `?email=` missing (D4) |
| **Email template editor** | `spec/email_template_editor.md` | ✓ shipped; Send a test to me. ⚠ §7 says nothing transmits (D1) |
| **Email dispatch** | `spec/email_infra_options.md` | ✓ **sending, per row** (was ⛔). ⚠ delegated Graph "out of scope", the transport a "stub" (D1); Reply-To shipped differently (D8). ⚠ bulk with the flag on only queues (L2) |
| **Cordware host and identity** | `cordware/spec/host.md`, `cordware/spec/identity.md` | ✓ shipped, deployed. ⚠ Graph "directory lookups only" (D1) |
| UI elements | `spec/ui_elements.md` | ✓ shipped. ⚠ two layout modifiers undocumented (D9) |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off. No change |
| Blob storage, operator theming | `guide/blob_storage_candidates.md`, `spec/visual_style_rrw.md` | ⏸ not built |
| Residential, Utilities | `residentialapps/spec/`, `utilityapps/spec/` | Residential ⏸ on sample data, gated; Utilities ✓ deployed. Both specs match |
| Interoperability | `cordware/docs/` (proposed) | ⏸ parked (2026-11-04) |

**Most of the drift is one cause: 14F is open, and its spec pass comes at
its close.** Its `Doc impact` names `email_infra_options`,
`email_template_editor`, `operations_pages`, `settings_inventory`,
`extract_data` and `identity.md`; it does not name
`rrw_functional_spec.md` §§9.13 and 11.6, `architecture.md`,
`operator_ui_concept.md` or `workflow_card.md`, which say the same false
thing (D1, D3). The user-facing copy is the more pressing half (D2):
the Guide still tells operators email is not implemented. The rest are
small: a self-contradiction (D6), two qualifiers (D7, D11), two
undocumented modifiers (D9), and `CONTRIBUTING.md` missing the format gate
(D10).

**Spec corpus:** 35 files in `spec/` (unchanged), plus 2 in
`cordware/spec/`, 4 in `residentialapps/spec/` and 2 in
`utilityapps/spec/`.

## 4. Strengths

- **The gates went in without moving behavior.** pyright strict across
  every package and test tree, no `type: ignore` honoured, ruff's wider
  rules and a formatter pass that rewrote thousands of lines: the defect
  read compared 143 changed files' syntax trees with docstrings,
  annotations and imports stripped, and the package read every changed
  package module, and neither found a behavior change. The suite stayed
  green across every rung.
- **The first real sends are narrow and auditable.** One claim flips a
  row `queued` → `sending` in a conditional update, so a row sends once;
  every outcome writes `email.sent` or `email.send_failed`; the bearer
  token never reaches a log, an error message or a redirect (the package
  read checked each path); a send fails closed with "reload the page"
  when the token is missing. The author's browser and email tests on
  Azure passed.
- **Review caught what tests did not, before merge.** Codex's findings on
  14F were real defects four times (Cc dropped, a test send losing its
  draft, a regenerate racing a queued send, an unaudited stamp) and once
  a documented cadence the code did not keep. Each was fixed with a test before merge.
- **CI is fast and split.** `CI` finishes in 2m34 and `CI - Postgres` in
  3m46 on `main`, against a 246 s local run; the prose and residential
  lanes run less.

## 5. Weaknesses

- **The send path's bookkeeping runs ahead of the send** (§6, M1). The
  invitation is stamped `sent` before the mail goes; a refused send
  leaves a row that says sent, has no Send, and moves the stepper on. It
  is live on Azure, where the first real failure will show it.
- **The contract and the copy lag the code by a segment.** Twelve
  drifts, most of them 14F's own close, unfinished; but four spec files
  sit outside its `Doc impact`, and operators can read in the Guide that
  email is not implemented while the button beside it sends.
- **"Before activation" has no answer.** Bulk is off, per-row Send waits
  for activation, and the Workflow card's State 5 tells operators to send
  ahead of activation. 14F's follow-up 1, `RRW_BULK_SEND`'s record-only
  behavior (L2) and the stale specs (D3) are one question, still open.
- **The four Setup route modules still repeat themselves**, now measured
  higher by the formatter (§2). No plan; carried.
- **Browser behavior stays the author's to check**, and
  `guide/things_to_check_in_browser.md` is the record.

## 6. Bugs and regressions

**At the pinned tree: one medium, four low, none high**, plus twelve spec
drifts (§3) and nine noted gaps. Each is a row of
`guide/findings_2026-11-06_assessment.md`; CONFIRMED means reproduced by a
scratch test, by trace means read through without a test.

- **M1 (medium, CONFIRMED).** A failed per-row Send or Remind still
  reads as sent: `send_invitation` stamps and commits before the
  dispatch, so a Graph refusal leaves `sent`, `sent_at`, the counters and
  the stepper as if it went, and the row offers no Send.
- **L1 (low, CONFIRMED).** A double-submitted Send mints a token per POST
  and mails both; the first link is dead.
- **L2 (low, CONFIRMED by trace).** With `RRW_BULK_SEND=true`, Send all
  and Remind incomplete stamp `sent` and queue rows nothing sends. Ships
  off.
- **L3 (low, by trace).** The schedule form accepts Start == End, which
  Validate then refuses, so such a session never activates.
- **L4 (low, by trace).** End's close on already-shut instruments writes
  no `session.deadline_reached`, which the specs read as written.

Notes, not defects (N1–N9): no test that the mailer's failure log omits
the token, nor of a POST redirect; `FakeMailer` logs addresses locally; a
network failure after Graph accepted reads `failed`; a 429 can hold a
worker about 70 s; five suspicions the defect read could not confirm;
System Status's "behind"; two spellings of `context.deadline`; the uneven
Postgres shards; and, found after the reads, the repository's churn and
pace measurements reading merge commits only, blind to every PR since the
switch to squash merges (N9, added 2026-11-06).

**Caught and fixed in the window, worth remembering:** a regenerate
between a queued send and its claim mailing a dead link (Codex, #3651);
an unaudited reviewer stamp (Codex, #3654); a test send discarding the
operator's unsaved draft (Codex, #3648); Cc silently dropped (Codex,
#3646); a Band 1 rule that could not be set on an untagged roster
(#3647); the 3 November M1 (#3568).

**What was checked to say the rest is sound:** the defect read's list
(the dispatcher's claim and its events; both regenerate paths failing
queued rows; `mark_opened`'s migration, `updated_at` and audit; the
Timestamps zone and `max()` typing in CSV and zip; Send a test to me's
overlay; the email preferences; 14E's `review_end`, `is_ongoing`,
`observe_deadline` and the visibility windows; the clock's advisory lock,
per-session rollback and `fired_by`; the recheck's server-side answers;
System Status's sys-admin gate; the session link's 404 to a stranger;
the typing refactors), and the package read's (`graph.py` in full: token
handling, redirects refused on GET and POST, error mapping,
`Retry-After` edge cases; the packages' changed modules by syntax tree;
a ~25,000-request fuzz of 72 routes under six identities with no 5xx, no
leak and no route open to the wrong role).

## 7. Estimated size upon completion

**Current: production 83,033, templates 35,808, `cordware` 5,827** at
`c912ae53`. Estimates are my judgment, from the plans and the nearest
shipped analogue.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| This register's defects (M1, L1–L4) | +40–120 | +0–10 | nothing |
| 14F rung 5, its follow-ups and close | +150–350 | +40–120 | nothing |
| 14G, scheduled and bulk email, paced | +300–600 | +20–60 | an application mail permission |
| The Setup routes' shared handler (§9) | −200 – −400 | 0 | a plan |
| Blob storage (18Q) | +400–700 | +50–150 | a storage account |
| Operator theming (stretch) | +150–300 | +100–200 | nothing |
| **Projected floor** | **83,673–84,903** | **36,018–36,348** | |

Excluded: Residential's wiring and RA Lifecycle (their own areas), the
interoperability work, magic links, and everything in
`guide/deferred_consolidated.md`.

**Reconciliation.** 3 November projected production **84,050–85,830**;
it is **83,033**, below the floor, and for a reason the method does not
model: 22C → 22H removed 2,068 lines without removing behavior. Without
them the window grew **+2,141**, inside the projection's +1,090 →
+2,870, and this time by the named route: 14E, 14C Item 2 and most of
14F shipped, 22C landed as a gate. Templates projected
**35,674–36,144**; **35,808**, inside. `cordware`'s code grew by the
mailer, as 14F's line implied.

## 8. Bottom line

In two days and 91 PRs, the 3 November register was struck, the
repository gained a type gate and a formatter with no behavior change,
the clock started, and **email sends**: from the operator's own mailbox,
one reviewer at a time, tested by the author on Azure. The defect read
found **one medium, none high**, and it is on that newest surface: a
refused send is recorded as sent.

**Recommended next moves, at most three:**

1. **Fix M1, with L1, before the next live send fails.** Stamp an
   invitation or reminder only when its dispatch reports `sent`, and make
   a second Send of a no-longer-pending invitation a refusal or a Remind,
   under the session lock. Both sit in `invitations.py` and
   `_operations.py`; it is on Azure now.
2. **Finish 14F's close as a contract catch-up.** Add
   `rrw_functional_spec.md`, `architecture.md`,
   `operator_ui_concept.md` and `workflow_card.md` to its `Doc impact`,
   fix the copy D2 lists first (the Guide tells operators email does not
   work), and close the register's D rows with it.
3. **Rule once on sending before activation.** 14F's follow-up 1 (per-row
   Send in `validated`), L2 (`RRW_BULK_SEND` on records without sending)
   and D3 (the specs and State 5) are one decision; take it before rung 5
   builds the due prompts on top.

**Settling the 3 November proposals.**
- Move 1, *fix M1 and L1*: **shipped** (#3568; L1 closed as not
  reproduced).
- Move 2, *build 14F*: **shipped through rung 3d** (#3645 → #3654), live
  on Azure; rung 5 and the close remain.
- Move 3, *plan the Setup routes' shared handler*: **not started**;
  carried in §9.

---

## 9. Proposed file splits — watchlist

**Watched now:**
- **`app/web/routes_operator/_quick_setup.py` (1,512, +7)**, still the
  largest file in `app/`. Cohesive; a split candidate only if Quick Setup
  grows another mode.
- **`app/services/session_lifecycle.py` (1,344, +101)**, grown by 14E's
  End and the clock's entry points. Watch if 14G adds sending to it; the
  clock's own module (`scheduled_events/_clock.py`) is the better home
  for anything timed.
- **The four Setup route modules**: not size but duplication (§2, §5).
  The seam is Observers' import route onto `roster_import._handle_import`,
  which it mirrors.
- **`app/web/templates/operator/instruments_index.html` (7,219)** and
  **`base.html` (6,846)**, carried. Nothing forces the stylesheet out.
