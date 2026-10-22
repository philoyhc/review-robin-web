# Codebase assessment — 2026-10-22

**As of** the close of Segment 21, the Cordware foundations. The 16
October snapshot called Segment 21 speculative and on hold; the author
reopened it against Cordware strategy v0.8 on 2026-10-21, and it shipped
and closed in two days. RRW now runs mounted at `/reviewrobin` under a
host that owns identity and logging. Before that, the 2026-10-16 bug
register was worked to nothing open, and three small segments shipped:
public IDs (19V), held uploads (19W) and browser-run refinements (19X,
19Y). No plan is in progress. 14B and 20 still wait on the institutional
Azure deployment, and the dev slot is dormant.

**Since the prior snapshot** (`guide/archive/codebase_assessment_16oct.md`,
`3d8adb38`), five arcs shipped:

- **The 2026-10-16 register, worked to empty** (PRs #3085 → #3121,
  2026-10-16 → 2026-10-18). All 46 rows done, eleven after one sitting of
  rulings (#3112 → #3118), plus three small plans the fixes opened: pair
  tags, warnings before clearing group answers, and refusing bad input.
- **Public IDs** (Segment 19V, PRs #3124 → #3137, 2026-10-18 →
  2026-10-19). Session URLs, form fields, CSV addresses and sort keys stop
  carrying workspace-wide ids.
- **Held uploads** (Segment 19W, PRs #3141 → #3151, 2026-10-19). A file
  chosen for a refused upload survives the ask; the author's second
  browser checklist run.
- **Refinements from browser runs** (Segments 19X and 19Y, PRs #3152 →
  #3191, 2026-10-19 → 2026-10-21, and #3220 → #3225, 2026-10-22).
  Date-time boxes, instrument intro layouts, help cards, the reviewer
  header, fit-to-text answer boxes, and the Guide's screencaps.
- **Cordware** (Segment 21, PRs #3192 → #3219, 2026-10-21 → 2026-10-22,
  after the strategy documents in #3138 → #3140, #3158, #3166 and
  #3191). The host skeleton (21A), the URL sweep (21B), shared identity
  (21C) and the flip to `/reviewrobin` (21D).

**Numbers taken at `00501f2e`**, `main` at #3225, before this snapshot's
own documents. Window `3d8adb38..00501f2e`: **73 merge commits, 262
non-merge commits, PRs #3082–#3225** (143 numbered), 2026-10-16 →
2026-10-22, seven calendar days. The PR range is read from commit
subjects: from #3150 the author merged most PRs by squash, which
`measure.py`'s merge count does not see.

**This document stands alone** and archives
`guide/archive/codebase_assessment_16oct.md` alongside it. Authority
lives elsewhere: `spec/` (indexed by `spec/README.md`) and, new this
window, `cordware/spec/` are the contract, and
`spec/rrw_functional_spec.md` and its siblings are what §3 audits
against. `guide/todo_master.md` holds the open work. **A bug sweep and a
corpus drift sweep ran beside it at the same commit**: seven code-reading
agents produced `guide/findings_2026-10-22_bugs.md`, and six verify-mode
`spec-writer` reads produced `guide/sweep_2026-10-22_corpus.md` and
`guide/findings_2026-10-22_corpus.md`. §3, §5 and §6 lean on them.

**Development context:** a single author, with AI agents building. The
author checks each change in a browser against a local run with fake
auth. The app is not deployed; the dev slot was made dormant on
2026-10-21, and an institutional pilot is pending. This window ran at
roughly 20 PRs a day, most of them small.

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
application on Postgres, with no JS build step. Since this window it runs as
the first application mounted in **Cordware**, a host that owns identity and
process logging, at `/reviewrobin`.

**New since the 16 October snapshot:**

- **Cordware, and RRW under a prefix** (segment 21, #3192 → #3219).
  `cordware/` is a new top-level package (16 files, 2,331 LOC, counted as its
  own area in §2). `cordware/main.py` (243 LOC) builds the host once:
  `/health` first, then each application in `REGISTRY` mounted by
  `CORDWARE_APPS`, and runs the mounted application's lifespan inside its
  own. `cordware/identity.py` (302 LOC) is now the only reader of the Easy
  Auth `X-MS-CLIENT-PRINCIPAL*` headers and the only source of the fake
  local identity; `app/auth/identity.py` re-exports it under RRW's names
  (21C). Super-admin became Cordware's platform role (#3213), and a
  malformed principal header no longer answers 500 (#3214).
  `cordware/logging.py` (116 LOC) owns the root logger. In RRW,
  `app/web/urls.py` (124 LOC) is the one place a URL leaves the app: the
  `url()` / `here()` template globals, `urls.redirect()` (all 124
  `RedirectResponse` calls moved to it, #3204) and `cookie_path()` (21B).
  `tests/unit/test_url_leaks.py` refuses a root-path literal and
  `tests/integration/test_url_crawl.py` visits every GET route under the
  mount (#3206). The flip to `/reviewrobin` is #3217.
- **The 2026-10-16 bug register, worked to nothing open** (#3085 → #3121,
  2026-10-16 → 2026-10-18). All 46 rows done, eleven of them after the
  author's rulings (#3112 → #3118). Rules are checked on write, on the
  Band 1 card and in the Settings import (#3085). `app/web/downloads.py`
  (34 LOC) builds every `Content-Disposition` (#3097).
  `app/web/oversized_ids.py` (41 LOC) answers 404 for an id past 64 bits on
  both databases (#3106). A regroup clears the group answers it changed,
  and a group that only shrinks keeps its answer (#3098 → #3100); the
  instrument card, a reviewee tag edit and Relationships changes ask before
  clearing them (#3101 → #3105). A change after Submit needs a new Submit
  (R1, #3115). Migration `f3a7c1e9d5b2` stores the Self review toggle per
  instrument (E3, #3114). Pair-context tags judge the pair, in Link 2 only;
  person-level pair tags are retired and the import refuses them
  (#3086 → #3091, #3119 → #3121).
- **Public IDs** (segment 19V, #3124 → #3137). Migration `a9d4f2c7e1b8`
  adds `sessions.public_id`, and session URLs resolve by it, so a URL no
  longer counts the workspace's sessions. The review form names answers by
  ordinal rather than assignment ID (`app/services/responses/_form_keys.py`,
  88 LOC) and refuses a post whose page changed underneath it, against a
  digest keyed by `sessions.form_key` (migration `c4e8b2f6a1d9`, #3130).
  The observer CSV address takes the instrument's number (#3135, migration
  `d2f7a3c9b5e4` makes `(session_id, session_seq)` unique), and the review
  page's sort keys stop carrying IDs (#3137).
- **A chosen file survives an ask** (segment 19W, #3145 → #3149).
  `app/services/held_uploads.py` (182 LOC) and the `held_uploads` table
  (migration `e8b3c1d4f6a2`) hold a refused submit's files, per session and
  operator under an opaque token with a short TTL, so the operator ticks and
  submits again without choosing them again; on the Setup upload cards and
  Quick Setup. Quick Setup on a fresh session takes a settings file as
  Create does (#3141).
- **Refinements from browser runs** (segments 19X and 19Y, #3152 → #3191,
  #3220 → #3225). Date-time boxes take 24-hour text with a picker and a
  clear (#3163, #3164). An instrument's intro picks Layout 1 or Layout 2
  (migration `c4e9a2f7b1d3`, #3171), and its help texts gather into one
  card (#3174). String answer boxes fit their text; the reviewer
  surface's header lost its card, its participant row's `|` drops when the
  pills wrap, and the description moved up to the session name
  (#3221 → #3224). The Guide's screencaps were retaken to match
  (#3184, #3185, #3188, #3225).

**Unchanged this window:** the assignment engine's generation algorithm
(its rules gained pair-context tags, above), the audit envelope schema, the
email pipeline (nothing sends), Rehydrate (still gated off), the
visibility grid's shape and the dependency set. Of the six migrations, four
add a column, one adds a table and one a unique constraint; none drops a
column.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`.
**One area is new:** `cordware/` matched no area and went uncounted, so on
2026-10-22 it gained an area of its own, holding the whole host package
(its code, template, tests and spec). The six existing areas are classified
as on 16 October, so their deltas compare like with like.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `tests` | 581 (515 prior) | **184,232** | +14,868 (+8.8%) |
| `docs` | 326 (315 prior) | **177,466** | +7,427 (+4.4%) |
| `production` | 225 (219 prior) | **77,396** | +3,660 (+5.0%) |
| `templates` | 67 (65 prior) | **33,807** | +1,118 (+3.4%) |
| `tooling` | 15 | **12,069** | +158 (+1.3%) |
| `migrations` | 96 (90 prior) | **7,984** | +342 (+4.5%) |
| `cordware` | 16 | **2,331** | new area |

**Test-to-production is 2.38**, from 2.30. Tests outgrew production again,
by the same two forces as last window: every register fix and plan rung
brought its regression test, and the browser tests grew from 127 in 33
files to **196 in 47**. Production grew more slowly than in the prior
window (+5.0% against +9.2%): a week that fixed and refined more than it
built. That is my read.

**Tests: 7,077 passed, 4 skipped, 0 xfails** (was 6,233 / 4 / 0), at
`00501f2e` with `node` and Chromium present (`RRW_REQUIRE_BROWSER=1`), so
the inline-script parse and the browser tests ran. The count includes
`cordware/tests/`, now on `pytest`'s `testpaths`. `ruff check .` is
clean. The four skips are unchanged: the opt-in CSS parity dump and the
three Postgres-only row-lock tests in
`tests/integration/test_owner_add_lock.py`, which run in `ci-postgres`.
Both CI tracks were green on #3225.

**Endpoints and schema: 197 route declarations in RRW over 96
migrations** (was 192 / 90): 194 `@router.*` (122 POST, 70 GET, 1 PATCH,
1 DELETE) and 3 `@app.get` in `app/main.py`. The host adds two of its
own, `/health` and the landing page at `/`. `EVENT_SCHEMAS` registers
**160** event types (was 155).

| LOC | File | Δ |
| --- | --- | --- |
| 1,718 | `app/services/csv_imports.py` | +94 |
| 1,585 | `app/services/responses/_core.py` | +176 |
| 1,493 | `app/web/routes_operator/_shared.py` | +353 |
| 1,381 | `app/services/instruments/_instrument_crud.py` | +189 |
| 1,381 | `app/web/routes_operator/_quick_setup.py` | +279 |
| 1,364 | `app/services/validation.py` | +2 |
| 1,356 | `app/web/views/_instruments.py` | +9 |
| 1,334 | `app/web/routes_operator/_instruments.py` | +65 |
| 1,321 | `app/services/assignments/_generate.py` | +46 |
| 1,246 | `app/services/instruments/_band1.py` | +127 |

**Two route modules climbed into the top five.** `routes_operator/_shared.py`
grew 1,140 → 1,493, mostly from 19W's hold plumbing for the four Setup
upload cards (#3147, +159) and the S4/O7 rulings' re-rendered refusals
(#3118, +146). `_quick_setup.py` grew 1,102 → 1,381 with 19W's hold
(#3148, +198) and the same rulings (#3118, +139). `responses/_core.py`
took R1's change-after-Submit rule and 19V's ordinal form keys;
`_band1.py` the pair-context tags and rules checked on write. Among
templates, `base.html` rose to **6,545** (+432) and
`operator/instruments_index.html` to **7,195** (+227).

**Where the growth landed:** production churn is **+6 files, −0**. The
six new modules total 522 LOC: `held_uploads.py` 182, `urls.py` 124,
`responses/_form_keys.py` 88, `models/held_upload.py` 53,
`oversized_ids.py` 41 and `downloads.py` 34. So about a seventh of the
+3,660 went into new seams and six sevenths onto existing ones, led by the
two route modules above. My read: the new seams are the right size and
each owns one contract (URL emission, form keys, download headers). The
accumulation on `_shared.py` is the one to watch. A shared module in the
route package is where four cards' common upload handling now lives,
and that handling decides what was "chosen" (S2 in the bug register).
Separately, `cordware/` is 2,331 lines in its own area.

**Package shape:** `app/services` holds 105 Python files (was 103).
`app/web` holds 79 (was 76): `app/web/views` is 30 and
`app/web/routes_operator` 22 (both unchanged). `app/db/models` holds 22
(was 21). `cordware/` is a new top-level package of 7 Python modules plus
its tests, a template and two specs.

**Duplication and churn** (`python3 tools/code_metrics.py` at `00501f2e`):

| | ≥10-line blocks | prior |
| --- | --- | --- |
| `app/` | 3,175 / 62,151 = **5.1%** | 5.4% |
| `tests/` | 15,436 / 148,115 = **10.4%** | 10.8% |

Churn, the share of Python lines deleted within 14 days of being written
over all 3,142 merges on `main`, is **68,257 of 107,466 (63.5%)**,
against a same-share baseline of 48.2%: a **ratio of 1.3×**, unchanged.
The roster route modules' duplication fell again, to **40% / 28% / 27% /
26%** (`_setup_reviewers.py`, `_setup_relationships.py`,
`_setup_observers.py`, `_setup_reviewees.py`); `_instruments.py` is 22%.

## 3. Functional-spec compliance

Every row was checked against code at `00501f2e` by the six corpus reads
and the seven bug reads at the same commit. **Bold rows changed this
window.** A `⚠ drift` row names its finding: *bugs R1* is in
`guide/findings_2026-10-22_bugs.md`, *corpus B3* in
`guide/findings_2026-10-22_corpus.md`.

| Area | Spec | Status |
| --- | --- | --- |
| Lifecycle (five states) | `spec/lifecycle.md` | ✓ shipped. Six pages run the scheduled-event pass (#3116). ⚠ drift: an untouched Release window refuses Save (bugs L1); the Observers gate count (corpus B1) |
| **Assignments engine** | `spec/assignments.md` | ✓ shipped. Pair-context tags judge the pair, in Link 2 only (#3120); rules checked on write (#3085). ⚠ drift: disabled children and non-link entries read two ways (bugs E1); the empty-key self group (bugs E2) |
| Validate page | `spec/validate_page.md` | ✓ shipped. 22 rules (unchanged). ⚠ drift: the GET runs the scheduled pass the spec says it doesn't (corpus B3) |
| Workflow card | `spec/workflow_card.md` | ✓ shipped. ⚠ drift: Prepare 500s on an unloadable rule set (bugs E3) |
| **Instruments** | `spec/instruments.md` | ✓ shipped. Self review per instrument (#3114); intro Layout 1 / 2 (#3171); help cards (#3174); a Save that clears group answers asks first (#3102) |
| **Setup pages** | `spec/setup_pages.md` | ✓ shipped. A chosen file survives an ask (19W, #3147). ⚠ drift: an empty chosen file sends the held one (bugs S2) |
| **Quick Setup** | `spec/quick_setup_card_spec.md` | ✓ shipped. Held files (#3148); a settings file on a fresh session (#3141). ⚠ drift: Relationships clears group answers without asking (bugs S1) |
| Operations pages | `spec/operations_pages.md` | ✓ shipped. No divergence (corpus D read) |
| **Session owners / tags** | `spec/session_owners.md`, `spec/sessions_overview.md` | ✓ shipped. Select all covers only shown rows (#3095); archived sessions left out of the lobby's counts (#3168). ⚠ drift: the Archived date moves on a later write (bugs O2); `session_owners.md` maps to no routing module (corpus B7) |
| **Participant model** | `spec/participant_model.md` | ✓ shipped. ⚠ drift: the observer CSV carries unsubmitted values (bugs R4) |
| Visibility policy | `spec/visibility_policy.md` | ✓ shipped. Unchanged but for labels ("Not shown", #3187) |
| **Reviewer surface** | `spec/reviewer-surface.md` | ✓ shipped. Change after Submit needs a new Submit (#3115); ordinal form keys and a page digest (#3130); the header as two rows (#3222 → #3224). ⚠ drift: a stale group form after a regroup (bugs R1); a re-save clears a stamp (bugs R2) |
| CSV contracts + round-trip | `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` | ✓ shipped; round-trips byte-identical. ⚠ drift: new columns missing from the matrix (corpus D4) |
| **Extracts** | `spec/extract_data.md` | ✓ shipped. Every download's `Content-Disposition` (#3097). ⚠ drift: the session code becomes a zip member path (bugs O1) |
| Audit | `spec/architecture.md` | ✓ shipped. `EVENT_SCHEMAS`, 160 types, strict in tests. ⚠ drift: production shape violations never reach the log (corpus F2) |
| **Permissions / identity** | `spec/permissions.md`, `cordware/spec/identity.md` | ✓ shipped; all 197 routes' gates match the matrix (bugs P read). Identity is Cordware's (21C); sessions resolve by `public_id` (#3127). ⚠ drift: a blank email claim 500s (bugs P1) |
| **Cordware host and mount** | `cordware/spec/host.md` | ✓ shipped 2026-10-21 → 2026-10-22. Host, `/health`, landing, logging, `/reviewrobin`. Events 4 and 5 not logged (a `todo_master` stub). ⚠ drift: pre-flip invite links resent by reminders (bugs C1) |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped; render only. No divergence |
| Email dispatch | `spec/email_infra_options.md` | ⛔ blocked. Nothing in `app/` calls a transport. Segment 14B needs institutional Azure |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off. ⚠ drift: short labels as a unique match key (corpus D1) |
| Blob storage | `guide/blob_storage_candidates.md` | ⏸ not built |
| Operator theming | `spec/visual_style_rrw.md` | ⏸ planned. `guide/deferred_consolidated.md` Part A |

**Doc drift: a corpus sweep ran at this commit.** All 63 files were
read (four long ones in part), and 49 findings were filed with nothing
edited. Seven are medium: three in specs (corpus B1, B3, D1) and four in
`docs/` and root (corpus H1–H4). Most of the `docs/` findings are one
story, deployment prose that predates the host and the dormant slot.
The spec count held at 35 files, plus the two in `cordware/spec/`. `spec/rrw_functional_spec.md` rose 2,575 →
2,596 lines; the trim the last two snapshots proposed now has a section
list (corpus F11).

## 4. Strengths

- **The bug count fell by more than half, with a seventh area added.** The
  2026-10-16 sweep found 46 defects, 8 of them high; all 46 were done by
  2026-10-18, each with its regression test. This sweep, with the same six
  areas plus the Cordware mount, found **19, none high**, and every read
  re-ran last week's regression files for its area and found them
  holding (128 tests in R's alone, 133 in E's). My read: the register
  method converges when the fixes come with tests. Different readers ran
  each sweep, so the fall is not a controlled measurement.
- **The prefix flip was gated, not hand-checked.** `app/web/urls.py` is
  the one place a URL leaves RRW; all 124 `RedirectResponse` calls moved
  to `urls.redirect()` (#3204); `tests/unit/test_url_leaks.py` refuses a
  root-path literal and `tests/integration/test_url_crawl.py` visits every
  GET route under the mount (#3206). The C read then sent 122 POST
  routes, in two states and as two users, and found no unprefixed URL.
  Both of its findings are about data stored before the flip, which no
  code gate can see.
- **The gates held again.** The P read walked all 197 routes, sent another
  session's ids to 41 child-id routes and its roster and assignment ids
  in 68 form bodies, and sent 13 hostile principal headers. Nothing let
  anyone in, and nothing changed another session. Its two findings are
  500s on malformed input.
- **Identity crossed a package boundary cleanly.** Cordware now owns the
  Easy Auth headers, the fake identity and the super-admin role, and RRW
  keys its fake roles only off `is_fake`. The boundary is a test
  (`cordware/tests/test_import_boundary.py`), not a convention.
- **Small segments closed inside the window.** 19V, 19W, 19Y and four
  sub-segments of 21 each opened and closed between 2026-10-18 and
  2026-10-22, scaffold first, with none reverted.

## 5. Weaknesses

- **Readers that re-judge stored data under newer rules.** Five of this
  sweep's 19 defects are one family. A rule or a shape changed, and what
  was already stored was not reconciled with it:
  - R2: stored CRLF or non-canonical values read as changed;
  - C1: invite URLs stored before the flip;
  - C2: sort cookies set at `Path=/` before the flip;
  - L1: a stored release pair now checked against the cap;
  - L2: an unpadded year that no longer parses.

  Last window's family was write paths that trust what they store; this
  is its mirror. My read: each change shipped its tests against new data,
  and nothing asks "what is already stored that this now refuses?" No
  plan; the register is new.
- **The deployment prose has fallen behind the host.** Nine of the eleven
  `docs/` and root findings concern deployment or Cordware:
  - the dev deploy described as live (corpus H1);
  - a start command that does not exist (corpus H4);
  - the parser attributed to the wrong module (corpus H7);
  - a missing environment variable (corpus H8).

  `.github/workflows/deploy_nus.yml` does not yet ship `cordware/` (stage
  4). Nothing is deployed, so nothing is broken yet, but these are the
  documents a first NUS deploy will be run from.
- **Nothing sends email, and nothing is deployed.** Unchanged; the dev
  slot is now dormant, with a resume checklist in `docs/deployment_dev.md`.
  14B and 20 wait on the institutional deployment, and Cordware stage 3 is
  unblocked but unplanned.
- **The functional-spec trim is in its third snapshot.** Moves to shrink
  `spec/rrw_functional_spec.md` were proposed on 5 and 16 October and not
  done; it grew 21 lines. Corpus F11 now names the sections and the
  constraints, so the remaining cost is an author's ruling and a PR.
- **Specs accumulate provenance.** Dated rulings, finding ids and segment
  ids recur in at least fifteen places (corpus A3, D9, E6): the commonest
  class of finding in this sweep. The prose rule is in the `segment-plan`
  skill and is not checked. Filed mentally; no plan.
- **`routes_operator/_shared.py` is 1,493 lines** and grew 353 in one
  window as the home of the Setup cards' shared upload handling. No plan;
  §9.

## 6. Bugs and regressions

**Known open bugs at `00501f2e`: 0 high, 7 medium, 12 low**, all in
`guide/findings_2026-10-22_bugs.md`, none yet fixed; 16 reproduced by a
scratch test, 3 by reading. The medium ones:

- a stale group form writes its answers into a different group after a
  regroup (R1);
- an unchanged re-save of a stored CRLF or non-canonical value clears its
  Submit stamp (R2);
- the observer CSV includes unsubmitted values (R4);
- an untouched Release window refuses every Session Home Save (L1);
- a session code becomes a zip member path, `../` included (O1);
- Quick Setup's Relationships slot clears group answers without asking
  (S1);
- reminders resend invitation links from before the flip, which 404 (C1).

Also checked: no open GitHub issues; no open pull requests; 0 xfails;
four skips, all named in §2. Five corpus findings are code defects rather
than spec drift (`guide/findings_2026-10-22_corpus.md` §1), the largest
Rehydrate's short-label match (corpus D1, gated off).

Worth remembering from the window, each now with a guard:

- **A Save after Submit released an edited answer as submitted** (the 16
  October R1, ruled and done in #3115). Its follow-on is this sweep's R2:
  the new change test meets values stored under older normalization.
- **A non-Latin-1 session code made every download 500** (#3097). Its
  cousin is this sweep's O1: the same free-text code also names zip
  members.
- **A regroup could leave one group holding different answers**
  (#3098 → #3100). The clear now runs, and this sweep's R1 is the open
  tab that can refill it.

## 7. Estimated size upon completion

**Current: production 77,396, templates 33,807, `cordware` 2,331** at
`00501f2e`.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| The 2026-10-22 bug register | +300–700 | +20–80 | rulings on R3, R4, L1, O2, O3, S1, E2, C1 |
| The corpus register's code rows (F2, F9, E8, B7, D1) | +20–120 | +0–10 | rulings on D1, F9, B7 |
| Segment 14B, email dispatch, reminders, invitations | +900–1,400 | +200–400 | the institutional Azure deployment |
| Segment 20, operator polish and documentation | +200–500 | +300–600 | the institutional Azure deployment concluded |
| Blob storage (18Q) seam and first consumers | +400–700 | +50–150 | an institutional storage account |
| Operator theming (stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |
| **Projected floor** | **79,396–81,176** | **34,497–35,297** | |

`cordware` adds host logging events 4 and 5, about +80–200, to
**2,411–2,531**. This excludes anything past v1, every entry in
`guide/deferred_consolidated.md` Parts A and C, and Cordware stage 3,
which is a second application rather than more of this one.

**Reconciliation: both areas landed inside the prior range, but not by
the prior plan.** The 16 October snapshot projected **75,816–77,596**
production and **33,409–34,239** templates. Production is **77,396** and
templates **33,807**, both inside. Of the named items, only the first
(the 2026-10-16 register, +400–900) shipped. The rest of the growth was
**scope discovered**:
- 19V's public IDs;
- 19W's held uploads;
- 19X and 19Y;
- Segment 21's RRW side, mainly `urls.py` and the redirect sweep. Segment
  21 itself had been excluded as speculative.

The landing inside the range is a coincidence of size, not a forecast
that held, and Cordware's 2,331 lines sit outside it entirely. The new
first two rows are this snapshot's registers. The other five carry
forward unchanged.

## 8. Bottom line

Review Robin Web closed last week's 46-row bug register in two days, then
shipped public IDs, held uploads and a run of browser refinements. It
ended the window as the first application mounted under Cordware, at
`/reviewrobin`. The suite reached 7,077 tests. A bug sweep at this commit
found **19 defects, none high**, against 46 with 8 high a week earlier; the
most consequential share one cause, stored data that newer rules
re-judge. The live thread is unchanged: **nothing sends email, and
nothing is deployed**.

**Recommended next moves, at most three:**

1. **Fix the register's medium defects, starting with O1 and R1.** O1 is
   the only finding that can place a file outside the operator's own
   extraction folder (with an unzip tool that does not sanitize names),
   and its fix is the slug helper the instrument names already use. R1 can put one group's answers on another with no refusal. Then
   the stored-data family (R2, L1, C1) together, because each is
   one comparison taught to read what older code stored, and doing them
   at once makes that a habit rather than five patches. Rule R4, S1 and
   C1 first; they are the author's calls.
2. **Bring the deployment documents up to the host before any NUS deploy**
   (corpus H1–H9, with `deploy_nus.yml` shipping `cordware/`). The next
   deploy will be run from these pages, and a wrong start command fails
   on day one.
3. **Rule the functional-spec trim (corpus F11) and let the spec-update
   PRs carry it.** It is in its third snapshot; the sweep has done the
   reading, so what remains is a decision and a pass, best taken while the
   corpus register's update rows are being worked anyway.

**Settling the 16 October proposals.** Move 1, *fix the register's high
defects, starting with the write paths*: **shipped** (S2 and E1 in #3085,
L1 in #3093, O1 in #3095, the register done by #3121). Move 2, *rule the
seven author rows in one sitting*: **shipped** (#3112 → #3118,
2026-10-17 → 2026-10-18). Move 3, *schedule the next corpus sweep and let
it carry the functional-spec trim*: the sweep **shipped** with this
snapshot. The trim did not; it is carried into move 3 above with its
section list.

---

## 9. Proposed file splits — watchlist

**Still no split queued; one new file joined the list.**

- **`app/web/routes_operator/_shared.py` (1,493 LOC, +353).** New to the
  list. It now holds the shared upload handling for the four Setup cards
  (`read_upload`, the hold plumbing) beside the package's other common
  route helpers. The cut would be `_uploads.py`, the four cards' upload
  read and hold, which is also where S2's fix lands. Watch past ~1,600 or
  at the next card that grows an upload.
- **`app/services/csv_imports.py` (1,718 LOC, +94).** Growth slowed. The
  proposed first cut, the incoming-set checks as `_incoming.py`, stands;
  no carrier arrived this window.
- **`app/web/routes_operator/_quick_setup.py` (1,381, +279).** It took
  19W's hold and the rulings' re-renders. Watched, not listed: the growth
  is one feature's, and S1 and S3 land in it.
- **`app/services/responses/_core.py` (1,585, +176).** R1's rules and the
  ordinal keys landed here, and R2 and R3 will. `_form_keys.py` already
  left as its own module; the number canonicalization is the next
  candidate if it grows.
- **`app/web/templates/operator/instruments_index.html` (7,195 LOC,
  +227)** and **`base.html` (6,545, +432)** are carried. Neither has a
  trigger; extraction of `base.html`'s stylesheet is still post-Azure
  checklist item 4.

`app/services/instruments/_instrument_crud.py` (1,381, +189) and
`_band1.py` (1,246, +127) are watched but not listed: both grew by
features, not by a second concern.
