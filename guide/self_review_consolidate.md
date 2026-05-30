# Self-review consolidation — DB column + canonical helper sweep

> **Shipped 2026-05-30 across PRs #1633 → #1636.** Five-PR
> ladder landed in one day. The canonical
> `Assignment.is_self_review` column is now the single source
> of truth for self-review classification: written at
> assignment-creation time + every edit trigger via
> `assignments.classify_self_review` →
> `recompute_self_review_classification`, consumed by every
> downstream reader (extracts, audit counters, the per-
> instrument Self-review pill + bulk toggle), and gated by the
> `verify_self_review_classification` continuous-gate invariant
> in `replace_assignments` (strict in tests, log + auto-correct
> in production). The whole-group rule from
> `spec/assignments.md` § *Self-review policy* is now applied
> everywhere — including the wide-format By-instrument extract,
> which pre-PR-3 hardcoded `SelfReview = FALSE` on group-scoped
> rows and silently mislabelled every self-review group.
>
> **PR ladder:** #1633 (schema + canonical helper, backfilled
> inert) → #1634 (write paths + 8 recompute hooks) → #1635
> (read sites switched + latent By-instrument bug fixed) →
> #1636 (continuous-gate invariant + spec + plan-doc sweeps) →
> archive close-out.
>
> **Original stub header (created 2026-05-30):** Plans the work
> to consolidate all self-review classification onto a single
> source of truth: a new `Assignment.is_self_review` boolean
> column, written at Assignment-creation time via the canonical
> whole-group rule, consumed by every downstream caller
> (extracts, exclusion machinery, audit counters). Sequenced
> **ahead of** the proposed-2026-05-30 *Self-review handling*
> chip slice (see `guide/extract_data.md`) so the chip can read
> the column from day 1.

## Why this exists

Self-review classification — "is this assignment row a row
where the reviewer is reviewing themselves" — is a first-class
concept in Review Robin (it has spec policy in
`spec/assignments.md` § *Self-review policy*, a UI toggle on
the Assignments page, audit semantics, and now a proposed
extract-time chip). But the *rule* for computing it lives in
**three separate places in code today**, with the wide-format
extract running a fourth, wrong, hard-coded definition:

1. **`is_self_review(reviewer, reviewee)`** in
   `app/services/assignments.py:243` — pair-level helper,
   case-insensitive email match. Correct for
   **individual-scoped** instruments. **Wrong for
   group-scoped** instruments (only flags the `(R, R)` pair,
   misses the other member-assignments in the same
   self-review group).
2. **`_self_review_assignment_ids`** in
   `app/services/assignments.py:282` — the canonical
   whole-group-aware helper. Correct for both kinds.
   Computes the right answer per Segment 13C's whole-group
   rule, now pinned in `spec/assignments.md` *Self-review
   policy* → *Group-scoped instruments — the whole-group
   rule*.
3. **`by_instrument_extract.py:436`** — hardcodes
   `SelfReview = FALSE` for group-scoped rows, bypassing
   both helpers. Latent bug: silently mislabels self-review
   groups in the wide-format CSV.
4. **`responses_extract.py:231`** — uses the pair-level
   helper from #1; correct for individual-scoped rows,
   silently wrong for group-scoped rows.

Every new consumer that needs the answer (extracts, audit
counters, the proposed Self-review handling chip,
hypothetical future analytics) has to pick a helper, and the
wrong choice is easy to make. The pair-level helper is the
shorter name, the easier-to-call one, and the one most
recently-arrived developer will land on. The canonical
helper is correct but has a heavyweight signature (needs
the full assignment + reviewer + reviewee row set + session
context).

**The fix is to compute the answer once, at Assignment
write time, and persist it as a column.** Every downstream
consumer reads the column; no caller ever computes the rule
ad-hoc again.

Beta-state means we can afford to backfill rather than
nuke: the canonical helper already handles every existing
session correctly, so the migration runs it per-session
and writes the result. No data loss.

## Design

### Column

```sql
ALTER TABLE assignments
  ADD COLUMN is_self_review BOOLEAN NOT NULL DEFAULT FALSE;
```

- `BOOLEAN NOT NULL DEFAULT FALSE` so SQLite + Postgres both
  produce the same shape (no nullable booleans anywhere in
  the project per existing convention).
- No index in v1 — `Assignment` is already keyed by
  `session_id + reviewer_id + reviewee_id + instrument_id`
  and the common access pattern (`WHERE session_id = ? AND
  is_self_review = ?`) is satisfied by the existing
  composite index. Add a partial index later if the chip's
  pool-scan turns out hot.

### Write rule

A single public helper sits next to the column:

```python
# app/services/assignments.py
def classify_self_review(
    db: Session,
    *,
    session_id: int,
    rows: Sequence[tuple[Assignment, Reviewer, Reviewee]],
) -> dict[int, bool]:
    """Returns {assignment_id: is_self_review} for the rows.

    Individual-scoped → pair-level email match.
    Group-scoped → whole-group rule (every row in a group
    where the reviewer is a member). Same machinery as
    ``_self_review_assignment_ids`` — that function becomes a
    thin wrapper that returns the ``{id for id, v in
    classify_self_review(...).items() if v}`` set.
    """
```

Both pair-level `is_self_review(r, ree)` and
`_self_review_assignment_ids(...)` stay as **thin
shorthand wrappers** around `classify_self_review` for
backwards-compatibility at callsites; the column is the
source of truth.

### Recompute triggers

The column is derived, so it needs recompute on every event
that can change the answer:

| Trigger | Recompute scope |
|---|---|
| Regenerate assignments (full rebuild) | Trivially correct — every row written fresh. |
| Manual assignment add | Per-row write site computes. |
| Reviewer email change | All `Assignment` rows for that reviewer. |
| Reviewee identifier change (email vs non-email; case) | All `Assignment` rows for that reviewee. |
| Reviewee tag change affecting group composition | Piggyback on the existing `reconcile_group_responses_for_tag_change` reconciliation pass in `app/services/responses/_group_reconciliation.py:296`. Same trigger set. |
| Reviewee added / removed from a group | Same — already routed through the reconciliation pass. |
| Instrument `group_kind` change | All `Assignment` rows on that instrument. |
| Relationship change (when relationships drive group composition) | `reconcile_group_responses_for_relationship_change` in `_group_reconciliation.py:365`. |

The recompute logic for each trigger calls
`classify_self_review` on the affected row scope and
`UPDATE` s any rows whose stored value differs.

### Invariant check

A cheap correctness assertion in the regenerate path:
after regenerate writes every fresh `Assignment`, compute
the column values via `classify_self_review` and compare
against what's actually stored. In tests, fail loudly on
drift. In production, log + correct (don't crash the
operator's regenerate). This catches missed recompute
hooks before they become silent extract bugs.

## PR plan

Five PRs, each small and independently mergeable. Sequenced
so the column is correct and reliable before any reader
switches over. By landing this **before** the
*Self-review handling* chip slice in `guide/extract_data.md`,
the chip can read the column from day 1 instead of paying
for a refactor later.

### PR 1 — Schema + model + canonical helper

**Scope.** Add the column, write the backfill, consolidate
the canonical helper. No callers change yet.

**Files.**

- `app/db/models/assignment.py` — new
  `is_self_review: Mapped[bool]` field.
- New Alembic migration in `alembic/versions/` — creates the
  column (`server_default="false"` for the column metadata
  + `NOT NULL`) and runs the data migration:
  ```python
  # Per-session backfill via the canonical rule.
  for session_id in op.get_bind().execute(
      sa.text("SELECT DISTINCT session_id FROM assignments")
  ).scalars():
      # ... call classify_self_review-equivalent inline, write back.
  ```
  Backfill keeps the column metadata default (`FALSE`) on
  rows the canonical rule says are self-reviews → flips them
  to `TRUE`. Idempotent.
- `app/services/assignments.py` — add public
  `classify_self_review(...)`. Refactor existing
  `_self_review_assignment_ids` to be a thin wrapper.
  `is_self_review(r, ree)` stays as the pair-level
  convenience.

**Tests.**

- `tests/unit/test_classify_self_review.py` — new file
  covering: individual-scoped with email match, individual-
  scoped with case mismatch, individual-scoped with
  non-email identifier, group-scoped with R as a member
  (all member-rows flagged), group-scoped with R not a
  member (no rows flagged), group with composed-name
  reviewee (the `(group)` rendering on the extract row), the
  symmetric reviewer/reviewee self-pair group.
- `tests/migrations/test_self_review_backfill.py` — new
  file or extension to an existing migration test:
  seed a session with a known mix, run the migration,
  assert the column matches what `classify_self_review`
  computes for that session.

**Done when.** Column exists, backfill produces correct
values for every existing session in the test suite, no
caller reads the column.

### PR 2 — Wire write paths + recompute hooks

**Scope.** Make sure every code path that creates or
materially changes an `Assignment` computes and stores the
column. No reader changes.

**Files.**

- `app/services/assignments.py` — the regenerate flow's
  `Assignment(...)` constructor call at line 812 picks up
  `is_self_review=<computed>`.
- Manual-assignment add path (in `assignments.py` — find the
  per-row write site).
- Group fan-out at save time (in
  `app/services/responses/_group_reconciliation.py` —
  `_refan_group_responses` already creates / drops member
  rows; have it write the column on creation).
- Reviewer-email edit site (in
  `app/web/routes_operator/_setup_reviewers.py` →
  whichever service module handles the update).
- Reviewee-identifier edit site (same shape for
  reviewees).
- Instrument `group_kind` edit site (in
  `app/services/instruments/_instrument_crud.py` — the
  group-kind set/unset paths).
- The two existing reconciliation entry points
  (`reconcile_group_responses_for_tag_change` /
  `_for_relationship_change`) grow a self-review-column
  recompute call.

**Tests.** For each trigger, a unit test that:
1. Sets up a session with at least one self-review pair.
2. Triggers the change (rename reviewer's email, edit
   reviewee's tag affecting group composition, etc.).
3. Asserts the affected `Assignment` rows' `is_self_review`
   column matches what `classify_self_review` would return.

**Done when.** Every Assignment write path keeps the
column current; the test suite proves it via the trigger
matrix above.

### PR 3 — Switch read sites to consume the column

**Scope.** Every consumer that asks "is this row a
self-review" reads the column. Fixes the
By-instrument extract bug along the way.

**Files.**

- `app/services/extracts/by_instrument_extract.py:436` —
  drop the `SelfReview = "FALSE"` hardcode for group rows;
  read `assignment.is_self_review` and render `"TRUE"` /
  `"FALSE"` from it. **Latent bug fixed.**
- `app/services/extracts/responses_extract.py:231` — switch
  from `is_self_review(reviewer, reviewee)` (pair-level,
  wrong for groups) to `assignment.is_self_review`.
- `app/services/assignments.py:269`
  (`count_self_reviews_in_assignments`) — switch the
  aggregation to `SELECT COUNT(*) WHERE session_id = ? AND
  is_self_review = TRUE`. Audit-event counters that fed off
  the old function pick up the corrected count for free.
- `_self_review_assignment_ids` callers — if any sites
  benefit from a direct column-read query rather than the
  in-memory helper, switch them. Keep the helper for the
  callers that already have the row tuples in hand.

**Tests.**

- Extend `tests/integration/test_extracts_by_instrument*.py`
  with a group-scoped self-review case asserting the
  `SelfReview` column reads `TRUE` on every member-row of
  the self-review group. This is the bug-fix test.
- Extend the responses-extract tests similarly.

**Done when.** No reader computes self-review on the fly;
the By-instrument bug is gone with a regression test
guarding it.

### PR 4 — Invariant check + sanity sweep

**Scope.** Belt-and-braces against the column going stale
plus a final sweep for missed call sites.

**Files.**

- `app/services/assignments.py` regenerate function —
  after writing every fresh row, call `classify_self_review`
  on the result set and compare to the stored column. In
  tests (via `settings.testing` or equivalent), `assert`
  the match. In production, log a warning + auto-correct.
- `grep -rn "is_self_review\b\|_self_review_assignment_ids"
  app/` audit. Every remaining call site is either:
  - The pair-level helper at a legitimate pair-level
    callsite (rare — most pair-level work has been
    replaced by column reads); document why with a brief
    comment.
  - The canonical helper at a callsite that already has the
    in-memory row tuples (also rare — those callsites can
    usually be replaced by column reads, but keep the
    helper for the ones that can't).
- `spec/assignments.md` *Group-scoped instruments — the
  whole-group rule* — update the closing paragraph: the
  rule lives in `classify_self_review` + the recompute
  hooks, persisted to `Assignment.is_self_review`, and
  every downstream consumer reads the column. The "Known
  gap" admonition retires (bug fixed) — replace it with a
  "consolidated 2026-XX-XX" note pointing back at this
  guide doc.
- `guide/extract_data.md` *Self-review handling in
  summarizing extracts* — the "But there's a known latent
  bug to fix in the same slice while we're here" paragraph
  in the By-instrument card bullet retires; same for the
  forward-pointer in the *Self-review classification*
  paragraph. Replace with "reads the canonical
  `Assignment.is_self_review` column landed by
  `guide/self_review_consolidate.md`."

**Tests.** One CI test that regenerates a known-mix session
and asserts every row's `is_self_review` matches
`classify_self_review`. The invariant runs forever.

**Done when.** The CI gate is in place, every remaining
call site is documented, the spec + the extract-data plan
reflect the new world.

### PR 5 — Archive + close-out

**Scope.** Doc hygiene only.

- This file → `guide/archive/self_review_consolidate.md`
  with a "Shipped 2026-XX-XX → 2026-XX-XX (PRs #NNNN →
  #NNNN)" status banner.
- `guide/archive/README.md` row added; `guide/README.md`
  row removed.
- `guide/todo_master.md` entry — Done entry summarising
  the consolidation.

**Done when.** Consolidation is the codebase's only story
for self-review classification, the docs reflect it, and
the *Self-review handling* chip slice can proceed with the
column as its single source of truth.

## Risks and open questions

1. **Reviewer email change frequency.** Need to confirm
   whether the current product allows post-creation email
   edits on reviewers, and via which route. If the answer
   is "yes via Reviewers Setup page inline edit", PR 2's
   hook there is required. If "no, email is set once at
   create time", PR 2 skips that branch but documents the
   absence.
2. **Reviewee identifier mutability.** Same question for
   reviewees. Reviewee identifier can be non-email (display
   identifier); whether it's editable post-creation needs
   confirmation.
3. **Backfill performance.** On beta-scale data (<100
   sessions, <10K assignments each) this is irrelevant.
   Worth a per-session loop with `session.flush()` between
   sessions so the migration doesn't hold one long
   transaction.
4. **`_refan_group_responses` interaction.** The
   reconciliation function already handles group recompose
   on tag / relationship change. Need to verify it touches
   every `Assignment` row that could shift self-review
   status (specifically: rows where a non-member becomes a
   member of the reviewer's own group, and vice versa).
   Read its scope set before writing PR 2 to confirm.
5. **Column on existing audit-event payloads.** The
   regenerate audit event already records a self-review
   count. Switching it to `COUNT(*) WHERE is_self_review`
   may change the value on group-scoped sessions
   (specifically, those that hit the
   `by_instrument_extract.py:436` bug on the read side).
   Audit-event values are immutable per the event-detail
   contract; the **new** events post-consolidation reflect
   the corrected count. Historical events stand. Worth a
   sentence in the PR 3 description.
6. **Spec drift between PRs.** Land the spec update only in
   PR 4 (after the readers have switched). If we update the
   spec in PR 1, there's a window where the doc claims the
   column is the source of truth but readers still call the
   helpers.

## Sequencing notes

- **Lands before the *Self-review handling* chip slice** so
  the chip reads the column from day 1.
- **Independent of every other queued item** (URL remodel,
  14B, 19, 20). No cross-dependencies.
- **5 PRs across one focused stretch** — at the cadence the
  Extract data slice ran (6 PRs over two days), a
  comfortable two-day window.

## Done when

- Every read path consumes `Assignment.is_self_review`.
- No helper-based ad-hoc computation remains except in the
  thin shorthand wrappers that route to
  `classify_self_review`.
- The By-instrument extract's `SelfReview` column reflects
  the whole-group rule for group-scoped instruments — bug
  fixed, regression test in place.
- A CI invariant proves the stored column matches
  recomputation on every regenerate.
- `spec/assignments.md` *Self-review policy* names the
  column as the source of truth.
- `guide/extract_data.md` *Self-review handling in
  summarizing extracts* drops the bug-fix scope (since the
  chip slice no longer has to fix it).
- Plan archived to `guide/archive/self_review_consolidate.md`.

## Related context

- `spec/assignments.md` *Self-review policy* — the canonical
  rule, recently extended to spell out the whole-group case.
- `app/services/assignments.py:243`, `:282`, `:269` — the
  three current helpers + the count function.
- `app/services/extracts/by_instrument_extract.py:436` — the
  bug the consolidation fixes.
- `app/services/extracts/responses_extract.py:231` — the
  silent group-row miscount the consolidation fixes.
- `app/services/responses/_group_reconciliation.py` — the
  existing reconciliation surface PR 2 piggybacks on.
- `guide/extract_data.md` *Self-review handling in
  summarizing extracts* — the chip slice the consolidation
  unblocks.

## Addendum — attributable-drop on Data shaper per-individual / per-tag-combo rows (2026-05-30)

> **Why this exists.** The Self-review handling chip slice
> shipped with a conservative interpretation pin at
> `app/services/extracts/data_shape_extract.py:578`: when a
> per-individual row's only response was the reviewer's own
> self-review, `exclude_self` surfaces the row with empty
> aggregate cells rather than dropping it. The
> 2026-05-30 codebase assessment flagged it for revisit; PR #1651
> (placeholder `Number of data rows: —` pill on each Data shape
> sub-card) and PR #1652 (flush-left CSS fix) prepared the visible
> surface that makes any drop legible to the operator.
>
> **The decision.** Adopt **attributable drop** — drop rows
> whose `_Acc` accumulator was non-empty under `include_self`
> but went empty under `exclude_self`. Apply to
> `per_individual` and `per_tag_combo` only; never drop on
> `single-summary` (one row, would empty the CSV); never drop
> on `self_review_handling = "both"` (operator opted in to
> seeing both side-by-side views). Wire the per-shape row count
> through to the pill so the drop is visible.

### What "attributable drop" means precisely

Strict drop ("any row with empty `_Acc` post-exclusion") would
turn `exclude_self` into a stealth "All reviewers OFF" toggle —
roster members with no participation at all would also vanish.
Attributable drop targets only the rows where exclusion is the
*cause* of emptiness:

```
keep if include_self_acc.is_empty()                  # no data either way — keep
   or not exclude_self_acc.is_empty()                # data survived — keep
drop if include_self_acc.non_empty()                 # had data
       and exclude_self_acc.is_empty()               # and exclusion removed it
```

`_Acc.is_empty()` ≡ `assigned == 0 and count == 0 and not
fanout_counts`. (`assigned` is the assignment-pool count, `count`
sums numeric / string / other response counts, `fanout_counts`
tracks discrete-value fan-out.)

The decision matrix:

| Row scheme \ chip | `include_self` | `exclude_self` | `both` |
|---|---|---|---|
| per_individual | no drop | **attributable drop** | no drop |
| per_tag_combo | no drop | **attributable drop** | no drop |
| single-summary | no drop | no drop | no drop |

### PR ladder

**Three PRs, target one focused stretch.**

#### PR 6 — Attributable drop in the extract pipeline

**Scope.** `data_shape_extract.py` only. No UI, no spec.

- Add `_Acc.is_empty(self) -> bool` predicate.
- In `build_shape_rows`, when `shape.self_review_handling
  == "exclude_self"` **and** row scheme ∈ {per_individual,
  per_tag_combo}, force both passes to run (currently only
  the requested state runs). Add `include_self`'s
  accumulators as a comparison set; only need them for the
  drop check (don't render them).
- Drop body rows whose `(include_acc, exclude_acc)` pair
  matches the attributable-drop predicate.
- Update `_aggregate_block` callsites — no signature change,
  just gate the row emission upstream.

**Tests.**
- Per-individual + `exclude_self`: reviewer whose only
  response is their own self-review → row dropped; reviewer
  with other-target responses → row kept; reviewer with no
  participation at all → row kept (matches "All reviewers
  ON" semantics on the metadata cards).
- Per-tag-combo + `exclude_self`: tag-combo whose only data
  was self-review → row dropped.
- Per-individual + `include_self`: no drop (regression
  guard).
- Per-individual + `both`: no drop (regression guard).
- Single-summary + `exclude_self`: no drop, even if every
  response was self-review (empty aggregates surface in
  the one row).

**Done when.** The CSV reflects attributable drop. Pill still
ships `—` (PR 7 wires it up). Operator who downloads the file
sees fewer rows than under conservative interpretation but
no visible warning yet — acceptable for one PR's worth of gap
in pre-MVP.

#### PR 7 — Server-rendered row count on the pill + JS live-preflight

**Scope.** Pill goes from placeholder to live counter.

- Add `count_shape_rows(db, session, shape) -> int` in
  `data_shape_extract.py` (re-uses `build_shape_rows` and
  returns `len(rows) - 1`; the extra pass cost is bounded
  since the function caches per-state accumulators).
- `app/web/views/_extract_data.py` adapter: each saved shape
  carries `row_count: int`. Template renders
  `Number of data rows: {{ saved.row_count }}` instead of `—`
  for saved sub-cards.
- New route: `POST /operator/sessions/{id}/data-shapes/preflight`
  taking the same payload shape as `DataShapePayload`
  (axis / slots / scope / self_review_handling), returning
  `{"row_count": N}`. Uses the in-memory `DataShape` shim so
  it doesn't have to be persisted to be counted.
- Page JS: on every chip toggle inside an edit-mode
  sub-card (debounced ~300ms), serialize the active chip
  state to the preflight payload, update the pill text
  with the returned count. Edit-mode pill renders `—` in
  the brief in-flight window.

**Tests.**
- View adapter: saved shape's `row_count` matches
  `count_shape_rows` output.
- Template render: saved sub-card surfaces the live count
  (no longer `—`).
- New preflight route: smoke (`200 OK` + `{"row_count": int}`),
  attributable-drop case (count drops when chip flips to
  `exclude_self`), authorization (non-operator → 403).

**Done when.** Operator sees the per-shape row count update
live as they toggle chips. The attributable drop from PR 6 is
no longer silent — flipping to `exclude_self` visibly
decrements the pill count.

#### PR 8 — Spec sweep + archive close-out

**Scope.** Doc hygiene only.

- `spec/extract_data.md` *Self-review handling* — add a row
  to the decision matrix: per-individual / per-tag-combo +
  `exclude_self` attributable-drop, `both` never drops,
  single-summary never drops. Reference the pill as the
  visibility surface.
- `spec/extract_data.md` — pill is part of every Data shape
  sub-card's surface contract; note the wire-up route.
- This file → `guide/archive/self_review_consolidate.md`
  with an addendum banner: "Addendum shipped 2026-XX-XX
  in PRs #NNNN → #NNNN — attributable drop on Data shaper
  per-individual / per-tag-combo rows + visible per-shape
  row count."
- `guide/todo_master.md` — Done entry summarising the
  attributable-drop slice + the row-count pill.
- `guide/codebase_assessment_30may.md` — strike the Q4
  conservative-interpretation flag (the assessment surfaced
  the need; the addendum closes it).

**Done when.** The Q4 pin is gone from the codebase
assessment, the spec reflects the new contract, and the plan
is archived.

### Risks and open questions

1. **Should the drop be auto-fired or chip-controlled?** The
   two metadata cards already use a chip-controlled drop:
   `entity_metadata_extract.py:564` drops rows whose
   `total_count == 0` when `all_reviewers=False`. Mirroring
   that on Data shaper would mean adding a per-shape "All
   rows" / "Drop empty" chip (default ON, OFF activates the
   drop) instead of auto-firing on `exclude_self`. The
   chip-controlled variant is **more general** (drops
   roster members with no participation too, not only
   self-review-attributable rows) and **more consistent**
   with the metadata cards. The auto-fire variant is
   **simpler** (no new chip, no new persisted column) and
   matches the operator mental model of "Exclude self
   should clean up the self-review-only rows". This
   addendum plans auto-fire per the 2026-05-30 conversation;
   if the chip-controlled approach lands instead, PR 6
   becomes "add `drop_empty_rows` column + scope-row chip"
   and the drop predicate becomes
   `chip on AND acc.is_empty()` (matches metadata-card
   logic exactly). **Revisit before PR 6 lands.**
2. **2× query cost on PR 6.** Always running both passes for
   per-individual / per-tag-combo + `exclude_self` doubles
   the assignment + response query cost for those shapes.
   At beta scale (<10K assignments per session, <1K
   responses) it's negligible; flag if it becomes hot.
3. **Preflight cost on PR 7.** Every chip toggle in an
   edit-mode sub-card fires a preflight POST. Debounce
   300ms (matches the typical extract-data card chip
   debounce). If chip-state churn becomes hot, consider
   caching the accumulator within the request.
4. **Authorization on the preflight route.** Re-uses
   `require_session_operator` like the existing data-shape
   routes; same permission model. Non-operator → 403, same
   as POST / PATCH / DELETE.
5. **Pill on the initial-blank sub-card.** Stays at `—` —
   no validated shape state to count against. Same for
   edit-mode cards mid-toggle (in-flight preflight window).
6. **Test-database `_Acc` empty-state semantics.** Verify
   `_Acc()` (no responses, no assignments) tests as empty
   via `is_empty()` — this is the predicate the drop logic
   keys off, so a regression-guard unit test in PR 6 is
   cheap insurance.

### Sequencing notes

- **Independent of every other queued item** (URL remodel,
  14B, 19, 20). No cross-dependencies.
- **3 PRs across one focused stretch** — pattern matches
  the original 5-PR self-review consolidation cadence.
- **PR 6 ships first** even though it changes CSV output
  silently — the gap is one PR's worth of "operator sees
  fewer rows in download but no visible warning". Pre-MVP,
  single operator, acceptable. Inverting (PR 7 ships first)
  would mean the pill shows pre-drop count, then the
  number jumps when PR 6 lands; equally acceptable but no
  better.

### Done when

- Per-individual / per-tag-combo + `exclude_self` drops
  rows whose only data was the now-excluded self-review.
- `both` / single-summary / `include_self` are unaffected.
- The per-shape row-count pill renders a live integer
  (server-rendered on saved sub-cards; JS-preflight-driven
  on edit-mode sub-cards).
- `spec/extract_data.md` and `guide/todo_master.md`
  reflect the new contract.
- The Q4 conservative-interpretation flag is gone from
  `guide/codebase_assessment_30may.md`.
- Plan archived to `guide/archive/self_review_consolidate.md`
  with the addendum-shipped banner appended.
