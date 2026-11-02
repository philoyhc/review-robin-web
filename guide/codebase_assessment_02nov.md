# Codebase assessment — 2026-11-02

**As of** the close of segment 20D (shared header chrome), with three new
email and scheduling plans (14C, 14E, 14F) and a type-checker plan (22C)
queued and none in build. The 22 October snapshot ended with "nothing
sends email, and nothing is deployed". Half of that changed: the Cordware
host has served Review Robin and Cordware Utilities on the institutional
Azure tenant since 2026-10-31, and Graph calls from application code are
proven there (#3423). Nothing sends email yet. Segment 19Z (append to a
roster) is still open, at its spec pass.

**Since the prior snapshot** (`guide/archive/codebase_assessment_22oct.md`,
`00501f2e`), six arcs shipped:

- **Both 2026-10-22 registers worked** (PRs #3227 → #3250, 2026-10-22 →
  2026-10-24). The bug register's 19 rows and the corpus register's 59
  findings were closed, including the functional-spec trim three snapshots
  had proposed (#3247).
- **Deployment out of this repository** (#3251 → #3259, #3514, #3515).
  The NUS deployment material, `deploy_nus.yml` and the dev slot's notes
  moved to the private deployment repository. `docs/deployment.md` is now
  the one general picture.
- **CI by path, and Postgres in parallel** (segments 22A and 22B, #3265 →
  #3285, 2026-10-26). A prose-only PR runs one job of about a minute, and
  `CI - Postgres` runs `pytest -n auto`.
- **Two more Cordware applications** (#3260 → #3412, #3420 → #3426,
  2026-10-25 → 2026-10-31):
  - Residential Operations and Support Logs (Residential segments 1A–1D)
    are screens on sample data behind a preview gate;
  - Cordware Utilities (U1, U2) is a live Email Address Checker.
- **Rosters and the directory** (21E, 21F, 19Z, #3415 → #3463,
  2026-10-31 → 2026-11-01). The host learned its public origin. Roster rows
  are bound to a directory account, and people are matched by it. Rosters
  gained append and merge uploads, invites check the directory, and the
  roster and invite boxes search it.
- **Segment 20, reshaped and shipped** (20A–20D, #3481 → #3512,
  2026-11-01 → 2026-11-02):
  - symmetric review (20B);
  - refinements (20C);
  - a shared top bar across all four applications, with the institution
    name and each user's Unit (20D).

  Beside it, three post-Azure items (gzip, a 5 s lock wait, Graph token
  renewal) and the honest outbox (#3513).

**Numbers taken at `2ffb0f42`**, `main` at #3521, before this snapshot's
own documents. Window `00501f2e..2ffb0f42`: **276 merge commits, 520
non-merge commits**, PRs #3226–#3521, 2026-10-22 → 2026-11-02, twelve
calendar days. `main`'s first-parent line holds 298 commits: the 276
merges, 20 squash-merged PRs (#3226 → #3229 and others early in the
window) and two direct commits (deleting `deploy_nus.yml`, and one upload).

**This document stands alone** and archives
`guide/archive/codebase_assessment_22oct.md` alongside it. Authority lives
elsewhere. The contract is `spec/` (indexed by `spec/README.md`) plus
`cordware/spec/`, `residentialapps/spec/` and `utilityapps/spec/`.
`guide/todo_master.md` holds the open work. **No sweep ran beside this
snapshot.** Three reads ran at the same commit instead, each by an agent
with no part in the window's builds:
- a spec-vs-code audit of every §3 row;
- a defect read of the window's RRW changes, with scratch tests;
- a read of the three non-RRW packages.

Their findings are §3, §5 and §6. Nothing was filed as a register, and
nothing was edited.

**Development context:** a single author, with AI agents building. The
author checks each change in a browser against a local run with fake
auth, and since 2026-10-31 also on the institutional deployment. This
window ran at about 23 merges a day, most of them small.

---

## 1. What's in the box

Review Robin Web runs structured peer review end to end:

1. An **operator** creates a **session** and imports **reviewers**,
   **reviewees**, **relationships** and **observers** from CSV.
2. They define **instruments** (what gets asked) with **rule sets** (who
   reviews whom) and **generate assignments**.
3. A **Validate** page runs its registered rules over the setup, and
   **Prepare** materializes invitations.
4. The session **activates**. Reviewers answer on their own surface, and
   the operator watches **Invitations** and **Responses** roll up.
5. Afterwards **reviewees** see their results and **observers** a
   collation, as a visibility policy resolved per audience and phase
   allows.

Configuration round-trips through CSV, and every mutation writes an audit
event. It is a server-rendered FastAPI + Jinja application on Postgres,
with no JS build step. It runs as one of four applications mounted in
**Cordware**, a host that owns identity, logging, the shared top bar and
Microsoft Graph access, at `/reviewrobin`.

**New since the 22 October snapshot:**

- **Rosters bound to the directory** (21F, #3424 → #3431). Migration
  `a7d3e9f1c2b5` gives each roster row a `directory_object_id`.
  - At import, add and edit, the operator's delegated Graph token
    resolves each address through `cordware/graph.py` (408 LOC, new in
    `cordware/`).
  - The Setup page reports the last import's directory check
    (`app/web/views/_directory_check.py`, 77 LOC).
  - A signed-in person matches a row by account as well as by email
    (`Viewer.matches` / `Viewer.clause`), so a row given by sign-in name
    reaches a person whose mail differs.
  - `app/services/directory_accounts.py` (217 LOC) holds the binding.
- **Append and merge uploads** (19Z, #3433 → #3463).
  - The four roster Upload cards gain an append tick and a merge
    (upsert) tick beside replace. Append refuses a row already on the
    roster (`AppendConflict`). Merge updates in place, a blank cell
    keeping the stored value, and deletes nothing.
  - Validate gains `{reviewers,reviewees,observers}.duplicate_account`
    for two rows on one account.
  - Invites are checked against the directory (#3451), and verified
    accounts show as pills.
  - Three directory-search routes feed pickers on the Accounts invite
    box, the roster rows and the help-contact boxes
    (`app/web/routes_operator/_directory.py`, 34 LOC, plus one in
    `_sys_admin.py`).
  - `app/services/csv_imports.py` grew +468 to carry the two modes.
- **Symmetric review** (20B, #3482 → #3499). Migration `b2f8d4a6c1e9` adds
  `sessions.symmetric_review` and a `mirrors_reviewer_id` link.
  `app/services/symmetric_review.py` (225 LOC) mirrors reviewers to
  reviewees on every reviewer write. Under the mode, Reviewees is
  read-only, imports follow the reviewers, and only the Reviewers roster
  is exported.
- **The shared top bar** (20D, #3503 → #3512).
  - `_partials/top_bar.html` and `app/web/views/_top_line.py` (89 LOC)
    render one header across RRW, Residential and Utilities.
  - Its top line is `CORDWARE_INSTITUTION_NAME`, or the session
    creator's Unit (migration `c3e9a1f7d2b4`, `users.unit`, a sys-admin
    bulk Set Unit, audit event `workspace.user_unit_set`).
  - Sys admin moved into the account menu.
- **Host and deployment** (21E, #3415 → #3417; post-Azure items, #3474 →
  #3477):
  - `CORDWARE_PUBLIC_ORIGIN` rewrites scheme and host behind a gateway;
  - responses are gzipped;
  - the session lock waits at most 5 s, then answers the 409 page;
  - the Graph token renews on page load and on "unauthorized".
  - RRW reads `RRW_DATABASE_URL` before `DATABASE_URL` (#3258).
- **The honest outbox** (#3513). Outbox rows stay `queued` until a
  transport sends them, and `invitation.status = "sent"` means "send
  recorded". The SMTP cards on Settings are gone (14C Item 1, #3471).

**Unchanged this window:**
- the assignment engine's generation algorithm;
- the audit envelope schema;
- the visibility grid;
- Rehydrate (still gated off);
- the dependency set.

Of the three migrations, all add columns and none drops one. A fourth
migration file changed in its docstring only (#3469).

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`.
**Two areas are new:** `residentialapps/` and `utilityapps/` arrived this
window. Their code matched no area and went uncounted (153 files), and
their 30 Markdown files fell into `docs`. On 2026-11-02 each gained an
area holding the whole package (code, templates, tests, docs), as
`cordware/` did on 22 October. So **the `docs` delta below is understated
by those 30 files**. The other areas compare like with like.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `tests` | 606 (581 prior) | **190,792** | +6,560 (+3.6%) |
| `docs` | 339 (326 prior) | **178,445** | +979 (+0.6%) |
| `production` | 230 (225 prior) | **80,965** | +3,569 (+4.6%) |
| `templates` | 71 (67 prior) | **34,777** | +970 (+2.9%) |
| `residentialapps` | 151 | **20,444** | new area |
| `tooling` | 16 (15 prior) | **12,385** | +316 (+2.6%) |
| `migrations` | 99 (96 prior) | **8,120** | +136 (+1.7%) |
| `cordware` | 20 (16 prior) | **4,256** | +1,925 (+82.6%) |
| `utilityapps` | 32 | **3,072** | new area |

**Test-to-production is 2.36**, from 2.38: RRW's tests grew more slowly
than its code for the first time in four snapshots. My read is that the
window's RRW work was features with focused tests (19Z, 20B, 20D), not
registers that bring a regression file per row. The test count for the
new packages sits in their own areas, below.

**Tests: 8,111 passed, 7 skipped, 0 xfails** (was 7,077 / 4 / 0), at
`2ffb0f42` with `node` and Chromium present (`RRW_REQUIRE_BROWSER=1`).
The count now includes `residentialapps/tests` (349 collected) and
`utilityapps/tests` (123), both on `pytest`'s `testpaths`, as well as
`cordware/tests` (206). `ruff check .` is clean. The seven skips:
- the opt-in CSS parity dump;
- three Postgres-only row-lock tests in
  `tests/integration/test_owner_add_lock.py`;
- three new Postgres-only lock-wait tests in
  `tests/integration/test_session_lock_timeout.py`.

All six run in `ci-postgres`. Both CI tracks were green on #3521 at
`2ffb0f42`. Browser tests: **223 in 53 files** (was 196 in 47).

**Endpoints and schema: 199 routes in RRW over 99 migrations** (was
197 / 96):
- 196 `@router.*` (121 POST, 73 GET, 1 PATCH, 1 DELETE);
- 3 `@app.get` in `app/main.py`.

Added: the three directory-search GETs and `POST
/sys-admin/users/bulk-set-unit`. Removed: `POST /settings` and `POST
/settings/clear` with the SMTP cards. `EVENT_SCHEMAS` registers **161**
event types (was 160), and Validate runs **26** rules (was 22).

| LOC | File | Δ |
| --- | --- | --- |
| 2,186 | `app/services/csv_imports.py` | +468 |
| 1,677 | `app/web/routes_operator/_shared.py` | +184 |
| 1,605 | `app/services/responses/_core.py` | +20 |
| 1,506 | `app/services/validation.py` | +142 |
| 1,492 | `app/web/routes_operator/_quick_setup.py` | +111 |
| 1,395 | `app/services/instruments/_band1.py` | +149 |
| 1,381 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,362 | `app/services/assignments/_generate.py` | +41 |
| 1,356 | `app/web/views/_instruments.py` | unchanged |
| 1,334 | `app/web/routes_operator/_instruments.py` | unchanged |

**`csv_imports.py` took the window's largest single growth.** It went
1,718 → 2,186, ten commits, almost all 19Z: append, merge, and the
directory binding at import. Its `_save` now folds replace, append and
merge together. `_shared.py` passed the ~1,600 line the 22 October
watchlist set, with 19Z's directory and merge-ask helpers (§9).
`validation.py` gained the four new rules. Among templates, `base.html`
rose to **6,761** (+216, the top bar's styles) and
`operator/instruments_index.html` held at **7,195**.

**Where the growth landed:** production churn is **+5 files, −0**. The
five new modules total 642 LOC:

| Module | LOC |
| --- | --- |
| `symmetric_review.py` | 225 |
| `directory_accounts.py` | 217 |
| `views/_top_line.py` | 89 |
| `views/_directory_check.py` | 77 |
| `routes_operator/_directory.py` | 34 |

So about a sixth of the +3,569 went into new seams, and five sixths onto
existing ones, led by `csv_imports.py`. My read: the new seams each own
one contract, as last window's did. The pattern to watch is the one the
22 October snapshot named: shared modules accreting a feature's second
half (`_shared.py` again, and now `csv_imports.py`).

**Package shape:**
- `app/services` holds 107 Python files (was 105).
- `app/web` holds 82 (was 79): `app/web/views` is 32 (was 30) and
  `app/web/routes_operator` 23 (was 22).
- `app/db/models` holds 22 (unchanged).
- `cordware/` holds 9 Python modules outside its tests (was 7):
  `graph.py` and `settings.py` are new, and `web/` holds the landing page
  and the shared app icons.

**The three other packages:**

| Package | All LOC | Python LOC | Test files | Tests collected | Persistence |
| --- | --- | --- | --- | --- | --- |
| `residentialapps` | 20,444 | 9,329 | 21 | 349 | none |
| `utilityapps` | 3,072 | 1,751 | 6 | 123 | none, by design |
| `cordware` | 4,256 | 3,483 | 7 | 206 | none of its own |

- **`residentialapps/` is screens, not yet an application.** All 62 GET
  routes render from three in-code sample modules (`sample_leave.py`
  1,275, `sample_support.py` 977, `sample_data.py` 470). There are no
  POST routes, no models and no migrations. Deployed, every non-health
  route answers 404 to anyone off the preview list.
- **`utilityapps/` is real and stateless.** The file travels back in the
  page, results come as a download, and nothing is stored.

Commands: `find <pkg> -type f -not -path '*__pycache__*' | xargs wc -l`,
and `pytest <pkg>/tests --collect-only -q`.

**Duplication and churn** (`python3 tools/code_metrics.py` at `2ffb0f42`):

| | ≥10-line blocks | prior |
| --- | --- | --- |
| `app/` | 3,100 / 65,017 = **4.8%** | 5.1% |
| `tests/` | 15,473 / 153,428 = **10.1%** | 10.4% |

Churn, the share of Python lines deleted within 14 days of being written
over all 3,418 merges on `main`, is **71,032 of 111,235 (63.9%)**, against
a same-share baseline of 47.9%: a **ratio of 1.3×**, unchanged.

The roster route modules' duplication is **27% / 25% / 25%**
(`_setup_relationships.py`, `_setup_observers.py`, `_setup_reviewers.py`).
`_instruments.py` is 22%, and the reviewer surface's `_routes.py`, new to
the list, also 22%.

---

## 3. Functional-spec compliance

Every row was checked against code at `2ffb0f42` by the spec-vs-code
audit, which ran each drift fix's regression tests and the new areas'
tests: 505 passed, 3 skipped (Postgres-only). **Bold rows changed this
window.** **Every ⚠ drift the 22 October table named is fixed**, each by
a commit in the window with its regression test. The three below are new.

| Area | Spec | Status |
| --- | --- | --- |
| **Lifecycle (five states)** | `spec/lifecycle.md` | ✓ shipped. An untouched Release window saves (L1, #3231). The session lock waits 5 s, then 409 (#3475) |
| **Assignments engine** | `spec/assignments.md` | ✓ shipped. One reading of a stored rule set (E1) and the catch-all group never the reviewer's own (E2), both #3237. The relationship mirror under symmetric review |
| **Validate page** | `spec/validate_page.md` | ✓ shipped. **26 rules** (was 22): `instruments.rule_set_unloadable` (#3238) and the three `duplicate_account` rules (#3438) |
| **Workflow card** | `spec/workflow_card.md` | ✓ shipped. Prepare reports an unloadable rule set (E3, #3237). Invitations read "marked sent" (#3513) |
| Instruments | `spec/instruments.md` | ✓ shipped. Spec prose only this window |
| **Setup pages** | `spec/setup_pages.md` | ✓ shipped. Empty file choice (S2, #3236), the directory-check line (#3428), Reviewees read-only under symmetric review (#3490). ⚠ drift: append and merge undocumented (D-a) |
| **Quick Setup** | `spec/quick_setup_card_spec.md` | ✓ shipped. Relationships asks before clearing group answers (S1, #3232). Symmetric mode set first |
| Operations pages | `spec/operations_pages.md` | ✓ shipped. No divergence found |
| **Session owners / tags** | `spec/session_owners.md`, `spec/sessions_overview.md` | ✓ shipped. Archived templates read-only (O2), the root sort cookie expired (C2), both #3235. Verified-name pills (#3485, #3497) |
| **Participant model** | `spec/participant_model.md` | ✓ shipped. The observer CSV's `Submitted` column (R4, #3230). Signed-in people matched by directory account (#3430) |
| Visibility policy | `spec/visibility_policy.md` | ✓ shipped. Spec prose only |
| **Reviewer surface** | `spec/reviewer-surface.md` | ✓ shipped. Group digest (R1, #3229). A re-save keeps its stamp (R2, #3230) |
| **CSV contracts + round-trip** | `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` | ✓ shipped. Matrix columns added (D4, #3241). ⚠ drift: "Wipe-and-replace, never merge" (D-a) |
| **Extracts** | `spec/extract_data.md` | ✓ shipped. Safe zip member names (O1, #3228). Only the Reviewers roster under symmetric review |
| **Audit** | `spec/architecture.md` | ✓ shipped. **161 types.** Production shape violations logged as WARNING (F2, #3239) |
| **Permissions / identity** | `spec/permissions.md`, `cordware/spec/identity.md` | ✓ shipped. A blank email claim answers cleanly (P1, #3236). Graph token renewal (#3476). ⚠ drift: three routes outside the matrix (D-b); Graph search undocumented (D-c) |
| **Cordware host and mount** | `cordware/spec/host.md` | ✓ shipped, and **deployed** (2026-10-31). Reminders rebuild links from the token (C1, #3233). Public origin (#3416), gzip (#3474). Host events 4 and 5 still not logged (a `todo_master` stub) |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped; render only. Locked on archived sessions (#3235) |
| **Email dispatch** | `spec/email_infra_options.md` | ⛔ not sending. `SmtpEmailTransport` has no caller. The outbox now says so (#3513). 14B retired; 14F (by hand) is unblocked, 14G (on a clock) waits on IT |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off. Duplicate short labels fall back to position (D1, #3239) |
| Blob storage | `guide/blob_storage_candidates.md` | ⏸ not built |
| Operator theming | `spec/visual_style_rrw.md` | ⏸ planned. A Light/Dark toggle shipped with 20D |
| **Symmetric review** | `spec/architecture.md`, `spec/setup_pages.md`, `spec/csv_contracts.md` | ✓ shipped (20B, #3482 → #3499), plan archived |
| **Roster append / merge** | (19Z's doc impact: `spec/setup_pages.md`) | ✓ code shipped (#3436 → #3440). 19Z open, at its spec pass. ⚠ drift (D-a) |
| **Directory accounts and search** | `cordware/spec/identity.md`, `spec/setup_pages.md` | ✓ shipped (#3427 → #3431, #3451 → #3460). ⚠ drift (D-b, D-c) |
| **Header chrome** | `spec/operator_ui_concept.md`, `docs/header_chrome.md` | ✓ shipped (20D, #3503 → #3512), closed |
| **Residential, Utilities** | `residentialapps/spec/`, `utilityapps/spec/` | Residential ⏸ screens on sample data, gated; Utilities ✓ shipped and deployed |

**The three drifts are one cause: 19Z's spec pass has not run.**
- **D-a.** `spec/csv_contracts.md` says a roster import is "Wipe-and-replace,
  never merge", but `save_reviewers`, `save_reviewees`, `save_observers`
  and `save_relationships` take `append` and `merge`. Neither spec
  mentions the ticks.
- **D-b.** The three directory-search routes appear in no spec, so "every
  route's gate matches the matrix" no longer holds for all 199. Their
  gates are right (§4).
- **D-c.** `cordware/spec/identity.md` documents `find_users` but not
  `search_users`.

All three are named in 19Z's close.

**Spec corpus:** 35 files in `spec/` (unchanged), plus 2 in
`cordware/spec/`, 4 in `residentialapps/spec/` and 2 in
`utilityapps/spec/`. `spec/rrw_functional_spec.md` fell **2,596 → 1,892
lines**: the trim three snapshots proposed shipped as corpus F11 (#3247).

## 4. Strengths

- **The registers converged, then stayed converged.** The 22 October bug
  register (19 rows) and corpus register (59) were worked in two days
  (#3227 → #3250). This snapshot's audit re-ran every fix's regression
  test, and all held. The defect read of a 276-merge window then found
  **2 medium and 3 low, none high** (§6), against 19 a window earlier.
  Different readers, a narrower scope (the window's changes, not whole
  areas), so the fall is not a controlled measurement. My read is that
  register-plus-test has become the steady state.
- **The first deployment arrived without code firefighting.** The host
  went live on the institutional tenant on 2026-10-31, and Graph from
  application code was proved there (#3423). The window's only
  production-driven fixes were small and planned (gzip, the lock wait,
  token renewal, #3474 → #3477). The deployment prose that the last
  snapshot called the risk left this repository for the private one,
  leaving `docs/deployment.md` with no institutional identifier in it.
- **Four applications, boundaries enforced by test.**
  `cordware/tests/test_import_boundary.py` forbids each package from
  importing the others' code (only `cordware` may be imported), with
  planted-import tests that prove it fails. The package read found no
  violation. RRW imports `cordware.graph`, `cordware.identity` and
  `cordware.settings`, the allowed direction only.
- **The new gates held.**
  - The Email Address Checker answers 403 to a non-super-admin and 401
    when anonymous on every route, from one router-level dependency.
  - Residential's preview gate returned 404 on all 60 non-health routes,
    deployed-mode, to a non-previewer.
  - The directory-search routes sit behind `require_session_operator`,
    `require_operator` and `require_sys_admin` as documented.
  - 618 junk GETs to Residential and a hostile-input set to the checker
    produced no 5xx.
- **CI fits the work.** Since 22A a prose-only PR runs the `prose` lane
  alone (54 s on #3521), and since 22B `CI - Postgres` runs in parallel
  (about 9 → 4 minutes).

## 5. Weaknesses

- **Directory binding rides a per-request delegated token, and fails
  quietly.** Roster rows are bound to accounts at import using the
  operator's own Graph token, with a 120 s budget on the request path. If
  the token has expired, every lookup returns "unauthorized" and the
  replace saves every row unbound. A person given by sign-in name then
  loses their surface, and the only signal is a "not checked" count on the
  card (§6, M1). The pickers retry after renewal; the import does not.
- **Symmetric review is held by convention.** Reviewees mirror reviewers
  only because each of the 10 reviewer-writing call sites calls
  `sync_reviewees_from_reviewers`. Nothing structural enforces it, and no
  Validate rule detects a reviewee that has drifted from its reviewer.
- **The specs lag 19Z.** For the first time since the permissions matrix
  was made exhaustive, three routes sit outside it, and the CSV contract
  states the opposite of what ships (D-a, D-b, D-c). The cause is
  procedural, a spec pass deferred to the close as the skill allows. The
  effect is that a reader of `spec/csv_contracts.md` today is told merge
  does not exist.
- **Residential is 20,444 lines with no persistence.** Its three sample
  modules (2,722 lines) carry the screens. The wiring items (1B items 2–5,
  1C items 2–5) have not started. My read: the screens were the right
  first step (scaffold-first, approved in walkthroughs), but every screen
  approved on sample data is a contract the wiring must meet, and some
  will move. The preview gate's test checks only `GET /`
  (`residentialapps/tests/test_preview_gate.py:89-96`), so a new router
  that forgets the dependency would pass CI.
- **`csv_imports.py` is 2,186 lines and `_shared.py` 1,677.** Both grew by
  a feature's second concern, the import modes and the directory. §9.
- **Nothing sends email.** Unchanged in effect, now honest in the UI
  (#3513) and planned: 14F sends on the operator's click and needs nothing
  from IT. 14E (a clock) and 14F are queued and not started.
- **No type checker.** `ruff` runs its default rules only. Segment 22C,
  queued, measured 289 basic-mode pyright errors in application code.

## 6. Bugs and regressions

**Known open bugs at `2ffb0f42`: 0 high, 2 medium, 3 low**, from the
defect read of the window's RRW changes. Three were reproduced by scratch
tests (one on SQLite only), and two by reading.
None is filed in a register; this section is the record.

- **M1. An import with an expired Graph token unbinds every row it
  replaces** (by reading). `app/services/csv_imports.py` `_save`, with
  `cordware/graph.py` `look_up_all`. Token renewal runs only on page load,
  so a Replace submitted long enough after the page loaded for the token
  to lapse sends an expired token, and every row is saved without its directory
  account. A row given by sign-in name stops matching the person whose
  mail differs.
- **M2. Merge binds an unbound row to an account another row holds**
  (reproduced). `_merge_rows`, the branch that binds a held row with no
  account. Append refuses this case, and merge refuses it within one file,
  but not against the saved roster. The gates pick the lowest id, so the
  other row's assignments and answers drop out of the person's view, and
  only the non-blocking Validate warning shows it.
- **L1. `acknowledged_loss` 500s on a 4,300-digit value**
  (`routes_operator/_shared.py:212`, reproduced). It predates the window,
  but 20B and 19Z added call sites. It is the class `oversized_ids` fixed
  elsewhere.
- **L2. SQLite only: a Replace under symmetric review can hand a removed
  person's reviewee row to a new reviewer** (reproduced on SQLite). Rows
  in SQLAlchemy's memory do not see `ON DELETE SET NULL`, and SQLite
  reuses ids. Postgres does not reuse ids, so production is unaffected,
  but local runs and the SQLite suite can show it.
- **L3. A symmetric session's export, imported into a non-empty session,
  leaves the reviewees alone without a notice** (by reading). The bundle
  drops `reviewees.csv` by design, and the import keeps the mode off
  beside existing rows.

Also noted, not defects: append accepts two rows in one file on one
account (19Z's plan records it as known); the Residential CSV writer has
no formula-prefix guard (harmless on sample data, needed before real
data); the Utilities index page answers without identity (it holds
nothing about anyone).

**Checked and sound:**
- the three migrations, portable both ways;
- every literal `event_type` registered;
- the new routes' gates;
- `Viewer.matches` and `Viewer.clause` agreeing across all three
  participant gates, the dashboard and the self-review engine;
- merge deleting nothing;
- the lock timeout's savepoint;
- nothing reading the outbox's `sent` status.

The 2026-10-22 registers' regression files pass (471 passed, 3 skipped,
in the defect read). No open GitHub issues, no open pull requests, 0
xfails, and the seven skips named in §2.

Worth remembering from the window:

- **The prior family, stored data under newer rules, did not recur.**
  The register's five rows of it (R2, C1, C2, L1, L2) are fixed, and the
  new migrations add columns only. M1 is its cousin: data *lost* when an
  outside service cannot answer, rather than data re-judged.
- **`deploy_nus.yml` left the repository** (2026-10-24) with the move to
  the private deployment repository. A release can no longer be started
  from here, which is what `CONTRIBUTING.md` now says.

## 7. Estimated size upon completion

**Current: production 80,965, templates 34,777, `cordware` 4,256** at
`2ffb0f42`. Estimates are my judgment, from the plans' ladders and the
nearest shipped analogue.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| This snapshot's defects (M1, M2, L1–L3) | +80–200 | +0–30 | nothing |
| 19Z close (spec pass only) | 0 | 0 | nothing |
| 14C Item 2, the Email settings card | +50–150 | +50–120 | 14F's send path, to wire |
| 14E, a clock for timed actions | +150–300 | 0 | nothing |
| 14F, email by hand as the operator | +500–900 | +150–300 | nothing (delegated `Mail.Send` granted) |
| 14G, scheduled email | +200–400 | +20–60 | IT (offline tokens or a mailbox) |
| 22C, pyright (fixes, then a gate) | +0–200 | 0 | nothing |
| Blob storage (18Q) seam and first consumers | +400–700 | +50–150 | an institutional storage account |
| Operator theming (stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| **Projected floor** | **82,495–84,315** | **35,147–35,637** | |

`cordware` adds host logging events 4 and 5, about +80–200, to
**4,336–4,456**. Excluded:
- Residential's wiring, which is a second application's growth, in its
  own area;
- magic links (`guide/magic_links.md`, deferred);
- the technical-support contact (deferred by 20A);
- everything in `guide/deferred_consolidated.md`.

**Reconciliation: production and templates landed inside the prior
range; `cordware` did not.** The 22 October snapshot projected
**79,396–81,176** production and **34,497–35,297** templates. Production
is **80,965** and templates **34,777**, both inside. Of its named items:
- the bug register and the corpus register's code rows shipped;
- 14B did not, and was retired for 14E/14F/14G;
- segment 20 shipped, reshaped into 20A–20D;
- blob storage and theming did not;
- the support contact was deferred.

The rest of the growth was scope discovered: 19Z's append, merge and
directory pickers, and 21F's binding. As last time, the landing inside
the range is a coincidence of size more than a forecast that held.
`cordware` projected **2,411–2,531** and is **4,256**:
- `graph.py` (408) moved Graph into the host for three applications;
- the public origin, the landing page's diagnosis rows, the shared icons
  and the top bar were all unplanned on 22 October.

## 8. Bottom line

Review Robin Web is deployed. The Cordware host has served it and the
Email Address Checker on the institutional tenant since 2026-10-31, with
Graph from application code proved. In twelve days and 276 merges, it:
- closed both 22 October registers and the long-standing functional-spec
  trim;
- moved the deployment prose to the private repository;
- split CI by path;
- added two more applications to the host;
- bound roster rows to directory accounts, with append and merge uploads;
- shipped symmetric review and a shared header.

The suite reached 8,111 tests. A defect read of the window found **2
medium and 3 low, none high**. Both mediums are at the new directory
seam. The live thread is the half that did not change: **nothing sends
email**, now with an unblocked plan.

**Recommended next moves, at most three:**

1. **Fix M1 and M2 before an operator uploads a real roster.** A Replace
   with an expired token should keep each row's existing binding, or
   refuse and ask for a reload, rather than save rows unbound. Merge
   should refuse an account another row holds, as append does. Both sit
   where a production roster now meets a production directory, and M1's
   loss is silent.
2. **Close 19Z with its spec pass.** D-a, D-b and D-c are one pass. Until
   it runs, the CSV contract says merge does not exist, and the
   permissions matrix is incomplete for the first time since it was made
   exhaustive.
3. **Build 14F.** "Nothing sends email" is in its fifth snapshot. 14F needs
   nothing from IT (delegated `Mail.Send` is granted), and 14E's clock and
   14C Item 2's settings card both wait on its transport. It is the
   shortest path from a deployed app to a usable one.

**Settling the 22 October proposals.**
- Move 1, *fix the register's medium defects, starting with O1 and R1*:
  **shipped**. O1 in #3228, R1 in #3229, the stored-data family (R2, L1,
  C1) in #3230 → #3233, the register done by #3238.
- Move 2, *bring the deployment documents up to the host before any NUS
  deploy*: **shipped, differently**. Corpus H1–H21 were fixed (#3248),
  then the material left for the private repository (#3251 → #3259,
  #3514). The first NUS deploy ran from there.
- Move 3, *rule the functional-spec trim (corpus F11)*: **shipped**
  (#3247, 2,596 → 1,892 lines). It was in its third snapshot.

---

## 9. Proposed file splits — watchlist

**Still no split queued. Two files passed their trigger.**

- **`app/services/csv_imports.py` (2,186 LOC, +468).** Past 2,000 and the
  largest file in `app/`. The 22 October cut, the incoming-set checks as
  `_incoming.py`, still stands. This window adds a second, cleaner one:
  the three modes as `_import_modes.py` (append's conflict check, merge's
  `_merge_rows`, the shared counts), leaving `_save` a dispatcher. M2's
  fix lands in `_merge_rows`, so the cut could carry it. **Recommended
  when M2 is fixed.**
- **`app/web/routes_operator/_shared.py` (1,677 LOC, +184).** Past the
  ~1,600 line set on 22 October. The proposed cut, `_uploads.py` for the
  four cards' upload read and hold, stands, and 19Z's directory helpers
  would go with it. L1's fix lands in `acknowledged_loss` here.
- **`app/web/routes_operator/_quick_setup.py` (1,492, +111)** and
  **`app/services/validation.py` (1,506, +142)** are watched. Both grew by
  additions in their own concern (20B's mode order; four rules).
- **`app/web/templates/operator/instruments_index.html` (7,195, unchanged)**
  and **`base.html` (6,761, +216)** are carried. `base.html` took the top
  bar's styles. Its stylesheet extraction is still deferred, and nothing
  forces it.
- **`residentialapps/residentialops/sample_leave.py` (1,275)** is not a
  split candidate: it is sample data that the wiring will retire.
