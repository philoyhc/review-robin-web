# Codebase assessment — 2026-11-03

**As of** the close of segment 20I (directory check follow-ups), with the
Cordware interoperability spec parked and no segment in build. The
2 November snapshot's register is worked off, its file splits shipped as
20E, and the directory seam it flagged went through four segments (20F →
20I). The deployment imports RRW through `6ff40f82`, so everything below
except the last lane fix (#3566, tooling only) is in the private import.
Nothing sends email yet.

**Since the prior snapshot** (`guide/archive/codebase_assessment_02nov.md`,
`2ffb0f42`), six arcs shipped, all on 2026-11-03 and the small hours of
11-04 (UTC):

- **The 2 November register, worked** (#3522 → #3525, #3541 → #3543). Its
  M1 and M2, the two medium directory defects, fixed first (#3525, #3524);
  L1 and N1–N3 after; L2 and L3 through 20F. The register is archived
  with every row struck.
- **20E — the watchlist's file splits** (#3526 → #3532). `csv_imports.py`
  and `validation.py` became packages; the Setup cards' upload handling
  left `_shared.py` for `app/web/roster_import.py`; the response tallies
  and the Band 1 preview moved out of their files.
- **20F — the symmetric mirror** (#3534 → #3538). The sync reads reviewee
  links from the database, drops duplicate mirrors, audits an unchanged
  save's repair (`reviewees.mirror_repaired`), and Validate gains
  `reviewees.mirror_drift`.
- **20G — the directory check, sturdier** (#3544 → #3549, with the banner
  audit #3546). Only an expired token holds an upload and asks to renew;
  every other failure saves and the line says why. Object ids are stored
  normalized (migration `e4b2c7a91d36`).
- **20H and 20I — the roster upload, from the 19Z walkthrough**
  (#3533, #3540, #3550 → #3564). The single-row forms refuse a second row
  on one account; the audit log's Event type filter; the upload counts its
  directory check down from the page, reading answers kept for 15 minutes
  (`directory_lookups`, migration `b7d4e2a9c1f3`); a "Check unmatched
  addresses again" button binds rows the directory now finds.
- **Cordware documents** (#3563, #3565, #3566, and the author's three
  renames). `cordware/docs/` holds the mobile-to-desktop guidance and the
  interoperability v0.3 spec and handoff, parked with the author's
  rulings; the CI lane picker and the private import's rules learned the
  folder.

**Numbers taken at `cc364ed0`**, `main` at #3566, before this snapshot's
own documents. Window `2ffb0f42..cc364ed0`: **37 merge commits, 80
non-merge commits**; `main`'s first-parent line holds 49 commits — the 37
merges, 8 squash-merged PRs (#3552 → #3555, #3563 → #3566) and 4 direct
commits by the author (one upload, three renames). PRs #3522 → #3566,
2026-11-02 → 2026-11-04 by commit date: two calendar days.

**This document stands alone** and archives
`guide/archive/codebase_assessment_02nov.md`. Authority lives elsewhere:
the contract is `spec/` (indexed by `spec/README.md`) plus
`cordware/spec/`, `residentialapps/spec/` and `utilityapps/spec/`;
`guide/todo_master.md` holds the open work. Three reads ran at
`cc364ed0`, each by an agent with no part in the window's builds:
- a spec-vs-code audit (§3);
- a defect read of the window's `app/`, `cordware/` and `alembic/`
  changes, with scratch tests (§6);
- a read of the three non-RRW packages, with their suite and a route fuzz
  (§3, §6).

Nothing was edited by them. Every defect, drift and gap they reported is a
row of `guide/findings_2026-11-03_assessment.md`, the checklist the fixes
strike off.

**Development context:** a single author, with AI agents building. The
window ran at about 22 PRs a day, almost all small; every code slice had
a cold read and a Codex review before merge.

---

## 1. What's in the box

An operator creates a review session and loads its rosters — reviewers,
reviewees, relationships, observers — by upload or by hand, each address
bound to a directory account where the institution's directory knows it.
Instruments define what reviewers answer; per-instrument rules generate
assignments; Validate checks the whole and Activate opens it. Reviewers
answer through their own surface, reviewees and observers read what the
visibility policy grants, and the operator extracts the responses. A
FastAPI + Jinja monolith over SQLAlchemy, mounted at `/reviewrobin` by the
Cordware host beside Residential Operations, Support Logs and Cordware
Utilities.

**New since the prior snapshot:**

- **Packages where files were** (20E). `app/services/csv_imports/`
  (`_parse`, `_saving`, `_identity`, `_modes`), `app/services/validation/`
  (`_registry`, `_rosters`, `_instruments`, `_assignments`, `_inputs`),
  `app/services/responses/_rollups.py`, `app/services/instruments/_preview.py`,
  and `app/web/roster_import.py` (the four Setup cards' upload read, hold
  and import, out of `routes_operator/_shared.py`).
- **The directory check's outcome is recorded and explained** (20G). An
  import's `*.imported` event carries `context.directory_unchecked`; the
  card's line names the reason (`views._directory_check._REASONS`); an
  expired token holds the file behind a renew banner
  (`partials/_directory_renew.html`, `cordwareRenewGraph()`).
- **The countdown and the recheck** (20H Item 6, 20I). Routes
  `POST /operator/sessions/{id}/directory-keys`, `…/directory-lookup` and
  `…/directory-recheck` in `routes_operator/_directory.py`; services
  `directory_lookups.py` (205 LOC) and `directory_recheck.py` (181); the
  `directory_lookups` table. The page never posts an outcome; the server
  keeps only what it fetched.
- **One person, one row** (20H Item 1). Add and address edit refuse an
  address that resolves to an account the roster already holds
  (`directory_accounts.account_holder`).
- **Smaller surfaces**: the audit log's Event type filter (prefix
  narrowing, click-to-toggle, Clear always shown); one banner stack under
  every Upload card's intro; a locked instrument card's fallback title.

**Unchanged this window:** the reviewer surface, results and collation,
assignments generation, the lifecycle, extracts, the email template
editor, Residential and Utilities (one doc row each aside), and the host's
code beyond its docs folder.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`
(unchanged). **The `cordware` delta is a move, not growth:** 979 lines of
prose came from `docs/` into `cordware/docs/`, which the `cordware` area
counts whole; its code grew by about 20 lines. So `docs` is understated
by the same 979.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `tests` | 623 (606 prior) | **193,541** | +2,749 (+1.4%) |
| `docs` | 345 (339 prior) | **180,394** | +1,949 (+1.1%) |
| `production` | 245 (230 prior) | **82,960** | +1,995 (+2.5%) |
| `templates` | 73 (71 prior) | **35,304** | +527 (+1.5%) |
| `residentialapps` | 151 | **20,482** | +38 (+0.2%) |
| `tooling` | 16 | **12,465** | +80 (+0.6%) |
| `migrations` | 101 (99 prior) | **8,240** | +120 (+1.5%) |
| `cordware` | 24 (20 prior) | **5,254** | +998 (+23.4%), see above |
| `utilityapps` | 32 | **3,072** | unchanged |

**Test-to-production is 2.33**, from 2.36: production grew faster, and a
third of its growth is 20E's package `__init__` re-export surface and
module headers rather than behavior (§2, "Where the growth landed").

**Tests: 8,265 passed, 11 skipped, 0 xfails** (was 8,111 / 7 / 0), at
`cc364ed0` with `node` and Chromium present; `ruff check .` is clean. The
four new skips are 20G's Postgres-only index-plan tests
(`tests/integration/test_directory_object_id_index.py`); the other seven
are the opt-in CSS parity dump and the six Postgres-only lock tests, as
before. All ten Postgres-only tests run in `ci-postgres`, green on
#3566. The non-RRW packages alone: 680 passed, 0
skipped (the package read). Browser tests: **232 in 53 files** (was 223
in 53).

**Endpoints and schema: 202 routes in RRW over 101 migrations** (was
199 / 99): 199 `@router.*` (124 POST, 73 GET, 1 PATCH, 1 DELETE) and 3
`@app.get`. Added: `directory-keys`, `directory-lookup`,
`directory-recheck`. `EVENT_SCHEMAS` registers **165** event types (was
161); Validate runs **27** rules (was 26; `reviewees.mirror_drift`).

| LOC | File | Δ |
| --- | --- | --- |
| 1,505 | `app/web/routes_operator/_quick_setup.py` | +13 |
| 1,381 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,362 | `app/services/assignments/_generate.py` | unchanged |
| 1,356 | `app/web/views/_instruments.py` | unchanged |
| 1,334 | `app/web/routes_operator/_instruments.py` | unchanged |
| 1,243 | `app/services/session_lifecycle.py` | unchanged |
| 1,241 | `app/services/users.py` | +2 |
| 1,227 | `app/services/audit.py` | +8 |
| 1,196 | `app/web/routes_operator/_operations.py` | unchanged |
| 1,194 | `app/services/responses/_core.py` | −411 |

**The top of the table flattened.** On 2 November it ran 2,186 → 1,334;
it now runs 1,505 → 1,194, a plateau with no file past 1,600. The three
that crossed their triggers are gone from it: `csv_imports.py` (2,186) is
a package whose largest member is `_parse.py` (904); `_shared.py` fell
1,677 → 1,072; `validation.py` (1,506) is a package whose largest member
is `_rosters.py` (506). `responses/_core.py` gave 411 lines to
`_rollups.py`. Templates: `operator/instruments_index.html` 7,203 (+8),
`base.html` 6,789 (+28, the banner and button spacing).

**Where the growth landed:** production churn is **+17 files, −2**. Of
the 17, 14 are 20E's package members, carrying code that already existed;
three are new behavior: `directory_lookups.py` (205), `directory_recheck.py`
(181) and, by its content, `roster_import.py`'s directory steps. The
window's `app/` diff is +7,835 / −5,313: most of it moved, not written.

**Duplication** (`python3 tools/code_metrics.py`, blocks of 10+ lines):
`app/` **4.8%**, `tests/` **9.9%**. The most-duplicated production files
are still the per-roster Setup routes (`_setup_observers.py` 26%,
`_setup_relationships.py` 27%, `_setup_reviewers.py` 26%): the four
cards' near-identical handlers, which 20E's `roster_import.py` began to
share and did not finish. **Churn** — lines deleted within 14 days of
being written — is **61.8% against a 47.5% baseline, ratio 1.3×**, over
all 3,455 merges: recent code is rewritten a little more than its age
alone explains, which matches a project that refines each surface in
small passes.

## 3. Functional-spec compliance

SECTION3

## 4. Strengths

- **A register worked inside a day, and its splits shipped the same
  day.** The 2 November snapshot's five defects and four drifts were
  struck by #3543, and all three files past their triggers were split by
  20E (#3526 → #3532) with no behavior change: the suite and both CI
  tracks stayed green across each rung, and a cold read per rung caught
  only stale pointers and an import cycle (broken in #3529).
- **The directory seam held its trust line under four segments of
  change.** 20G, 20H and 20I each touched how an address binds to an
  account, and the invariant stated in 20H's plan — the server binds only
  what it fetched — survived each: the page posts keys, never outcomes;
  answers are cached per operator and session; the recheck reads only its
  own countdown's answers (`since`). The window's defect read checked this
  path specifically and found it sound (§6).
- **Concurrency is designed for Postgres, not discovered there.** The
  lookup cache's per-key savepoint (#3554) was written in answer to a
  two-tab race Codex described before any user met it, and its test forces
  the collision on both dialects; 20F's guard checks at a root commit,
  not a savepoint release (#3536), after Postgres showed the difference.
- **Tests grew with the behavior.** 232 browser tests (+9) cover the
  window's scripts — the countdown's batches and early stops, the audit
  filter's toggling, the banner spacing measured in pixels — where an
  inline script's failure is otherwise silent.

## 5. Weaknesses

- **The recheck is a setup write that doesn't behave like one** (§6, M1).
  Every other roster write sends a validated session back to draft; the
  recheck, which can flip self-review classification and rewrite a
  symmetric mirror, does not, and it runs on activated sessions too. It
  is the window's one confirmed medium, and it sits on the newest surface.
- **The four Setup route modules still repeat themselves.** 26–27% of
  `_setup_observers.py`, `_setup_relationships.py` and `_setup_reviewers.py`
  is duplicated in 10-line blocks. `roster_import.py` shares the upload
  path; Observers still carries its own copy of `_handle_import`
  (`observers_import_submit`), so a fix to the upload must land twice —
  20H Item 6 did exactly that. No plan.
- **Email still does not send.** In its sixth snapshot. 14F (email by hand
  as the operator) needs nothing from IT and has not started; the window
  went to the directory seam instead.
- **Browser behavior is the author's to check, and the list is long.**
  The countdown against real Graph, the recheck's placement, the audit
  filter in Safari and Firefox, the banner spacing light and dark: none of
  it can be settled by the suite, and `guide/things_to_check_in_browser.md`
  is the only record of what is owed.
- **The public repository names the institution in places**, against the
  host's own rule that the institution's name lives only in the private
  deployment (§6, N1). Small, but a hygiene line that has drifted.

## 6. Bugs and regressions

**At `cc364ed0`: one medium, six low, none high.** Each is a row of
`guide/findings_2026-11-03_assessment.md`; CONFIRMED means reproduced by a
scratch test or request, PLAUSIBLE means traced only.

- **M1 (medium, CONFIRMED).** `directory_recheck.recheck` binds rows,
  recomputes self-review classification and (under symmetric review)
  re-syncs the mirror without `lifecycle.invalidate_if_validated`. A
  validated session whose recheck turns an assignment into a self-review
  flips its `include` off and stays `validated`; in an activated session
  the same pass switches off included assignments mid-review.
- **L1 (low, PLAUSIBLE).** The Reviewers recheck under symmetric review
  calls the mirror sync without `acknowledged_loss`; a drifted mirror whose
  sync would clear answered group responses raises `GroupAnswersWouldClear`
  uncaught, a 500 rather than the ask every other reviewer write shows.
- **L2 (low, PLAUSIBLE).** The countdown sets its shared `counted` flag
  before `requestSubmit`; a submit the browser's validation then blocks
  leaves it set, so every later submit on the page skips the count (the
  server still checks every address).
- **L3 (low, CONFIRMED).** The Email Address Checker's preview takes a
  `column` value of over 4,300 digits to `int()`, which raises: a 500 where
  the spec says the value is ignored. Super-admin only.
- **L4 (low, CONFIRMED).** The Residential preview list's address reader
  strips angle brackets before trailing punctuation, so `<a@b.edu>.` names
  nobody; fails closed.
- **L5 (low, CONFIRMED by trace).** `residentialapps/web/` logs under a
  logger no registry prefix covers, so its two log lines are stamped
  `application: "cordware"`.
- **L6 (trivial, CONFIRMED).** A whitespace-only
  `X-MS-CLIENT-PRINCIPAL-NAME` yields a blank-looking name; Easy Auth never
  sends one.

Hardening notes, not defects: the Graph transport follows redirects with
its bearer header (Graph `/users` does not redirect); the Checker's
`/check` and `/preview` accept cross-site form posts (impact: rate usage);
Support Logs' consultation check carries emails in a GET query (sample
data today). They are register rows N2–N4.

**Caught and fixed in the window, worth remembering** (2 November ids): an
expired token that saved rows unbound (M1, #3525); merge binding one account
twice (M2, #3524); a symmetric sync that read stale links (L2, #3534); the countdown
that would have waited out a dead directory 30 s a lookup (Codex, #3555);
the lookup cache's two-tab insert race (Codex, #3554); a recheck that bound
without recomputing self-review (Codex, #3558) — whose fix is this
snapshot's M1.

**What was checked to say the rest is sound:** the defect read's list
(the lookup cache's scope, TTL and race; the recheck's lock and refusals;
20H's single-row checks; both migrations' round trips on SQLite; the 20G
stop on all four upload routes, Quick Setup and rehydrate; the 2 November
M1's kept account; the audit filter's script; the banners' `form=`), and the package
read's (identity parsing, Graph quoting and logging, the import boundary,
the preview gate, a 1,898-request route fuzz with no 5xx).

## 7. Estimated size upon completion

**Current: production 82,960, templates 35,304, `cordware` 5,254** at
`cc364ed0`. Estimates are my judgment, from the plans and the nearest
shipped analogue.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| This snapshot's defects (M1, L1–L6) | +40–120 | +0–10 | nothing |
| The Setup routes' shared handler (§9) | −200 – −400 | 0 | a plan |
| 14C Item 2, the Email settings card | +50–150 | +50–120 | 14F's send path |
| 14E, a clock for timed actions | +150–300 | 0 | nothing |
| 14F, email by hand as the operator | +500–900 | +150–300 | nothing |
| 14G, scheduled email | +200–400 | +20–60 | IT |
| 22C, pyright (fixes, then a gate) | +0–200 | 0 | nothing |
| Blob storage (18Q) | +400–700 | +50–150 | a storage account |
| Operator theming (stretch) | +150–300 | +100–200 | nothing |
| **Projected floor** | **84,050–86,610** | **35,674–36,144** | |

Excluded: Residential's wiring and RA Lifecycle (their own areas), the
interoperability work (parked until a consumer exists), magic links, and
everything in `guide/deferred_consolidated.md`.

**Reconciliation.** The 2 November snapshot projected production
**82,495–84,315**; it is **82,960**, inside, but not by the projected
route: the named items (14C–14G, 22C, blob storage, theming) all did not
start, and the growth is the register's fixes, 20E's re-export surface and
the directory seam's three segments (20G–20I), none of them on the list.
Templates projected **35,147–35,637**; **35,304**, inside. `cordware`
projected **4,336–4,456** with host logging events 4 and 5; it is 5,254,
but by moved prose: its code is about 4,275, and events 4 and 5 still are
not logged.

## 8. Bottom line

In two days and 45 PRs, the 2 November register was struck, the three
oversized files split into packages with no behavior change, and the
roster upload's directory check became something an operator can watch,
recover and repeat. The defect read found **one medium, none high**, and
it is on the newest surface: the recheck changes setup without sending a
validated session back to draft. The live thread is still the one that
did not move: **nothing sends email**.

**Recommended next moves, at most three:**

1. **Fix M1 (and L1 with it) before the recheck reaches an activated
   session in production.** The deployment now imports it. Invalidate a
   validated session when a recheck binds, and decide whether an activated
   session's recheck may move includes at all; both are in
   `directory_recheck.recheck`.
2. **Build 14F.** "Nothing sends email" is in its sixth snapshot, needs
   nothing from IT, and 14E and 14C Item 2 wait on its transport. The
   directory seam is now done enough to step away from.
3. **Plan the Setup routes' shared handler** before the next upload change
   lands twice. 20E moved the upload read into `roster_import.py`; Observers
   still runs its own copy, and the four modules' 26% duplication is where
   the next two-site fix will come from.

**Settling the 2 November proposals.**
- Move 1, *fix its M1 and M2 first*: **shipped** (#3525, #3524), then the rest
  of the register (#3534, #3542, #3543).
- Move 2, *close 19Z with its spec pass*: **shipped**; D-a, D-b and D-c
  closed with 19Z, and the walkthrough became 20H.
- Move 3, *build 14F*: **not started**; carried as move 2 again.

---

## 9. Proposed file splits — watchlist

**The 2 November watchlist closed as 20E** (`guide/archive/` holds its
plan): `csv_imports.py` and `validation.py` are packages, `_shared.py`'s
upload handling is `roster_import.py`, and `responses/_core.py` and
`instruments/_band1.py` gave up their tallies and preview.

**Watched now:**
- **`app/web/routes_operator/_quick_setup.py` (1,505, +13)**, the largest
  file in `app/`. Cohesive (one card, five slots, one pipeline); a split
  candidate only if Quick Setup grows another mode.
- **The four Setup route modules** (`_setup_reviewers.py` 647 code lines,
  `_setup_observers.py` 939, `_setup_relationships.py` 922, and Reviewees):
  not size but duplication (§2, §5). The seam is Observers' import route
  onto `roster_import._handle_import`, which it mirrors.
- **`app/web/templates/operator/instruments_index.html` (7,203)** and
  **`base.html` (6,789)**, carried. Nothing forces the stylesheet out.
