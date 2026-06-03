# Segment 18O — Post-participants-model file splits

**Status:** Stub created 2026-06-03. Source: the
[2026-06-03 codebase assessment](codebase_assessment_03jun.md)
§5 "Weaknesses" + §9 "Proposed file splits". Three production
files have sat in the 1,300+ LOC band unchanged since the
2026-06-01 assessment (`assignments.py`, `scheduled_events.py`,
`session_config_io/_apply.py`); a fourth (`_surface.py`)
joined them mid-stream when the reviewer-surface context
builder kept growing under the participant-model rollout. The
observer-side ladder closing 2026-06-03 leaves this the
natural housekeeping window before Segment 14B (email
infrastructure) lands route-heavy bulk on top.

The "18O" number follows the 18-family sequence after 18N; no
prior 18O existed. Mirrors the 18N pattern: a single
housekeeping number collected from the codebase-assessment
watch list, landed as a short sequence of small focused PRs.

## Goal

Four file splits — pure structural cleanup, **no new
features, no new routes or models, no behaviour change.**
Each PR independent of the others; each landable on its own.

Together: ~5,500 LOC redistributed into ~18 small modules of
50–800 LOC each. Net file count grows by ~14; biggest file
post-segment drops from 1,426 to roughly ~700.

## Why a separate segment

- The four candidates are real but small, share the
  "housekeeping" theme with no feature segment, and bundling
  them with feature work would muddy review (per
  `CLAUDE.md`: "Don't bundle independent changes").
- **No new dependencies, no dependents.** Best landed
  *before* Segment 14B (email infrastructure) adds its
  route-heavy bulk — splits hurt more the later they land
  because rebases get harder.
- Mirrors the 17A / 18N precedent: a single housekeeping
  number, short sequence of small PRs.
- The 18N housekeeping pass (PRs #1557 → #1559) is the
  established playbook: package by concern, keep the public
  import surface backward-compatible via the package's
  `__init__.py`, split file sizes broadly equal, no behaviour
  changes. That playbook applies verbatim here.

## Tracks

Four independent tracks, each one file → one package. Order
of execution chosen to minimise merge conflicts (smallest
mechanical seams first).

### Track A — `app/services/scheduled_events.py` (1,380 LOC)

**Most mechanical.** Top-of-file already carries `# ─────`
rule banners marking the seams; no cross-concern function
calls past a small helper set.

| Concern | Lines | Notes |
|---|---|---|
| Duration parsing | 44–95 | `parse_iso_duration` |
| Offset resolution | 99–135 | `_ensure_aware_utc`, `resolve_offset` |
| Locking + observation core | 139–219 | `lock_session`, `observe_scheduled_events` (the entry point) |
| Activation observation + audit | 221–451 | `_observe_scheduled_activation`, `_emit_activation_skipped`, `_emit_activation_retry_or_failed`, `_count_recent_retries` |
| Activation validators | 453–520 | `ScheduledActivateError`, `parse_and_validate_scheduled_activate_at` |
| Invites scheduling | 521–787 | `_resolve_invite_fires`, `_consumed_invite_offset_indices`, `_observe_scheduled_invites`, `_dispatch_pending_invitations` |
| Reminders scheduling | 788–end | `_resolve_reminder_fires`, … |

**Proposed shape:**

```
app/services/scheduled_events/
  __init__.py         # public surface re-exports
  _duration.py        # ~50 LOC — parse_iso_duration + offset resolver
  _lock.py            # ~80 LOC — lock_session + observe_scheduled_events orchestrator
  _activation.py      # ~290 LOC — activation observers + validators + audit emit
  _invites.py         # ~270 LOC — invite resolution + observe + dispatch
  _reminders.py       # ~250 LOC — reminder resolution + observe + dispatch
  _shared.py          # ~40 LOC — _ensure_aware_utc, _count_recent_retries
```

The three integration test files
(`tests/integration/test_scheduled_*.py`) survive the rename
without restructuring — they import via the package's
`__init__.py` which keeps the public function names stable.

### Track B — `app/services/assignments.py` (1,426 LOC)

Three cohesive concerns, plus a tail (`list_*` /
`delete_all_assignments`) that fits cleanly with one of them.
The self-review consolidation slice (2026-05-30) already
exercised the classification block's seam, so the split lines
are well-tested.

| Concern | Lines | Public functions |
|---|---|---|
| **Coverage / staleness / counts + roster queries** — read-only summaries the Validate page + Workflow card + Assignments page consume | 42–254, 1290–end | `reviewer_fields_with_data`, `reviewee_fields_with_data`, `assignment_fields_with_data`, `display_source_presence`, `existing_count`, `included_count_per_instrument`, `existing_count_per_instrument`, `compute_staleness`, `latest_generated_event_per_instrument`, `list_reviewers`, `list_reviewees`, `list_pairs`, `count_pairs`, `delete_all_assignments` |
| **Self-review classification** — the canonical helpers, the recompute invariant, the breakdown reporters | 257–574 | `is_self_review`, `count_self_review_candidates`, `count_self_reviews_in_assignments`, `classify_self_review`, `recompute_self_review_classification`, `verify_self_review_classification`, `self_review_breakdown_per_instrument`, `set_instrument_self_reviews_active` |
| **Generation + reconciliation** — the rule-runner + Full Matrix + diff/materialise + reconcile pipeline | 576–1288 | `bulk_set_assignment_include`, `generate_full_matrix`, `coverage_stats`, `_session_rule_set_to_schema`, `_full_matrix_schema`, `_InstrumentDiff`, `_diff_one_instrument`, `_materialise_one_instrument`, `_ReconcileInputs`, `_load_reconcile_inputs`, `ReconcileImpact`, `reconcile_impact`, `replace_assignments` |

**Proposed shape:**

```
app/services/assignments/
  __init__.py         # public surface re-exports
  _coverage.py        # ~310 LOC — coverage + counts + roster queries (the read-only summaries)
  _self_review.py     # ~320 LOC — classification + recompute + breakdown
  _generate.py        # ~700 LOC — generate + reconcile pipeline
  _shared.py          # ~50 LOC — _is_active, _is_test_env, _apply_pair_search
```

`_generate.py` is the only block over 600 LOC after the
split; it's a single cohesive pipeline (diff → materialise →
reconcile) so further splitting would cut across the
behavioural seam.

### Track C — `app/services/session_config_io/_apply.py` (1,361 LOC)

Already lives in a package. Splits *within* the existing
`session_config_io/` package — per-section applier modules
plus a parse / validate split. Each `_apply_*_kv` handler is
independent (no sibling-applier calls), so the orchestrator
dispatches purely by section type.

| Concern | Lines | Notes |
|---|---|---|
| Public surface + dataclasses | 63–240 | `ApplyError`, `ApplyResult`, `_DisplayFieldSpec`, `_ResponseFieldSpec`, `_InstrumentSpec`, `_RuleSetSpec`, `_FieldLabelSpec`, `_DataShapeSpec`, `_ParsedConfig`, `apply_session_config` entry point |
| Parsing | 276–354 | `_parse_rows`, `_ParseError`, `_route_row` |
| Per-section appliers | 356–671 | `_apply_session_kv`, `_apply_email_kv`, `_apply_instrument_kv` (the biggest single block, 116 LOC), `_apply_rule_set_kv`, `_apply_field_label_kv`, `_apply_data_shape_kv` |
| Cross-row validation + helpers | 672–end | `_cross_row_errors`, `_parse_bool` + other low-level parsers |

**Proposed shape:**

```
app/services/session_config_io/
  __init__.py
  _apply.py             # ~250 LOC — public dataclasses + apply_session_config orchestrator
  _parse.py             # ~120 LOC — _parse_rows + _route_row + _ParseError
  _apply_session.py     # ~60 LOC
  _apply_email.py       # ~30 LOC
  _apply_instrument.py  # ~120 LOC (biggest applier)
  _apply_rule_set.py    # ~35 LOC
  _apply_field_label.py # ~35 LOC
  _apply_data_shape.py  # ~50 LOC
  _validate.py          # ~120 LOC — _cross_row_errors + parsers
```

Bigger file count change than Tracks A / B (six new modules);
each is small and section-scoped. Test-file mapping survives
as long as the public `apply_session_config` entry point stays
in `_apply.py`.

### Track D — `app/web/routes_reviewer/_surface.py` (1,299 LOC)

**Newest entrant** to the 1,300+ club. Grew under the
participant-model arc as the reviewer surface absorbed the
per-page Save / submit / recall / clear handlers + the
context builder absorbed the per-page status + per-group
collapse helpers. Two clear seams:

| Concern | Lines | Functions |
|---|---|---|
| Helpers + context builder | 69–858 | `_load_assignments_with_relations`, `PageStatus`, `_page_status_for_group`, `_session_status`, `GroupCompletion`, `_group_completion`, `_instruments_for_session`, `_pages_for_session`, `_collapse_group_rows`, `_reviewer_row_sort_key`, `_require_session_accepting`, `_surface_context` |
| Route handlers | 860–end | `submit_redirect_url`, `review_surface_default_position`, `review_surface` (GET), `reviewer_save` (POST), `reviewer_save_consolidated` (POST), `reviewer_submit` (POST), `reviewer_recall` (POST), `reviewer_clear` (POST) |

The context builder (`_surface_context`) is itself ~490 LOC —
the single biggest function in the file. It's a candidate
for a third sub-split, but its internal structure is linear
(rows → status → group collapse → sort) so cutting it apart
risks creating cross-imports.

**Proposed shape:**

```
app/web/routes_reviewer/_surface/
  __init__.py         # re-exports router + context builder
  _routes.py          # ~440 LOC — GET + 4 POST handlers + submit_redirect_url
  _context.py         # ~500 LOC — _surface_context + the small loaders it calls
  _status.py          # ~180 LOC — PageStatus + GroupCompletion + status computers
  _group_collapse.py  # ~130 LOC — _collapse_group_rows
```

`_status.py` and `_group_collapse.py` are independent of
the rest — they take inputs, return outputs, no side
effects. `_context.py` and `_routes.py` are the two
biggest modules post-split; both stay under 600 LOC.

The reviewer-surface tests are predominantly integration
tests (~30 files under `tests/integration/test_reviewer_*`);
they import via the route's URL not the module path, so the
split is transparent to them.

## Sequencing

If all four land sooner rather than later, the order that
minimises merge conflicts:

1. **Track A (`scheduled_events.py`)** first — most
   mechanical (rule banners already mark the seams; no
   cross-concern calls). Sets the package-split pattern for
   the others.
2. **Track B (`assignments.py`)** next — three clean blocks;
   the self-review consolidation already exercised the
   classification block's seam.
3. **Track D (`_surface.py`)** third — two-way split is
   straightforward but touches a route module (rather than
   a service module), so the test-coverage check is
   integration-heavier. Best landed before Segment 14B
   adds new POST handlers in the same family.
4. **Track C (`session_config_io/_apply.py`)** last — most
   files touched (six new modules), but each is small once
   split. Leave for the housekeeping window that owns the
   Settings-CSV round-trip story.

Each track is independent — no shared imports between the
four files past the public service surface — so the order
above is a recommendation, not a hard dependency.

## Risks

- **Public-surface re-exports must stay byte-stable.** Every
  caller goes through `from app.services.assignments import
  …` (etc.); the new package's `__init__.py` must re-export
  the same names. This is the standard 18N housekeeping
  pattern; the package-level test fixtures
  (`tests/integration/test_*_routes.py`) catch any
  re-export drift.
- **Hidden cross-concern calls in `_apply.py`.** The
  per-section appliers *should* be independent, but a sneaky
  cross-call could surface during the split. Mitigation:
  the parse → apply → validate orchestrator is the only
  function that dispatches across sections; if any
  `_apply_X_kv` calls `_apply_Y_kv` directly, the split
  needs to factor a shared helper into `_shared.py`.
- **Track D's `_surface_context` ~490 LOC function.** Big
  but linear; the split keeps it in one module
  (`_context.py`) rather than risking cross-cuts. A
  future housekeeping window could break it down further
  if the function grows past ~600 LOC.
- **Merge cost across the four tracks.** Each split touches
  ~1 file; the four together touch 4 files. None of the
  four overlap. The biggest cross-track risk is if
  Segment 14B lands a new route in `_surface.py` between
  Tracks B and D — that route would need to move to the
  new module in the same PR.

## Definition of done

For each track:

- Original single-file module replaced by a same-named
  package (or, in Track C's case, additional siblings in
  the existing package).
- Package `__init__.py` re-exports every public name the
  original module exported.
- Full test suite green on SQLite + Postgres (both CI
  tracks); `ruff` clean.
- No behaviour change observable from any caller —
  no new audit events, no new routes, no new audit
  envelope keys.
- Per-track PR description includes the LOC distribution
  before / after + the function-to-module mapping.

Done for the segment: all four tracks shipped + the
biggest file in the repo back under 800 LOC.

## Cross-references

- `guide/codebase_assessment_03jun.md` §9 — the
  watch-list source.
- `guide/codebase_assessment_01jun.md` §9 (archived) —
  the original three-track plan that this segment
  inherits (the 01jun proposal aged unchanged; Track D
  is the new addition).
- `guide/archive/segment_18N_housekeeping.md` — the
  precedent housekeeping segment whose Track A
  (`_instrument_crud.py` split, 1,928 → 1,052 + siblings)
  is the established playbook.
- `guide/archive/segment_17A.md` — earlier
  housekeeping precedent (smaller scope).
