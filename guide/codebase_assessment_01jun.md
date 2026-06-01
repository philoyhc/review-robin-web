# Codebase assessment — 2026-06-01

**As of:** the close of the **participant-model surface arc** —
from the URL remodel (`/reviewer/` → `/me/`, PRs #1668 / #1669)
through Phase 1 schema + dead-code helpers (PRs #1671 → #1680),
the cross-role lobby + Observer roster + per-session feature
toggles + Band 3 visibility-policy editor + schedule authoring
(PRs #1684 → #1735), and the final wiring tail: reviewee
`/results` body across all three visibility modes (raw +
anonymized + summarized aggregates; PRs #1737 → #1749), the
Acknowledge gesture (W19 / #1750), the lobby sub-row retirement
(#1751), the Observers Quick Setup + Extract Setup round-trip
(W12 + W13 / #1754, #1755), the reviewer `profile_link` Setup
mirror (W11 / #1756), the `sessions_for_user` stub retirement
(L1 / #1757), and the Validate-page reviewee reachability
warning (W8 / #1758). Plus a doc consolidation pass that
retired both `participant_model_prep.md` and the
upgrade / remainder pair into the active or archive tiers
(#1759 → #1762) and a spec sweep against current code (#1763).

All shipped 2026-05-30 → 2026-06-01 (≈90 PRs merged in two
calendar days at the high-PR end of the cadence, atop the
2026-05-30 push that the prior snapshot bookended). Numbers
taken on `main` at `1018cce`. Citizen project — single author
+ AI-agent cadence, not yet pilot-deployed.

A **standalone** snapshot. Prior snapshot
`guide/codebase_assessment_30may.md` archives alongside this
write-up. Authoritative ship-state lives in `docs/status.md`;
the functional spec audited against is
`guide/archive/functional_spec.md`.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response →
extract → release** loop end-to-end, now with the
**participant-model surface arc** mostly live. An operator
creates a review session, uploads rosters of reviewers,
reviewees, *and observers* (when the per-session toggle is on),
optionally adds relationships, configures one or more
instruments through a three-band per-instrument card (Identity
+ Rule slots + Live preview / Response fields), authors a
per-instrument visibility policy for each non-operator
audience (reviewer / reviewee / observer) on a 3 × 2 chip grid
(Session-ongoing × Responses-released), pins assignment rules,
validates (now with a soft warning for reviewees with non-
deliverable identifiers), activates, and monitors. Reviewers
reach a tabular response surface; the operator can release
responses on a stamped datetime window. **Reviewees see their
results** at `/me/sessions/{id}/results` in the operator-picked
mode — Raw (per-reviewer rows, identified), Anonymized (same
table, identification dashed), or Summarized (one aggregate
row with mean/median/min/max for numerical fields, per-choice
frequency + percentage for List, total + average length for
String) — and tick Acknowledge when they've seen the responses.
Observer plumbing is operator-side-complete (Setup page +
Quick Setup slot + Extract row + bundle inclusion + visibility
policy), but the participant-facing `/me/sessions/{id}/collation`
body is **paused** — render shape is still being rethought
(captured in `guide/observers.md`).

**New since the 30may snapshot:**

- **URL remodel** (PRs #1668 / #1669, 2026-05-30) —
  `/reviewer/` → `/me/` aggressive hard rename across ~340
  callsites; the four `routes_reviewer/` router prefixes
  flipped and 16 templates, ~290 test strings, 10 specs all
  swept in two PRs. Single-author beta with no live URLs in
  flight; no compat shim. Plan archived to
  `guide/archive/url_remodel.md`.

- **Participants-model Phase 1 prep — schema + audit allowlist
  + helper stubs** (PRs #1671 → #1680, 2026-05-30 → 2026-05-31).
  Alembic `b3e7d2a4c8f1` shipped the `observers` table,
  `instrument_view_policies` table, `sessions.relationships_enabled`
  / `observers_enabled` toggles, `reviewers.profile_link`,
  `reviewees.results_acknowledged_at`, and the audit-event
  type allowlist. `app/services/participants.py` shipped
  `is_email_identified` + the route deps
  `require_reviewee_in_session` / `require_observer_in_session`.

- **Participant-model surface slices — Phase 2 placeholders +
  Phase 3 wiring (round 1)** (PRs #1684 → #1735, 2026-05-30 →
  2026-05-31). Empty Observers Setup page lit up by W10's CRUD
  + Upload + Operator-actions row + Danger Zone; both
  per-session feature toggles wired end-to-end (Setup-nav
  gating, route guards, lock-on-data); friendly-label
  retirement on reviewee identity slots (Name / Email_or_id /
  Profile); cross-role `/me/` lobby union with the role-pill
  stack folded into the Session cell; per-instrument visibility-
  policy editor (the per-window mode-pair encoding S14
  consolidated into) with operator-side transparency surfaces
  on the reviewer form (per-instrument intro grid) and Band 2
  preview; session-schedule authoring on the Edit / Create
  form (Release-from + Release-until datetimes).

- **Reviewee `/results` body + Acknowledge + lobby trim**
  (PRs #1737 → #1751, 2026-06-01). The reviewee surface gets
  a body for all three visibility modes; the new **summarized
  aggregate render** carries per-data-type primitives that
  the future observer collation surface will reuse. Acknowledge
  card sits bottom-right with a checkbox-gated button, post-ack
  pill in the page header, `reviewee.results_acknowledged`
  audit event, idempotent POST. The participant-lobby's per-
  page sub-row treatment retired; multi-page sessions now show
  just the main row.

- **Observers Quick Setup + Extract Setup + reviewer
  `profile_link` Setup mirror + cleanup + Validate warning**
  (PRs #1754 → #1758, 2026-06-01). Closes the Observers
  round-trip (W12 + W13): Setup page → Quick Setup slot →
  Extract row → bundle. The Quick Setup card's split formula
  flipped from `(N+1)//2` to `N//2` so the right column always
  carries the configuration-style slots (4-slot or 5-slot
  shape depending on `observers_enabled`). Reviewer
  `profile_link` mirrors the reviewee Setup treatment end-to-
  end (W11). L1's `sessions_for_user` stub deleted (~30 LOC
  of dead code gone). The Validate page surfaces a soft
  warning when reviewees have non-deliverable identifiers
  (W8).

- **Doc consolidation + spec sweep** (PRs #1759 → #1763,
  2026-06-01). Two `participant_model_*` docs (`_prep.md`
  retired earlier into `_upgrade.md`'s Appendix A; the
  `_upgrade.md` + `_remainder.md` pair archived as the surface
  work landed). Residual tail dispersed: W20 / W21 + magic-link
  schema into the `segment_14B_email_infrastructure.md`
  appendix; W5 / W17 + the open questions blocking observer
  collation into the new `guide/observers.md` stub (paused).
  Spec sweep aligned nine spec files with shipped behavior
  (Reviewers `PhotoLink` extract column, five-slot Quick Setup,
  Observers extract details, W8 rule count, lifecycle
  consumer notes).

The reviewer + operator surfaces are otherwise unchanged from
the 30may snapshot.

---

## 2. Size (LOC)

| Area | Files | LOC | Δ from 30may |
|---|---|---|---|
| `app/` Python (production) | ~155 | **50,334** | +4,114 (+8.9%) |
| `app/web/templates/` | 80+ | **20,908** | (steady — most net delta in this stream is route + service code) |
| `tests/` | 210 (152 integration + 58 unit) | **78,869** | +6,323 (+8.7%) |
| Alembic migrations | **75** | — | +5 vs 30may (the participant-model Phase 1 + S12 + S14 expand/contract pair) |

Test-to-production-Python ratio **~1.57×** (steady).
**2,417 tests passing**, 17 skipped (was 2,206 on 30may; +211
in two days). Suite **green** on both the SQLite default and
the `postgres:16` CI service; `ruff` clean.

**Biggest files** (top 10 production Python):

| LOC | File |
|---|---|
| 1,426 | `app/services/assignments.py` |
| 1,380 | `app/services/scheduled_events.py` |
| 1,361 | `app/services/session_config_io/_apply.py` |
| 1,299 | `app/web/routes_reviewer/_surface.py` |
| 1,097 | `app/services/instruments/_instrument_crud.py` |
| 1,068 | `app/web/routes_operator/_instruments.py` |
| 999 | `app/web/views/_instruments.py` |
| 982 | `app/web/routes_operator/_quick_setup.py` |
| 976 | `app/services/responses/_core.py` |
| 966 | `app/services/instruments/_response_fields.py` |

**10 files past 800 LOC** (down from 16 on 30may), **2 past
1,300** (down from 4 past 1,150 on 30may). The 18N housekeeping
splits + the additive nature of this stream (a lot of new code
arrived in small modules — `_setup_observers.py`,
`_extract_data.py`, `_reviewee_results.py`,
`observers_extract.py`, `visibility_policies.py`) shifted the
distribution flatter. The new package patterns from 18N
(`responses/`, `instruments/`, `extracts/`) absorb a meaningful
share of the growth.

**The package count** (`app/services/`) climbed to 31 modules
+ 4 sub-packages; `app/web/routes_operator/` has 21 slice
files; `app/web/views/` has 16 view adapters; `app/db/models/`
has 20 model files. Visible architectural coherence — almost
every surface change in the last two days touched 3-6 files
in the standard route → view → service → template fan-out
without churning the seams.

---

## 3. Functional-spec compliance

The functional spec (`guide/archive/functional_spec.md`) is
fully shipped for everything in scope; the participant-model
upgrade explicitly **extended the functional spec's surface**
during this stream (the spec itself is 2026-05-11 vintage),
and `spec/participant_model.md` is now the active doc covering
the post-upgrade behavior. **Spec-vs-code drift** was the
explicit subject of PR #1763's spec sweep, which aligned 9
files; no remaining alignment errors known.

**§-by-§ summary** of major in-scope items vs current state:

| Functional area | Spec status | Code status |
|---|---|---|
| Operator session CRUD + lifecycle | Live in `spec/lifecycle.md`, `spec/session_home.md` | ✓ shipped |
| Reviewer / Reviewee / Relationship / **Observer** rosters | Live in `spec/setup_pages.md`, `spec/csv_contracts.md` | ✓ shipped |
| Instruments (3-band card, group-scoped, page-break / reorder) | Live in `spec/instruments.md` | ✓ shipped |
| Assignment engine (rule-based, Full Matrix default, self-review) | Live in `spec/assignments.md`, `spec/rule_based_assignment.md` | ✓ shipped |
| Reviewer surface (multi-page, sortable, drafts, submit) | Live in `spec/reviewer-surface.md` | ✓ shipped |
| Operator preview / Validate page | Live in `spec/validate_page.md` | ✓ shipped (18 rules; W8 added) |
| Audit log + listing UI | Live in `spec/architecture.md`, retired catalog at `unfinished_business.md` | ✓ shipped |
| Extract setup (5 CSVs + bundle) | Live in `spec/csv_contracts.md`, `spec/settings_inventory.md` | ✓ shipped (Observers + bundle as of W13) |
| Extract data (per-instrument + Reviewer/Reviewee metadata + Data shaper) | Live in `spec/extract_data.md` | ✓ shipped |
| Per-instrument visibility policy (3 × 2 chip grid; Raw / Anonymized / Summarized × Session-ongoing / Responses-released) | Live in `spec/visibility_policy.md`, `spec/participant_model.md` | ✓ shipped (W15) |
| **Reviewee `/me/sessions/{id}/results` body — all three modes** | Live in `spec/participant_model.md §4.1`, `spec/reviewer-surface.md` | ✓ shipped (W16 / this stream) |
| **Acknowledge gesture** | Live in `spec/participant_model.md` | ✓ shipped (W19 / this stream) |
| Email infrastructure (transport, queue, templates) | Stub at `guide/segment_14B_email_infrastructure.md`; spec at `spec/email_infra_options.md` | ⏸ planned |
| **Observer `/collation` body** | Stub at `guide/observers.md`; design rationale archived at `guide/archive/participant_model_upgrade.md` §7 | ⏸ **paused** (use scenarios under review) |
| Magic-link landings for reviewees / observers | Filed in 14B appendix; design call still pending | ⏸ blocked on `invitations`-extensibility shape |

Everything else lives in `docs/status.md` (the authoritative
ship-state).

---

## 4. Strengths

- **Surface-by-surface architectural discipline holds.** The
  participant-model arc forced 11 distinct surface touchpoints
  (Setup-Observers, Quick Setup card, Extract Setup card,
  Band 3 visibility editor, reviewer surface transparency,
  Validate, Edit / Create form, `/me` lobby, `/me/sessions/{id}/results`,
  Setup-Reviewers form, plus the new audit emitters). Almost
  every surface landed by editing the **same** small set of
  files (route → view → service → template → tests) without
  cross-cutting churn. The §12.B refactor + 17A / 18N
  housekeeping continue to pay off.
- **Reuse cleanly across the visibility-modes stream.** The
  reviewee `/results` summarized aggregate primitives
  (`_summarize_field`) were designed to be reusable; they're
  already cited as the future home of W17's observer-collation
  aggregate semantics. The W15 visibility-policy editor +
  resolver carry across reviewer / reviewee / observer
  audiences with one code path.
- **Test density up, no regressions.** +211 tests in two days
  (≈ 70 lines of new tests per merged production-line)
  without flakes; both the SQLite default and the
  `postgres:16` CI service pass cleanly on every PR. The
  test-to-production-Python ratio holds at ~1.57×.
- **Docs disciplined alongside code.** The
  `participant_model_*` consolidation (3 docs → 0 active +
  2 archived + 1 new stub + 1 14B appendix) closed out a
  multi-phase plan in a way that leaves the design rationale
  preserved in archive while the active docs point at what's
  next. `guide/` has trimmed from 11 active files to 10
  (one retire, one create, two archive); `spec/` is at 32
  files and aligned with code as of PR #1763.

## 5. Weaknesses

- **The participant-model arc isn't fully done.** Three of the
  21 W-items still pending:
  - **W17 / W5 — observer collation surface body** (paused
    while use scenarios are rethought; `guide/observers.md`
    is the home).
  - **W20 — reviewee / observer email notifications**
    (gated on Segment 14B's email infrastructure; filed in
    that segment's appendix).
  - **W21 — magic-link landings for reviewees / observers**
    (blocked on the `invitations`-extensibility design call).
  These are tracked in their specific homes rather than a
  central remainder doc.
- **Top three files are now in the 1,300+ band.**
  `assignments.py` (1,426), `scheduled_events.py` (1,380),
  `session_config_io/_apply.py` (1,361). The first two are
  cohesive but the splits the 18N housekeeping applied to
  `_instrument_crud.py` / `responses.py` could be applied to
  `assignments.py` next — it has clear seam lines (the
  rule-runner + the recompute helpers + the manual-add path).
- **Spec/code split lives in two places for the reviewee
  `/results` body.** Per the spec-writer's #1763 report,
  `spec/participant_model.md §4.1` carries the per-mode
  aggregate semantics while `spec/reviewer-surface.md` carries
  the route contract. Intentional split, but a casual reader
  has to know to look in both. No fix planned today; flag for
  future consolidation if the surface grows.

## 6. Bugs and regressions

None known as of `1018cce`. The 2026-05-30 stream's most
recent latent-bug catch (the `by_instrument_extract.py` 18N PR
3 `SelfReview = FALSE` hardcode on group-scoped rows) was
fixed in that stream. No new bugs surfaced or flagged in PRs
#1737 → #1763. Suite green; production routes serve.

## 7. Estimated size upon completion

Updated projection. Today: ~50.3k production Python + ~21k
templates + ~79k tests. Remaining unscheduled / paused work
within the participant-model surface:

- **W17 / W5 observer collation surface body** — best estimate
  +500-700 production LOC + ~300 test LOC for a sketch
  comparable to W16's reviewee `/results` body (the aggregate
  primitives reuse and the cross-reviewee axis flip are the
  novel surface).
- **W20 reviewee / observer email notifications** — small;
  +200-300 LOC mostly in `email_outbox`-writer call sites once
  14B Part A lights up the pipeline.
- **W21 magic-link landings** — depends on the schema-shape
  decision; +400-600 LOC in `invitations` plus a landing
  handler.

Plus the four remaining MVP segments (14B, 19, 20, plus the
operator polish + Known limitations docs from segment 20).
Roughly +5-7k production LOC + +1-2k template LOC + +6-8k
test LOC to a "feature-complete v1" projected total of
~56-58k production + ~22-23k templates + ~85-89k tests. Tracks
with the prior snapshot's 60k projection.

## 8. Bottom line

The participant-model surface arc shipped end-to-end across
two calendar days at ~45 PRs/day. Reviewees can now see their
results in any of the three operator-chosen visibility modes,
acknowledge them, and the operator can configure the policy +
the schedule + the per-audience visibility on top of the
shipped roster of observers. Observer roster plumbing is all
operator-side-complete; the participant-facing collation body
is deliberately paused. The cleanup pass (L1 stub retirement,
participant-model doc consolidation, spec sweep) leaves the
docs aligned with code and the residual work filed in homes
that match the work's actual dependency boundaries (14B for
the email + magic-link tail, `observers.md` for the design-
question parked items).

**Recommended next moves:**

1. **Land Segment 14B Part A** when ready — unblocks W20 *and*
   gives a real test of the magic-link schema shape (W21)
   under load.
2. **Reopen W17 / W5 design** when the use-scenario rethink
   completes. `guide/observers.md` captures the open
   questions; the W16 stream's aggregate primitives mean the
   implementation is the smaller half of the work.
3. **Split `assignments.py`** at ~1,426 LOC in a 17A / 18N-
   style housekeeping pass before it crosses 1,500.

---

## 9. Proposed file splits

The 18N housekeeping pass (PRs #1557 → #1559) is the established
playbook: package by concern, keep the public import surface
backward-compatible via the package's `__init__.py`, split file
sizes are broadly equal, no behavior changes. Three production
files are at or near the threshold where the same treatment
pays off.

### Candidate 1 — `app/services/assignments.py` (1,426 LOC)

Top-of-file structure scans as **three cohesive concerns**:

| Concern | Lines | Public functions |
|---|---|---|
| **Coverage / staleness / counts** — read-only summaries the Validate page + Workflow card consume | 42–254 | `reviewer_fields_with_data`, `reviewee_fields_with_data`, `assignment_fields_with_data`, `display_source_presence`, `existing_count`, `included_count_per_instrument`, `existing_count_per_instrument`, `compute_staleness`, `latest_generated_event_per_instrument` |
| **Self-review classification** — the canonical helpers, the recompute invariant, the breakdown reporters | 257–574 | `is_self_review`, `count_self_review_candidates`, `count_self_reviews_in_assignments`, `classify_self_review`, `recompute_self_review_classification`, `verify_self_review_classification`, `self_review_breakdown_per_instrument`, `set_instrument_self_reviews_active` |
| **Generation + reconciliation** — the rule-runner + Full Matrix + diff/materialise + reconcile pipeline | 576–end | `bulk_set_assignment_include`, `generate_full_matrix`, `coverage_stats`, `_session_rule_set_to_schema`, `_full_matrix_schema`, `_InstrumentDiff`, `_diff_one_instrument`, `_materialise_one_instrument`, `_ReconcileInputs`, …reconcile + regenerate paths |

**Proposed shape:**

```
app/services/assignments/
  __init__.py         # re-export public surface (backwards compat)
  _coverage.py        # ~250 LOC — coverage + staleness + counts
  _self_review.py     # ~320 LOC — classification + recompute + breakdown
  _generate.py        # ~600–700 LOC — generate + reconcile pipeline
  _shared.py          # ~50 LOC — small helpers (_is_active, _is_test_env)
```

**Why now:** all three concerns have grown independently; the
generate-reconcile pipeline keeps adding behavior (the 15D
rule-runner, the 18H reconcile passes, the W4 / 15B per-
instrument scoping); the self-review consolidation slice
(2026-05-30) tripled the classification block in one PR. Splits
on natural seams; no cross-concern function dependencies past
the few small helpers.

### Candidate 2 — `app/services/scheduled_events.py` (1,380 LOC)

The 18G scheduler. Top-of-file already carries `# ─────` rule
banners between **five marked concerns**:

| Concern | Lines | Notes |
|---|---|---|
| **Duration parsing** | 44–95 | `parse_iso_duration` |
| **Offset resolution** | 99–135 | `_ensure_aware_utc`, `resolve_offset` |
| **Locking + observation core** | 139–219 | `lock_session`, `observe_scheduled_events` (the entry point) |
| **Activation observation + audit** | 221–451 | `_observe_scheduled_activation`, `_emit_activation_skipped`, `_emit_activation_retry_or_failed`, `_count_recent_retries` |
| **Activation validators** | 453–520 | `ScheduledActivateError`, `parse_and_validate_scheduled_activate_at` |
| **Invites scheduling** | 521–787 | `_resolve_invite_fires`, `_consumed_invite_offset_indices`, `_observe_scheduled_invites`, `_dispatch_pending_invitations` |
| **Reminders scheduling** | 788–end | `_resolve_reminder_fires`, …  |

**Proposed shape:**

```
app/services/scheduled_events/
  __init__.py         # public surface
  _duration.py        # ~50 LOC — parse_iso_duration + offset resolver
  _lock.py            # ~80 LOC — lock_session + observe_scheduled_events orchestrator
  _activation.py      # ~290 LOC — activation observers + validators + audit emit
  _invites.py         # ~270 LOC — invite resolution + observe + dispatch
  _reminders.py       # ~250 LOC — reminder resolution + observe + dispatch
  _shared.py          # ~40 LOC — _ensure_aware_utc, _count_recent_retries
```

**Why now:** each section is cohesive and the rule-banner
markers already encode the seam lines — the split is mostly
mechanical. The activation / invites / reminders blocks have
distinct test files already (`tests/integration/test_scheduled_*.py`),
so the test-file mapping survives without renaming.

### Candidate 3 — `app/services/session_config_io/_apply.py` (1,361 LOC)

The Settings-CSV importer. Top-of-file dataclasses + `apply_session_config`
+ a stack of `_apply_*_kv` per-section handlers.

| Concern | Lines | Notes |
|---|---|---|
| **Public surface + dataclasses** | 63–240 | `ApplyError`, `ApplyResult`, `_DisplayFieldSpec`, `_ResponseFieldSpec`, `_InstrumentSpec`, `_RuleSetSpec`, `_FieldLabelSpec`, `_DataShapeSpec`, `_ParsedConfig`, `apply_session_config` entry point |
| **Parsing** | 276–354 | `_parse_rows`, `_ParseError`, `_route_row` |
| **Per-section appliers** | 356–671 | `_apply_session_kv`, `_apply_email_kv`, `_apply_instrument_kv` (the biggest single block, 116 LOC), `_apply_rule_set_kv`, `_apply_field_label_kv`, `_apply_data_shape_kv` |
| **Cross-row validation + helpers** | 672–end | `_cross_row_errors`, `_parse_bool` + other low-level parsers |

**Proposed shape:**

```
app/services/session_config_io/
  __init__.py
  _apply.py           # ~250 LOC — public dataclasses + apply_session_config orchestrator
  _parse.py           # ~120 LOC — _parse_rows + _route_row + _ParseError
  _apply_session.py   # ~60 LOC
  _apply_email.py     # ~30 LOC
  _apply_instrument.py # ~120 LOC — the biggest applier
  _apply_rule_set.py  # ~35 LOC
  _apply_field_label.py # ~35 LOC
  _apply_data_shape.py # ~50 LOC
  _validate.py        # ~120 LOC — _cross_row_errors + parsers
```

**Why this shape:** each `_apply_*_kv` handler is independent
(a section's apply doesn't call sibling appliers). The
orchestrator dispatches by section type. Splitting per-applier
makes the import-time surface of each concern small + lets
section-specific tests target a single module.

### Sequencing

If these all land sooner rather than later, the order that
minimizes merge conflicts:

1. **`scheduled_events.py`** first — most mechanical (rule
   banners already mark the seams; no cross-concern calls).
2. **`assignments.py`** next — three clean blocks; the
   self-review consolidation already exercised the
   classification block's seam.
3. **`session_config_io/_apply.py`** last — most files
   touched (six new modules) but each is small once split;
   leave this for the housekeeping window that owns the
   Settings-CSV round-trip story.

Together: ~4,200 LOC redistributed into ~16 modules of 50–700
LOC each. Net file count grows by ~13; biggest file post-split
drops from 1,426 to ~700. Tracks with the 18N housekeeping
results (`_instrument_crud.py` 1,928 → 1,052; `responses.py`
1,444 → `_core.py` 976 + `_group_reconciliation.py`).
