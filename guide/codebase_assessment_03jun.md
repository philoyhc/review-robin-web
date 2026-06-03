# Codebase assessment — 2026-06-03

**As of:** the close of the **observer-side ladder** (the four
clean-up items 13-16 retired, the W17 collation surface body
shipped, the cohort partition refactor, and the Token keys
deanonymization extract) **plus** a Workflow card UX pass that
collapses the 3-row stepper into a single row of ≤ 4 visible
buttons (each at 25% column width, inactive hidden).

Specifically, since the 2026-06-01 snapshot:

- **W17 + W5 observer collation surface (the previously paused
  arc)** shipped 2026-06-02 across PRs #1799 → #1808 (cohort
  materialiser + per-instrument stats builder + participant-
  token helper + by-instrument cohort filter + the collation
  surface body + Band 3 mode tightening + chip-cycle
  tightening + after-release rendering regression test).
- **Observer cohort editor + cohort_rule persistence**
  (PRs #1787 → #1796) — the operator-side cohort match rule
  builder + Cohort column in the Observers table + the
  observer.cohort_rule_assigned audit envelope.
- **Workflow card Row 3 manual buttons** (Release responses /
  Stop releasing responses / Archive session, PR #1810).
- **Observer follow-ups 2026-06-03** (PRs #1812 → #1815) —
  pair_context + cross-roster operand dropped from the cohort
  editor dropdowns, partition-model refactor on the collation
  stats (closes the cross-side OR degeneracy), and
  `participant_tokens.csv` extract shipped as the operator-side
  deanonymization key from the Extract data tab's Token keys
  card.
- **Doc consolidation 2026-06-03** (PRs #1816, #1817, #1818) —
  `guide/observers.md` → `guide/archive/observers.md`,
  `guide/clean_up.md` → `guide/archive/observers_clean_up.md`
  (turned out to be entirely observer-cohort-editor follow-up),
  README + CLAUDE/AGENTS swept for participant-model coverage.
- **Workflow card single-row redesign 2026-06-03** (PRs #1819 →
  #1820) — 3 rows of buttons (10 conceptual slots) → single
  row, ≤ 4 visible per state, 25% width grid, Codex-flagged
  backdated-release-at edge case closed.

All shipped 2026-06-02 → 2026-06-03 (79 merge commits in two
calendar days; ~95 non-merge commits on 2026-06-02 alone, the
shape of a high-cadence single-author + AI-agent stream).
Numbers taken on `main` at `5889a0f`. Citizen project — single
author + AI-agent cadence, not yet pilot-deployed.

A **standalone** snapshot. Prior snapshot
`guide/codebase_assessment_01jun.md` archives alongside this
write-up. Authoritative ship-state lives in `docs/status.md`;
the functional spec audited against is
`guide/archive/functional_spec.md`.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response →
extract → release → observer-collation** loop end-to-end. An
operator creates a review session, uploads rosters of
reviewers, reviewees, *and observers* (when the per-session
toggle is on), optionally adds relationships, configures one
or more instruments through a three-band per-instrument card,
authors a per-instrument visibility policy on a 3 × 2 chip
grid (Reviewer / Reviewee / Observer × Session-ongoing /
Responses-released), **authors per-observer cohort match rules
on the Observers Setup page**, pins assignment rules,
validates, activates, monitors, optionally releases responses
manually + closes + archives. Reviewees see their results at
`/me/sessions/{id}/results` in the operator-picked mode (Raw
/ Anonymized / Summarized aggregates) and tick Acknowledge.
**Observers see their collation surface** at
`/me/sessions/{id}/collation` — per-instrument tables with
distinct-reviewer + distinct-reviewee headcount badges over
the cohort's in-cohort assignment pool, plus a conditional
CSV download (Raw / Anonymized rows / Summarized note).
**Operators decode Anonymized observer tokens** by downloading
`participant_tokens.csv` from the Extract data tab's Token
keys card.

**New since the 01jun snapshot:**

- **W17 + W5 observer collation surface body** (PRs #1799 →
  #1808, 2026-06-02). `/me/sessions/{id}/collation` renders
  per-instrument tables with the cohort's in-cohort
  assignment pool driving stats, plus per-instrument CSV
  downloads at `.../collation/instruments/{instrument_id}.csv`.
  Anonymized downloads swap reviewer + reviewee names for
  per-session opaque tokens (`R-a3f8b2c1` / `E-9d4e7f10`) via
  `app/services/participant_tokens.py` (env salt mixed with
  `session.created_at`). The W16 reviewee `/results`
  aggregate primitives (`summarize_field`) get reused on the
  collation surface as anticipated. Band 3 observer /
  Session-ongoing tightened to None / Summarized only (no
  per-row Raw / Anonymized downloads while session is open).

- **Observer cohort editor** (PRs #1787 → #1796, 2026-06-02).
  Per-observer Cohort match rule editor on the Observers Setup
  page (multi-rule + AND/OR combinator + literal / observer-
  attribute operands), `observers.cohort_rule` JSON column,
  `CohortRuleSet` Pydantic validator, observer.cohort_rule_
  assigned audit event, Cohort column in the Observers table
  with friendly summary, mixed-state detection across multi-
  observer selection, ensureStaleOption JS for legacy saved
  rules.

- **Workflow card Row 3 buttons** (PR #1810, 2026-06-02).
  Release responses · Stop releasing responses · Archive
  session manual overrides for late-stage operator control.
  Backed by `lifecycle.release_responses_now`,
  `stop_responses_release`, and a widened
  `archive_session` (accepts any non-archived state at the
  service layer; chrome gating is separate).

- **Observer cohort partition refactor** (PR #1814,
  2026-06-03). The collation surface's stats rows reformed
  to honour the user's mental model: the cohort rule picks
  out a per-instrument pool of in-cohort assignments, and
  both rows draw from that same pool. New
  `materialize_cohort_assignments(observer, instrument_id)`
  walks via the per-row predicate
  `assignment_matches_cohort` and returns
  `CohortAssignments(assignment_ids,
  distinct_reviewer_count, distinct_reviewee_count)`. Row 1
  + Row 2 share an identical aggregate (one query, one
  summarise per field); they differ only in the distinct-
  count headcount badge. Closes the cross-side OR
  degeneracy + the "Row 2 ignores reviewer side"
  side-specific-filter weirdness in one go.

- **Token keys deanonymization extract** (PR #1815,
  2026-06-03). New `participant_tokens_extract.py`
  service + `GET /sessions/{id}/export/participant_tokens.csv`
  route + Token keys card on the Extract data page + intro-
  card Token keys chip driving `?tokens=0` on the
  responses-bundle URL. Replaces the originally-planned
  paste-a-token widget on the Observers Setup page; same
  deanonymization use case, no per-lookup JS / audit
  machinery. Closes `guide/clean_up.md` item 15 (now
  archived as `guide/archive/observers_clean_up.md`).

- **Cohort editor dropdown tightening** (PRs #1812 + #1813,
  2026-06-03). `pair_context.*` dropped from the left-field
  dropdown; cross-roster `Reviewer:` / `Reviewee:` operands
  dropped from the right-side operand dropdown. Schema +
  per-row predicate still recognise both defensively
  (legacy saved rules degrade to an empty cohort). Closes
  clean_up items 13 + 14 by removing the surface rather
  than implementing the deferred pair-level join.

- **Workflow card single-row redesign** (PRs #1819 + #1820,
  2026-06-03). The three-row layout (prep / run / release-
  overrides) collapsed to a **single row of ≤ 4 visible
  buttons, each at 25% column width**; inactive buttons are
  not rendered. Each of the 10 conceptual button slots
  gates on its own `*_visible` flag computed by
  `views.build_workflow_card_context`. Pruning rules keep
  every state at ≤ 4 visible buttons: Create invites drops
  once `invitations_generated`; Send invites drops once
  `invitations_sent`; Release responses / Stop releasing
  responses share a slot via
  `is_response_release_window_open`; Archive surfaces only
  in `is_expired`. CSS grid (`grid-template-columns:
  repeat(4, 1fr)`) replaces the previous flex row.
  `next-action-body` `min-height` lifted from 3.5em to
  7.5em so the card height stays stable + the single row
  lands at the old run-phase Y position.

- **Doc archives** (PRs #1816 + #1817, 2026-06-03).
  `guide/observers.md` → `guide/archive/observers.md`
  (observer ladder closed). `guide/clean_up.md` →
  `guide/archive/observers_clean_up.md` — every item in
  the original clean_up file turned out to be observer-
  cohort-editor follow-up; renaming + archiving once they
  all closed reads truer than leaving the file in active
  rotation. Cross-references swept across CLAUDE / AGENTS /
  spec/ / app/ docstrings (~30 path updates).

The reviewer + operator surfaces (assignments, instruments,
validate, previews, invitations, responses, extracts) are
otherwise unchanged from the 01jun snapshot.

---

## 2. Size (LOC)

| Area | Files | LOC | Δ from 01jun |
|---|---|---|---|
| `app/` Python (production) | 162 | **52,231** | +1,897 (+3.8%) |
| `app/web/templates/` | 59 | **21,469** | +561 (+2.7%) |
| `tests/` | 240 (161 integration + 67 unit + 12 conftest/helpers) | **83,483** | +4,614 (+5.8%) |
| Alembic migrations | **76** | — | +1 (observer cohort_rule column) |

Test-to-production-Python ratio **~1.60×** (vs ~1.57× on
01jun — still ticking up). **2,546 tests passing**, 17 skipped
(was 2,417 + 17 on 01jun; +129 in two days). Suite **green**
on both the SQLite default and the `postgres:16` CI service;
`ruff` clean.

**Biggest files** (top 10 production Python):

| LOC | File | Δ |
|---|---|---|
| 1,426 | `app/services/assignments.py` | unchanged |
| 1,380 | `app/services/scheduled_events.py` | unchanged |
| 1,361 | `app/services/session_config_io/_apply.py` | unchanged |
| 1,299 | `app/web/routes_reviewer/_surface.py` | unchanged |
| 1,097 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,068 | `app/web/routes_operator/_instruments.py` | unchanged |
| 1,046 | `app/services/session_lifecycle.py` | +18 (W17 release / close / archive helpers) |
| 999 | `app/web/views/_instruments.py` | unchanged |
| 982 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 976 | `app/services/responses/_core.py` | unchanged |

Still **10 files past 800 LOC**, still **3 past 1,300**. The
three Appendix §9 split candidates from 01jun (`assignments.py`
/ `scheduled_events.py` / `session_config_io/_apply.py`) are
unchanged; `session_lifecycle.py` is newly close to the
threshold but doesn't justify a split yet (clean concern
boundaries internally, well-scoped helpers).

The cohort + collation arc almost entirely landed in **new
small modules**: `observer_cohort.py` (303 LOC),
`participant_tokens.py` (87 LOC),
`collation.py` (164 LOC),
`participant_tokens_extract.py` (97 LOC),
`_observer_collation.py` (179 LOC),
`_observers.py` view helpers (98 LOC),
`_collation.py` reviewer route (208 LOC). That's the §12.B
discipline holding — net +1,897 production LOC distributed
across new modules + minor edits to existing files, not
accumulated on the already-big seams.

**Package shape:**

- `app/services/` — **34** modules + **5** sub-packages
  (was 31 + 4; the new modules listed above).
- `app/web/routes_operator/` — **21** slice files (unchanged).
- `app/web/routes_reviewer/` — **8** slice files (unchanged;
  `_collation.py` was already there as a placeholder).
- `app/web/views/` — **18** view adapters (was 16; +
  `_observers.py`, `_observer_collation.py`).
- `app/db/models/` — 20 model files (unchanged; cohort_rule
  is a JSON column on the existing `Observer` model).

---

## 3. Functional-spec compliance

`spec/participant_model.md` is now the active doc covering the
full participant-model behaviour shipped 2026-05-30 →
2026-06-03 — observer roster + cohort match rule editor +
collation surface + Anonymized token swap + Token keys
deanonymization extract. No drift surfaced in the recent doc
sweeps; the cross-cutting README / CLAUDE / AGENTS pass
(PR #1818) explicitly re-aligned the top-of-tree narrative
with shipped behaviour, and the workflow-card spec sweep
(PR #1820) closed the last stale framing inside
`spec/workflow_card.md`.

**§-by-§ summary** of major in-scope items vs current state:

| Functional area | Spec status | Code status |
|---|---|---|
| Operator session CRUD + lifecycle (draft → validated → ready → expired → archived, with manual release window) | Live in `spec/lifecycle.md`, `spec/session_home.md`, `spec/workflow_card.md` | ✓ shipped |
| Reviewer / Reviewee / Relationship / **Observer** rosters | Live in `spec/setup_pages.md`, `spec/csv_contracts.md` | ✓ shipped |
| Instruments (3-band card, group-scoped, page-break / reorder) | Live in `spec/instruments.md` | ✓ shipped |
| Assignment engine (rule-based, Full Matrix default, self-review) | Live in `spec/assignments.md`, `spec/rule_based_assignment.md` | ✓ shipped |
| Reviewer surface (multi-page, sortable, drafts, submit) | Live in `spec/reviewer-surface.md` | ✓ shipped |
| Operator preview / Validate page | Live in `spec/validate_page.md` | ✓ shipped (18 rules) |
| Audit log + listing UI | Live in `spec/architecture.md` | ✓ shipped |
| Extract setup (5–6 CSVs + bundle) | Live in `spec/csv_contracts.md`, `spec/settings_inventory.md` | ✓ shipped |
| Extract data (per-instrument + Reviewer/Reviewee metadata + Data shaper + Token keys) | Live in `spec/extract_data.md`, `spec/csv_contracts.md §2.9` | ✓ shipped (Token keys live 2026-06-03) |
| Per-instrument visibility policy (3 × 2 chip grid; Raw / Anonymized / Summarized × Session-ongoing / Responses-released) | Live in `spec/visibility_policy.md`, `spec/participant_model.md` | ✓ shipped |
| Reviewee `/results` body — all three modes | Live in `spec/participant_model.md §4.1`, `spec/reviewer-surface.md` | ✓ shipped |
| Acknowledge gesture | Live in `spec/participant_model.md` | ✓ shipped |
| **Observer cohort match rule editor + per-observer cohort_rule persistence** | Live in `spec/setup_pages.md` | ✓ shipped (2026-06-02) |
| **Observer `/collation` body** + **partition-model stats** + **cohort-scoped CSV downloads** | Live in `spec/participant_model.md`, `spec/reviewer-surface.md` | ✓ shipped (2026-06-02; partition refactor 2026-06-03) |
| **Operator-side token deanonymization** (`participant_tokens.csv` extract + Token keys card) | Live in `spec/csv_contracts.md §2.9`, `spec/extract_data.md` | ✓ shipped (2026-06-03) |
| **Workflow card single-row layout** (≤ 4 visible buttons per state) | Live in `spec/workflow_card.md` | ✓ shipped (2026-06-03) |
| Email infrastructure (transport, queue, templates) | Stub at `guide/segment_14B_email_infrastructure.md`; spec at `spec/email_infra_options.md` | ⏸ planned |
| Magic-link landings for reviewees / observers | Filed in 14B appendix; design call still pending | ⏸ blocked on `invitations`-extensibility shape |

The participant-model surface that was the previous snapshot's
"in-flight + paused" item is now closed — `spec/participant_model.md`
covers the whole arc, and the four observer follow-ups
(`observers_clean_up.md` items 13-16) are all closed.

---

## 4. Strengths

- **Architectural discipline is still holding through the
  observer arc.** The W17 + cohort + Token keys + Workflow-card-
  redesign + doc-archive stream covered five distinct
  surface concerns and landed across **20+ small PRs** (most
  ≤ 300 LOC) without any single file ballooning. New code
  arrived in new modules; the per-route / per-view / per-service
  package patterns absorbed the growth flatly. The biggest-file
  list is unchanged top-7 from 01jun.
- **The partition-model refactor is a good worked example of
  spec-driven correctness.** The user's "one pool of in-cohort
  assignments" mental model surfaced through conversation,
  led to a per-instrument materialiser + shared-aggregate stats
  builder, and the change landed alongside specs (`spec/participant_model.md`,
  `guide/archive/observers.md`) describing the new shape — not
  drift introduced by the refactor but a model alignment that
  fixed an actual cross-side OR degeneracy bug. The CSV download
  path (already partition-correct per PR #1804) and the surface
  stats now share one predicate.
- **Doc cadence kept up.** Every code PR in this stream was
  paired with spec edits as it landed; the three end-of-arc
  sweep PRs (#1816 + #1818 + #1820) closed the doc-drift
  ledger to zero for the touched surfaces. `guide/` continues
  to trim (2 active files retired to archive this stream:
  `observers.md` and `clean_up.md`), and the archive index
  (`guide/archive/README.md`) stays hand-maintained.
- **Workflow card UX cleanup is meaningful.** Pre-this-stream,
  several states surfaced 5-7 buttons; post-stream, every
  state caps at 4. The chrome reads tighter and the operator's
  attention isn't pulled in five directions in `validated +
  invites drafted`. Codex caught the one residual edge case
  (backdated `responses_release_at` flipping `stop_release_visible`
  in pre-activation), closed in the same PR via a dual-gate.
- **Test density up, no regressions.** +129 tests in two days
  on top of the 211 in the previous two-day stream. No flakes;
  both CI tracks pass. The new tests are concentrated in
  observer-side modules and the workflow-card per-state
  visible-button coverage.

## 5. Weaknesses

- **Three production files in the 1,300+ band, same as 01jun.**
  The §9 Appendix split proposals haven't been actioned;
  nothing in this stream touched them. They remain the natural
  next-housekeeping-window targets:
  1. `app/services/assignments.py` (1,426 LOC) — three cohesive
     concerns (coverage / self-review / generate-reconcile).
  2. `app/services/scheduled_events.py` (1,380 LOC) — rule-
     banner-marked seams between five concerns.
  3. `app/services/session_config_io/_apply.py` (1,361 LOC) —
     per-section appliers + the orchestrator.
  The plan in the 01jun assessment §9 still stands verbatim; no
  rework needed when these are picked up. `session_lifecycle.py`
  (1,046) is newly close but the internal structure is clean
  (lifecycle transitions cluster naturally) so a split isn't
  pressing.
- **The 14B email infrastructure tail is the last truly
  in-flight thing.** W20 (reviewee / observer email
  notifications) and W21 (magic-link landings) are both in
  `guide/segment_14B_email_infrastructure.md`'s appendix. The
  observer arc closed cleanly without these — observers reach
  `/me/sessions/{id}/collation` via the existing Easy Auth
  path. But invite-by-email for non-reviewer audiences is
  the remaining loose thread on the participant-model
  contract.
- **Workflow card's per-state body copy is still generic
  through States 4 – 9.** The State 10 (expired) copy is new
  this stream and reads cleanly; earlier states still use the
  pre-redesign phrasing. Not a regression, but the visible
  Activate / Send invites / Send reminders progression could
  carry richer in-card hints (count pills, "X reviewers
  haven't been invited yet") that today live in the right
  column's status panel. Filed mentally; no plan.

## 6. Bugs and regressions

None known as of `5889a0f`. Codex's review on PR #1819 caught
the one edge case in the workflow-card redesign (backdated
`responses_release_at` flipping Stop visible in pre-activation
states); fix shipped in the same PR with a regression test.
No other bugs surfaced in PRs #1799 → #1820.

## 7. Estimated size upon completion

Updated projection. Today: ~52.2k production Python + ~21.5k
templates + ~83.5k tests. Remaining MVP scope:

- **Segment 14B Part A (email infrastructure activation)** —
  +800-1,200 LOC across `email_outbox`-writer call sites,
  Outbox dispatch helper wiring, the per-backend transports
  (SMTP live, Graph / ACS / generic transactional stubbed).
  Plus the W20 invite-trigger call sites for reviewees /
  observers (+200-300 LOC).
- **W21 magic-link landings** — +400-600 LOC pending the
  schema-shape decision.
- **Segment 19 (spec hygiene)** — small; a cross-cutting
  sweep that produces no production-LOC delta but may add
  a `docs/` runbook or two.
- **Segment 20 (operator polish + documentation)** — Known
  limitations + operator-runbook + Start Here docs. Mostly
  `docs/` content; +500-1,000 prose-LOC, +100-300 production-
  LOC of polish.

Roughly +1.5-2.5k production LOC + +500-800 template LOC +
+1.5-2.5k test LOC to a "feature-complete v1" projected total
of **~54-55k production + ~22-22.5k templates + ~85-86k tests**.
Tracks with the 01jun projection (56-58k production); the
delta is that the observer-collation arc that 01jun budgeted
as a remainder item is now shipped.

## 8. Bottom line

The observer-side ladder shipped end-to-end across two
calendar days at ~40 PRs/day. The "participant-model arc
mostly done — observer collation paused" framing from 01jun
is now closed: cohort editor + cohort_rule persistence +
collation surface body + cohort-scoped CSV downloads +
Anonymized token swap + operator-side Token keys
deanonymization are all live. The cohort-stats render shape
absorbed a model-alignment refactor mid-stream (partition
model, PR #1814) that fixed an actual cross-side OR
degeneracy bug. Plus the Workflow card UX cleanup capped every
state at ≤ 4 visible buttons in a single 25%-grid row.

Doc cadence kept pace: `spec/participant_model.md` /
`spec/setup_pages.md` / `spec/visibility_policy.md` /
`spec/extract_data.md` / `spec/csv_contracts.md` /
`spec/workflow_card.md` all swept in the same window; the
older `guide/observers.md` and `guide/clean_up.md` retired
to archive once their content turned out to be either
historical record (observers.md) or single-purpose (the
clean_up file's items were all observer-cohort-editor follow-
up, hence the `observers_clean_up.md` rename + archive).

**Recommended next moves:**

1. **Land Segment 14B Part A** — the remaining MVP gap. Email
   infrastructure activation is the dependency for W20
   (reviewee + observer notifications) and a real test of the
   magic-link schema shape (W21) under load.
2. **Pick one of the three Appendix §9 file splits** — the
   01jun proposals stand verbatim. `scheduled_events.py` is
   still the most mechanical (rule banners encode the seams);
   `assignments.py` is highest-value since it's still
   top-of-file at 1,426 LOC and clean three-way seam.
3. **Defer Segments 19 + 20** until 14B lands; those are
   "polish for pilot" segments that work best with the email
   path actually live.

---

## 9. Proposed file splits

The three Appendix §9 split candidates from 01jun stand
unchanged:

1. **`app/services/assignments.py` (1,426 LOC)** — split into
   `_coverage.py` / `_self_review.py` / `_generate.py` /
   `_shared.py` under a new `app/services/assignments/`
   package. The three top-of-file concerns are unchanged from
   01jun (coverage / self-review / generate-reconcile); the
   self-review consolidation slice still marks the cleanest
   seam line.
2. **`app/services/scheduled_events.py` (1,380 LOC)** — split
   into `_duration.py` / `_lock.py` / `_activation.py` /
   `_invites.py` / `_reminders.py` / `_shared.py`. Rule-banner
   markers already encode the seams; mechanical split. The
   three integration test files (`test_scheduled_*.py`) survive
   the rename without restructuring.
3. **`app/services/session_config_io/_apply.py` (1,361 LOC)**
   — split into per-applier modules
   (`_apply_session.py` / `_apply_email.py` /
   `_apply_instrument.py` / `_apply_rule_set.py` /
   `_apply_field_label.py` / `_apply_data_shape.py`) plus
   `_parse.py` + `_validate.py`. The orchestrator dispatches
   by section type; per-applier modules are independent.

See the prior assessment (`guide/archive/codebase_assessment_01jun.md`
§9) for the full line-by-line concern tables + the sequencing
recommendation (`scheduled_events` first, `assignments`
second, `session_config_io/_apply` last). No changes to the
plan; the candidates aged exactly as expected — no growth
relative to 01jun, but no new natural split-windows opened
either.
