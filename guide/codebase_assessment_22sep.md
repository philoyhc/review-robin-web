# Codebase assessment — 2026-09-22

**As of** the close of the 19M–19R arc: six segments opened and closed (or
all-but-closed) in ten days, ending with Segment 19R's eight items shipped and
its ninth deferred unbuilt. 19R is the only plan still open in `guide/`, by the
author's instruction, and it has no open items.

**Since the prior snapshot** (`guide/archive/codebase_assessment_11sep.md`,
`ba7b37e7`), six arcs shipped:

- **19M — spec history sweep** (closed 2026-09-13). Six sweep batches pulling
  narrative history out of live specs, then a reversal on the author's rule that
  history does not belong in a spec at all.
- **19N — generated assignments** (closed 2026-09-13). Assignments are only ever
  *generated*; the identity fold settled on `str.lower`; Rehydrate gated off
  (`rehydrate_enabled` ships `False`).
- **19P — the expander revamp** (PRs #2393 → #2446, closed 2026-09-18). Seven
  items, five built and two retired unbuilt: the roster and Operations tables
  moved to the lobby's expander idiom.
- **19Q — workflow and previews** (closed 2026-09-19/20). Seven items. The
  Previews hub retired onto the Invitations per-reviewer drill-in; Prepare now
  creates the invitations; instrument identity became per-session.
- **19O — rosters and instruments** (closed 2026-09-20). Eight items plus a
  sixteen-entry consistency register.
- **19R — optimization and bugfixes** (opened and eight items closed
  2026-09-21, PRs #2518 → #2540). Driven by a measured bench rather than a
  hunch; see §1.

**Numbers taken at `ed8a69e7` on `main`, 2026-09-22.** Window `ba7b37e7..HEAD`:
**228 merge commits, 540 non-merge commits, PRs #2322–#2541** (220 numbered)
across 2026-09-12 → 2026-09-22. The delta baseline is the **11 September**
sidecar, because the 18 September document was a re-measurement of a Codex read
and wrote no sidecar of its own — so every Δ below spans ten days and two
snapshots' worth of work, not one.

**This document stands alone** and archives
`guide/archive/codebase_assessment_18sep.md` alongside it. Authority lives
elsewhere: `docs/status.md` is the ship-state record (As of 2026-09-21, 1,112
lines), `spec/rrw_functional_spec.md` and its siblings are what §3 audits
against, and `guide/app_responsiveness.md` owns every performance figure quoted
here.

**An independent cold read exists** and is worth reading first:
`guide/codex_assessment_21sep.md`, taken at `8dee36e3`. I built most of this
window, so under `constitution.md` III I am the maker, not a checker. Where I
re-measured its figures they reproduce, with one exception recorded in §1 and
one reconciliation in §2.

**Development context:** single author, AI agents doing the building, no
laptop dev loop, pre-deployment with an institutional pilot pending. 228 merges
in ten days is not a team velocity figure and should not be read as one.

## 1. What's in the box

Review Robin Web runs structured peer review end to end. An **operator** creates
a **session**, imports **reviewers**, **reviewees**, **relationships** and
**observers** from CSV, defines **instruments** (what gets asked) with **rule
sets** (who reviews whom), and **generates assignments** — the reviewer ×
reviewee × instrument pairs. A **Validate** page runs 22 registered rules over
the setup and gates promotion; **Prepare** materializes invitations; the session
**activates**, reviewers answer on their own surface, and the operator watches
**Invitations** and **Responses** roll up. Afterwards **reviewees** see their
results and **observers** see a collation, each under a visibility policy
resolved per audience and phase. Configuration round-trips through CSV, every
mutation writes an audit event, and the whole thing is a server-rendered
FastAPI + Jinja monolith on Postgres with no JS build step.

**New since the prior snapshot:**

- **The expander idiom reached every roster and Operations table** (19P, PRs
  #2393 → #2446). Reviewers, Observers, Reviewees, Relationships and the three
  Operations tables now share one row-expander, toolbar and Unlock panel. Two
  of 19P's seven items were **retired unbuilt** after the shape settled — the
  plan records them struck rather than deleted.
- **The Previews hub retired** (19Q Item 1). `spec/preview_hub.md` is now a
  retirement notice; its two jobs moved to the Invitations per-reviewer
  drill-in, which opens `/operator/sessions/{id}/preview-surface/{page_n}` and
  renders the three email tabs for a named reviewer.
- **Prepare creates the invitations** (19Q Item 2), and one eligibility test now
  governs every send path — the fix for a page and a button that disagreed about
  who was in the session.
- **Instrument identity became per-session** (19Q Item 6), across three
  surfaces.
- **19R rebuilt the hot paths off a measured bench.** `guide/app_responsiveness.md`
  was written 2026-09-20 at 1,000 × 1,000 and **re-set 2026-09-21 to a 200 × 200
  full matrix** on the author's ruling that a thousand people each reviewing a
  hundred is rare. Its finding was that **this was not a database problem** —
  SQL was never more than 9% of any slow page; five of six slow pages were slow
  because the rules engine ran on page load. Item 2 cached the staleness verdict
  on four `instruments.cached_reconcile_*` columns against a content stamp
  (`app/services/assignments/_reconcile_cache.py`, 287 LOC — **the window's only
  new production module**). Item 3 rolled progress up in SQL, retiring a
  2,000-query-per-page N+1. Item 5 stopped the Validate page building its
  readiness report twice and gave the 22 rules one shared `ValidationInputs`.
- **Four of 19R's eight items turned out to be about descriptions, not code**
  (Items 6, 7, 8 and half of 2). Item 6 found **nine wrong passages describing
  one validation rule across six files**; Item 8 deleted `compute_staleness`,
  the uncalled helper those descriptions kept reproducing; Item 7 retired the
  `Instruction-Received` stamp as a standing rule after measuring that **of 37
  slices that wrote it, 16 parse** — git reads only a message's last block as
  trailers, so 21 were silently discarded.

**Unchanged this window:** the reviewer response surface, the participant
`/results` and `/collation` contracts, the audit envelope schema, the CSV
contracts, the permission model, and the transaction boundary. No new
dependency, no frontend framework, no service split.

**One correction to the cold read.** `guide/codex_assessment_21sep.md` reports
that at "the current 200 × 200 full-matrix benchmark" Invitations and Responses
sit "at roughly 1.4–1.5 seconds". Those are the figures in
`guide/app_responsiveness.md`'s **third** column, the retired 1,000 × 1,000
stress fixture. At the bench they are **646 ms and 693 ms**; every page is under
700 ms there. The conclusion it draws from them — that local refinement should
stop and deployment should decide what resumes — I agree with, and it does not
depend on the figure.

## 2. Size (LOC)

Physical lines, git-tracked files only, classified by `guide/assessment.json`.
Δ is against the 11 September sidecar, so it covers ten days.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 269 (247 prior) | **170,435** | +20,043 (+13.3%) |
| `tests` | 363 (307 prior) | **129,731** | +26,012 (+25.1%) |
| `production` | 205 | **63,541** | +4,086 (+6.9%) |
| `templates` | 60 (64 prior) | **29,161** | +3,941 (+15.6%) |
| `tooling` | 18 (14 prior) | **16,444** | +4,388 (+36.4%) |
| `migrations` | 79 (77 prior) | **6,917** | +145 (+2.1%) |

**Test-to-production crossed 2.0 for the first time: 2.04**, from 1.74. Tests
grew 25.1% against production's 6.9%. My read: this is not straightforwardly a
quality signal. Much of 19O–19Q was UI restructuring where a template change
needs several integration tests to pin, and 19R added parity goldens and
query-count guards that are large by line count. The ratio says the suite is
being kept ahead of the code; it does not say the tests are proportionally more
valuable.

**Tests: 4,636 passed, 16 skipped, 0 xfails**, `ruff check .` clean, with `node`
present so `tests/integration/test_inline_scripts_parse.py` ran rather than
skipped. All 16 skips are documented and deliberate — fifteen are Wave 5 PR 5.3
scope retirements, one is the opt-in CSS parity dump. CI runs the same suite
twice, once on SQLite and once against a real `postgres:16` with a full
`downgrade base + upgrade head` round-trip; both green at this SHA.

**Endpoints and schema: 188 route declarations over 79 migrations.** The cold
read says 185; both are right and the difference is definitional — 185 is the
`@router.*` count (120 POST, 63 GET, 1 PATCH, 1 DELETE), and three `@app.get`
declarations in `app/main.py` make 188. They resolve to 109 distinct path
literals.

| LOC | File | Δ |
| --- | --- | --- |
| 1,300 | `app/services/validation.py` | +346 |
| 1,279 | `app/web/routes_operator/_instruments.py` | +15 |
| 1,246 | `app/services/csv_imports.py` | +246 |
| 1,119 | `app/services/assignments/_generate.py` | +355 |
| 1,109 | `app/services/responses/_core.py` | +89 |
| 1,109 | `app/web/routes_operator/_operations.py` | +71 |
| 1,107 | `app/services/session_lifecycle.py` | +1 |
| 1,066 | `app/services/instruments/_band1.py` | +363 |
| 1,061 | `app/web/routes_operator/_shared.py` | +202 |
| 1,049 | `app/web/views/_instruments.py` | +40 |

**The shape is a plateau, and it moved.** Twelve production modules are now at
or above 1,000 LOC. For six consecutive windows the top of this table was flat;
this window it is not — `validation.py` took the top spot from
`_instruments.py` with +346, and three others moved by more than 200. None of
the growth is incoherent: `validation.py`'s is the `ValidationInputs` dataclass
plus 22 rewritten rule signatures, `_generate.py`'s is the reconcile cache's
stamp plumbing, `_band1.py`'s is per-session instrument identity. But the
long-flat plateau tilting in one window is the most diagnostic fact in §2.

**Where the growth landed: on existing seams, almost entirely.** Production
churn for the whole window is **+1 file and −1 file**. One new production
module (`_reconcile_cache.py`) absorbed 287 of +4,086 LOC; the other ~3,800
went onto modules that already existed. Compare `tests` at +60 files and `docs`
at +28. My read: the architecture absorbed six segments without needing a new
seam, which is the good reading, and simultaneously every large module got
larger, which is the cost of that.

**Tooling grew fastest in percentage terms (+36.4%)** — dev-only scripts that
operate on the repo, including the roster-scale bench `tools/bench_roster_scale.py`
that 19R was built on. It ships in no artefact.

**Package shape:** `app/services` 96 modules, `app/web` 69 (of which
`app/web/views` 23 and `app/web/routes_operator` 22), `app/db/models` 21.

**Duplication and churn** (`python3 tools/code_metrics.py`, the standing
quantitative items `guide/README.md` requires every snapshot to record):

| | ≥10-line blocks | prior |
| --- | --- | --- |
| `app/` | 3,234 / 50,977 = **6.3%** | 6.5% |
| `tests/` | 13,420 / 103,478 = **13.0%** | 13.6% |

Churn — Python lines deleted within 14 days of being written, over all 2,531
merges on `main` — is **59,637 of 82,205 (72.5%)** against a same-share baseline
of 68.4%, a **ratio of 1.1×**. Both metrics sit below the thresholds
`guide/README.md` sets for acting on them (duplication rising materially above
the 6.5% `app/` baseline; churn meaningfully above ~1.5×), and both moved
slightly *down* across ten days and 228 merges. A ratio near 1.0 means deletions
are age-blind — the code is simply young — rather than that recent work is being
specifically rewritten.

The duplication that does exist is concentrated and known: the roster route
modules remain the leading cluster at **47% / 42% / 35% / 34% / 28%**
(`_setup_reviewers.py`, `_setup_reviewees.py`, `_setup_observers.py`,
`_setup_relationships.py`, `_quick_setup.py`). 19P gave those five pages one UI
idiom without consolidating their route modules, so the shared shape is now
visible in the numbers. It is deliberate — five near-identical CRUD surfaces
that differ in their entity — and it is the obvious extraction if anyone ever
wants one. No plan.

## 3. Functional-spec compliance

Every row checked against code — a route registered, a service function
present, a test covering it — not against the spec's description of itself.
**Bold rows changed this window.**

| Area | Spec | Status |
| --- | --- | --- |
| Lifecycle (five states) | `spec/lifecycle.md` | ✓ shipped — `session_lifecycle.py` carries activate / revert / close |
| **Assignments engine** | `spec/assignments.md` | ✓ shipped — `replace_assignments` + `staleness_by_instrument`; verdict cached since 19R.2 (2026-09-21) |
| **Validate page** | `spec/validate_page.md` | ✓ shipped — 22 rules in `REGISTERED_RULES`, one `ValidationInputs` per run since 19R.5 |
| **Instruments** | `spec/instruments.md` | ✓ shipped — per-session identity since 19Q.6 |
| **Setup pages** | `spec/setup_pages.md` | ✓ shipped — expander idiom on all four rosters since 19P |
| **Operations pages** | `spec/operations_pages.md` | ✓ shipped — SQL rollups since 19R.3 |
| **Workflow card** | `spec/workflow_card.md` | ✓ shipped — Prepare creates invitations since 19Q.2 |
| Participant model | `spec/participant_model.md` | ✓ shipped — `require_reviewee_in_session` / `require_observer_in_session` |
| Visibility policy | `spec/visibility_policy.md` | ✓ shipped — `resolve_mode` over the 3 × 2 grid |
| Reviewer surface | `spec/reviewer-surface.md` | ✓ shipped |
| CSV contracts + round-trip | `spec/csv_contracts.md`, `spec/roundtrip_coverage.md` | ✓ shipped — `session_config_io` apply/serialize |
| Extracts | `spec/extract_data.md` | ✓ shipped |
| Audit | `spec/architecture.md` | ✓ shipped — `EVENT_SCHEMAS` allowlist, strict in tests |
| Permissions / identity | `spec/permissions.md`, `spec/audience_and_identity_model.md` | ✓ shipped — Easy Auth headers, `ALLOW_FAKE_AUTH` false in deployed envs |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped — render only; nothing sends |
| **Previews hub** | `spec/preview_hub.md` | ✓ retired 19Q.1 — spec is now a retirement notice pointing at the drill-in |
| Email dispatch | `spec/email_infra_options.md` | ⛔ blocked — outbox rows write `queued`; Segment 14B, needs institutional Azure |
| Rehydrate | `spec/rehydrate.md` | ⏸ gated off — `rehydrate_enabled: bool = False` in `app/config.py`; routes exist, flag ships false |
| Blob storage | `spec/blob_storage.md` | ⏸ stub, not built — plan at `guide/segment_18Q_blob.md`, needs a storage account |
| Operator theming | `spec/visual_style_rrw.md` | ⏸ planned — `guide/deferred_consolidated.md` Part A |

**No `⚠ drift` row.** That is a claim, and here is what backs it: 19M swept
history out of the live specs across six batches, 19O Item 7 worked a
sixteen-entry consistency register to closure, and 19R Items 6–8 closed the last
known code-vs-prose divergence (the `stale_generated` family, nine passages in
six files). `tests/unit/test_doc_references.py` and `test_doc_conventions.py`
gate the mechanical part — every anchored backticked repo path in live prose,
every `§N` pointer, the `CLAUDE.md`/`AGENTS.md` twins, and the checks derived
from `app` constants. What they cannot gate is whether a paragraph describes the
rule correctly, which is precisely what 19R Item 6 found nine counterexamples
of. So: no drift I can find, by a method that has demonstrably missed drift
before.

## 4. Strengths

- **Six segments landed in ten days with one new production module.** +4,086
  production LOC across 228 merges, and production file churn of +1/−1. The
  three-layer split plus the `app/web/views/` seam absorbed a roster-UI
  rebuild, a workflow change, an identity change and a performance pass without
  anyone needing to invent a place to put things.
- **The performance work was measured, not guessed, and the measurement
  overturned the hypothesis.** `guide/app_responsiveness.md` set out to find a
  database problem and found that SQL was never more than 9% of any slow page —
  the cost was the rules engine running on page load. 19R Items 1–3 and 5 were
  written against that finding, and the bench re-ran after each. Measured on the
  bench: Session Home 441 ms, Assignments 389 ms, Validate 482 ms, Invitations
  646 ms, Responses 693 ms, lobby at 1,003 sessions 96 ms.
- **Gates that read no Python catch what review misses.** The doc-convention
  tests fail on a dangling backticked path, a stale `§N` pointer, a
  `CLAUDE.md`/`AGENTS.md` divergence, and a `guide/` file with no README row.
  Several 19M–19R slices were caught by them before CI.
- **Two-reader discipline with separate cadences, and the cadence itself was
  measured.** `diff-reviewer` runs per item, `spec-writer` at a close — a split
  made 2026-09-18 after a merge-history audit found the cold read caught real
  defects on code rungs and overclaimed only prose on plan rungs. In this
  window's last two items the readers caught, respectively, a wrong denominator
  and a false claim about when a review had happened. Both were in my prose, not
  in the code.
- **The deferred ledger is used rather than performative.** 1,658 lines across
  three dispositions, and work moves both ways: 19R Item 9 was planned, designed
  over four mock-up rounds, and moved there unbuilt on the author's call, with
  its blocking constraint recorded so a later pick-up starts from the answer.

## 5. Weaknesses

- **Prepare takes 20 seconds at the bench, and it is the one thing not
  comfortable.** `guide/app_responsiveness.md` Finding 4, at 200 × 200 / 80,000
  rows, with 5.7 s at half the roster — climbing steeply, because Prepare
  inserts one ORM object per pair. It is a click with no feedback. **The cold
  read's executive summary does not mention it**, and it is a larger user-facing
  problem than the page times that do get mentioned. There is no plan: the
  measured candidates sit in `guide/app_responsiveness.md`'s "Later candidates"
  and the author has deliberately not turned them into a queue.
- **The plateau tilted.** Twelve modules ≥ 1,000 LOC, and after six flat windows
  four of the top ten moved more than 200 LOC each. `validation.py` at 1,300 is
  the new largest and has no queued split. Cost: the next reader of any of them
  pays for the growth. Filed as a watchlist in §9; no plan, and I think that is
  still right for this window but will not be right for two more.
- **The prose about the work has been wrong more often than the work.** Across
  19R alone: nine wrong descriptions of one rule in six files (Item 6); a
  blast-radius grep whose scope excluded the directories the item was about,
  twice (Item 6); a denominator computed with `--since=<bare date>`, which takes
  its time-of-day from the current clock — the exact bug `tools/pace_audit.py`
  has a helper to prevent (Item 7); and a close that claimed a cold read had run
  *before* the change in the same commit whose body said it was still running
  (Item 8). Every one was caught by a reader or a gate, none by me. Cost: review
  attention spent on records rather than on code. No plan, and I am not sure
  what one would look like.
- **`docs/status.md`'s summary line drifted two items behind** before Item 8's
  cold read caught it — a counter each closing slice is supposed to maintain,
  missed by two consecutive closes. It is fixed, and nothing gates it.
- **Nothing sends email.** Outbox rows write `status="queued"`; Segment 14B is
  the first real transport and is blocked on institutional Azure provisioning.
  The pilot cannot run without it, so this is the gap between "ready" and
  "shippable", and it is not a code problem.

## 6. Bugs and regressions

**No known open bugs at `ed8a69e7`.** What I checked to be able to say that:
0 open pull requests; 0 xfails; all 16 skips read and confirmed as deliberate
scope retirements plus one opt-in dump; both CI tracks green; the 19R plan's
`Status` blocks and the two cold reads from this window, whose findings are all
either fixed or recorded as deferred with a reason.

Worth remembering from the window, because each now has a guard:

- **Five Quick Setup upload routes silently dropped roster CSV friendly labels**
  (19R.4). Parsed, carried to the save call, dropped there — with a 303 and a
  correctly populated roster. Against the pre-fix tree the suite was 6 failed /
  4,602 passed, every failure in the new test file: **nothing in the suite
  noticed**. A router-level gate now requires every POST endpoint taking an
  `UploadFile` to be exercised or carry a written reason.
- **A no-duplicate query guard passed while recognising nothing** (19R.5). It
  attributed queries by splitting a filename on the repo name, which the CI
  runner's `/home/runner/work/<repo>/<repo>/` defeats. The visible symptom was
  six failures; the real one was the main guard passing vacuously. It resolves
  the root from `app.__file__` now and asserts it saw the report at all.
- **A parity golden pinned absolute row ids** (19R.5), which is a SQLite fact,
  not a fact — Postgres sequences do not rewind on rollback, so `ci-postgres`
  failed four of seven cases. The golden pins each row's position now.
- **The Manage Invitations table and Send all disagreed about who was in the
  session** (19Q.2) — two copies of the same join, one filtered and one not.
  One eligibility helper governs every send path now; the monitoring layer's
  duplicate is recorded in the deferred ledger.

## 7. Estimated size upon completion

**Current: production 63,541, templates 29,161** at `ed8a69e7`.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | institutional Azure deployment concluded |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |
| **Projected floor** | **65,221–66,501** | **29,831–30,561** | |

Excludes anything past v1, and excludes every entry in
`guide/deferred_consolidated.md` Parts A and C.

**Reconciliation — the floor was overtaken for a third consecutive window, by
more than ever.** The 11 September snapshot projected a floor of
**61,066–62,346** production and **25,811–26,541** templates. Production is now
**63,541**, past the top of that range by 1,195; templates are **29,161**, past
theirs by 2,620. Neither overrun is scope discovered in the named work: 14B,
Segment 20 and 18Q are all still blocked and unstarted, so their ranges carry
forward unchanged. The whole of it came from work no item list contained on
11 September — six segments that did not exist then.

That is now three windows saying the same thing, and the 10 September snapshot's
reason for replacing a projection with a floor holds: the floor tracks neither
the item count nor the work, only **how much of the work happens to be
production code**. This window is the sharpest case yet — 228 merges and +4,086
production LOC against a floor built entirely from blocked segments. The floor
remains honest about being a floor. It is not a forecast, and a reader should
not use it as one.

## 8. Bottom line

Review Robin Web is feature-complete for a pilot and has been for several
windows; what this window added was **evidence that it holds up under load** and
**a pass over the places where its own records had stopped matching it**. Six
segments closed in ten days with one new production module, 4,636 tests green on
two CI tracks, and every operator page under 700 ms at a 200 × 200 full matrix.
The one live thread is that **nothing sends email** — 14B is blocked on
institutional Azure, and no amount of further local work changes that.

**Recommended next moves, at most three:**

1. **Close Segment 19R and deploy.** It has eight items closed, one deferred,
   and no open items; the plan stays open only because nobody has closed it.
   This is first because every other candidate on the list is a refinement
   whose value is a guess until an institution touches the system — and the
   cold read reached the same conclusion independently from a different
   direction.
2. **Fix Prepare before the pilot, not after.** 20 seconds with no feedback is
   the single worst interaction in the product, it is measured rather than
   suspected, and it is on the critical path of every session. This ranks above
   the file splits because it is user-facing and below deployment because the
   pilot's own rosters will tell you whether 200 × 200 is even the right bench.
3. **Then re-take the bench, not the code.** `guide/app_responsiveness.md`'s
   headline already inverted once this window — "not a database problem" became
   84% SQL on Invitations, because 19R moved the counting into SQL. That
   sentence is a 2026-09-20 fact, not a standing one. The next performance
   question is a query question, and it should be asked of real data.

**Settling the 11 September proposals.** Its §9 was a watchlist with no queued
split, and nothing was proposed beyond it — so there is nothing to mark shipped.
Its §8 recommendation to stop broad local refinement was **not followed**, and
19R is the result: the refinement was measured rather than speculative and found
four real defects, but the recommendation stands and is repeated above as move 1.

## 9. Proposed file splits — watchlist

**Still no split queued, but the seventh window is the first one that moved.**

- **`app/services/validation.py` (1,300 LOC, +346).** **New to this list and now
  the largest production module.** The growth is 19R Item 5's `ValidationInputs`
  dataclass plus `load_validation_inputs` and 22 rewritten rule signatures — a
  coherent addition, not accretion. The seam if it grows: the 22 `_check_*`
  functions are already a registry, so they carve into a `_rules/` sub-package
  cleanly, leaving the orchestrator and `REGISTERED_RULES` in place. Revisit
  past ~1,450.
- **`app/web/routes_operator/_instruments.py` (1,279 LOC, +15).** Seventh
  effectively flat window. Seam unchanged: carve the `/save` payload-parsing
  blocks into a `_save.py` sibling. **121 LOC from its ~1,400 tripwire.**
- **`app/services/csv_imports.py` (1,246 LOC, +246).** New to this list. Per-slot
  import pipelines; the natural carve is per entity, but they share enough
  header-parsing machinery that a split would need a `_headers.py` first.
  Watchlist only.
- **`app/services/session_lifecycle.py` (1,107 LOC, +1).** Third consecutive
  window inside 100 of its ~1,200 tripwire and still no natural seam — the state
  machine is cohesive and splitting it would scatter the transition table.
  **93 LOC away. Watch actively; do not plan.**
- **`app/web/routes_operator/_operations.py` (1,109 LOC, +71).** Carried from
  the 11 September list, where it was new at 1,038. Still a two-page route
  module; the 19R.3 SQL rollups landed in the service layer rather than here,
  which is why the growth is modest. Watchlist only.
- **`app/services/instruments/_band1.py` (1,066 LOC, +363).** The window's
  largest mover. Per-session instrument identity (19Q.6) landed here. Not yet at
  a tripwire, but +363 in one window is the rate to watch rather than the level.

`app/services/instruments/_instrument_crud.py` **leaves this list** at 940 LOC,
having been at 1,044 on 11 September — the only large module that shrank.
