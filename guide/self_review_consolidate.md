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

## Addendum — chip-controlled drop of empty rows on the Data shaper (+ consistency sweep across the metadata / by-instrument cards) (2026-05-30)

> **Why this exists.** The Self-review handling chip slice
> shipped with a conservative-interpretation pin at
> `app/services/extracts/data_shape_extract.py:578`: when a
> per-individual row's only response was the reviewer's own
> self-review, `exclude_self` surfaces the row with empty
> aggregate cells rather than dropping it. The 2026-05-30
> codebase assessment flagged it for revisit.
>
> **The decision.** Generalise away from "auto-fire on
> `exclude_self`" to a separate, operator-controlled chip that
> applies uniformly: by default every relevant row ships
> (including empty ones), and an opt-in chip drops the empty
> ones. The chip handles the Q4 case as a *consequence* of the
> general policy — a self-review-only row under `exclude_self`
> is just one of the cases where the row's accumulator goes
> empty, and the chip closes it without special-casing.
>
> **Why generalise.** The three other extract cards (By
> instrument, Reviewer response metadata, Reviewee response
> metadata) already do chip-controlled empty-row dropping
> through `All assignment rows` / `All reviewers` /
> `All reviewees`. The Data shaper was the odd one out. The
> consistent pattern is "default = surface every relevant
> row; chip OFF drops the empty ones". This addendum brings
> the Data shaper in line *and* relabels the other three
> chips to the two-state cycling-pill semantics so the
> surface reads symmetrically across all four cards.
>
> **Pill plan dropped (2026-05-30).** PR #1651 / #1652 shipped
> a placeholder `Number of data rows: —` pill on each Data
> shape sub-card, on the theory that PR 7 would wire it to a
> live row-count preflight. Walking through the cost in a
> medium-sized session (1,000 reviewers × 5-peer + 5-group
> reviews × 2 fields ≈ 10K assignments + 20K responses)
> exposed the problem: server-rendered counts cost
> ~150-300ms per saved shape per page load, and live JS
> preflight on every chip toggle multiplies the cost further.
> Dropped entirely. The chip's drop is visible at Download
> time (operator sees the file); a lighter-touch snapshot or
> on-demand recount can layer in later if pilot use justifies
> it. PR 7 below now reverts the placeholder pill instead of
> wiring it.
>
> **Chip labels (axis-neutral on Data shaper, axis-aware
> elsewhere).** Two-state cycling pill on each card:
>
> | Card | "Include" state | "Drop empty" state |
> |---|---|---|
> | Data shaper (new) | `All rows` | `Rows with data` |
> | By instrument | `All assignment rows` | `Assignment rows with data` |
> | Reviewer response metadata | `All reviewers` | `Reviewers with responses` |
> | Reviewee response metadata | `All reviewees` | `Reviewees with responses` |

### What the "Drop empty" chip does

`_Acc.is_empty()` ≡ `assigned == 0 and count == 0 and not
fanout_counts`. (`assigned` is the assignment-pool count,
`count` sums numeric / string / other response counts,
`fanout_counts` tracks discrete-value fan-out.)

The decision matrix collapses to one axis (chip on/off), with
`self_review_handling` orthogonal — it just decides which
assignments / responses feed `_Acc`, and the chip handles the
post-filter emptiness uniformly:

| Row scheme \ chip | `All rows` (default) | `Rows with data` |
|---|---|---|
| per_individual | no drop | drop if `_Acc.is_empty()` |
| per_tag_combo | no drop | drop if `_Acc.is_empty()` |
| single-summary | no drop | no drop (always one row, even if empty) |

For `self_review_handling = "both"`: drop only when **both**
`_self` and `_noself` accumulators are empty (the row is
genuinely no-data; opting into `both` doesn't override the
drop policy when there's nothing to show on either side).

Q4 closes by implication: an operator who wants self-review-
only rows dropped under `exclude_self` flips the chip;
otherwise they stay, exactly as today.

### PR ladder

**Four PRs across one focused stretch.** PR 6 shipped
2026-05-30 in #1654; PRs 7-9 remain.

#### PR 6 — `include_empty_rows` column + extract drop + Data shaper chip — **shipped #1654**

**Scope.** Full vertical slice — no silent CSV change. The
chip ships at the same time as the extract pipeline change so
default behaviour stays put and the new behaviour is
operator-driven from day 1.

- `DataShape.include_empty_rows: Mapped[bool]` column, default
  `True`. Alembic migration `d8e4c3a1b5f6` (server_default
  `true`, no backfill needed).
- `DataShapePayload` accepts `include_empty_rows: bool = True`;
  `_validate` allows it; `_serialize` writes it as the 7th CSV
  row per shape; `_apply` parses it.
- `_Acc.is_empty(self) -> bool` predicate in
  `data_shape_extract.py`.
- In `build_shape_rows`, when `shape.include_empty_rows is
  False`, drop body rows whose `_Acc.is_empty()` (per-individual
  / per-tag-combo). On `both`, drop when both halves are empty.
  Single-summary unaffected.
- New scope-row chip on the Data shaper, placed before the
  Self-review handling chip. Two-state cycling pill: `All rows`
  (default) ↔ `Rows with data`. Persists via the existing
  PATCH route.

Q4 closes by implication for any operator who flips the chip.

#### PR 7 — Revert the placeholder row-count pill — **next**

**Scope.** Back out PR #1651 / #1652. The pill was a visibility
surface for a live-preflight slice we've since dropped (see
"Pill plan dropped" callout above). Removing it tightens the
Data shape sub-card surface and avoids carrying a dead
placeholder.

- Remove the `Number of data rows: —` `<span>` from all three
  Data shape sub-card variants (the hidden `<template>` clone
  source, the saved-shape loop, the initial-blank fallback) in
  `app/web/templates/operator/session_extract_data.html`.
- Remove the `.data-shape-row-count` CSS rule from
  `app/web/templates/base.html`.
- Remove `test_data_shape_row_count_pill_renders` from
  `tests/integration/test_extract_data_tab.py`.
- No service, route, or model surface touched.

**Tests.** Existing chip / save / download tests cover the
restored action row. The deleted test is the only one keyed
off the pill's presence.

**Done when.** The action row on every Data shape sub-card
shows only the Save / Edit / Cancel / Delete / +Shape /
Download buttons — no leading pill. Tests pass.

#### PR 8 — Two-state cycling-pill conversion of the three existing chips

**Scope.** UI consistency sweep — no extract-pipeline change.
The three existing single-state ON/OFF toggles on By
instrument / Reviewer response metadata / Reviewee response
metadata become two-state cycling pills with explicit labels
for each state, matching the Data shaper's new chip.

- Template: each of the three chips emits two label strings,
  swapped on click. `aria-pressed` semantics replaced with
  `data-state` mirroring the Self-review handling chip
  pattern.
- JS chip handler: cycle between the two labels on toggle;
  update the chip's `data-state` + the underlying
  query-string-driven download href.
- The chips' underlying URL contract stays the same (`?all=0` /
  `?all_rows=0`) so existing query-param tests still hold.
- Existing chip-render tests update their label expectations
  (one assertion per chip — the new label is the only diff).

**Tests.**
- Each chip's initial render carries both labels in template
  (one visible, one swapped in via JS).
- Toggle flips `data-state` + the visible label.
- Download href reflects the right `?all=0` / `?all_rows=0`
  flip per chip state (regression guard against the existing
  URL contract).

**Done when.** All four extract cards' empty-row-drop chip
reads as a two-state cycling pill with explicit labels for
each state. Surface symmetry across cards.

#### PR 9 — Spec sweep + archive close-out

**Scope.** Doc hygiene only.

- `spec/extract_data.md` *Self-review handling* — update
  the chip vocabulary: drop the Q4 conservative-interpretation
  flag; document the `Drop empty` chip as the general policy
  knob; show the decision matrix above.
- `spec/extract_data.md` — relabel the three existing
  empty-row-drop chips per the table above; note the
  consistency-sweep rationale. Note that the `Number of data
  rows` pill is **not** part of the Data shape sub-card
  contract (the placeholder shipped + reverted; the chip
  exposes the drop intent and the file makes it observable).
- `spec/settings_inventory.md` §9.5 `data_shapes` — add
  `include_empty_rows` row; bump §10 CSV coverage by one
  key.
- This file → `guide/archive/self_review_consolidate.md`
  with an addendum banner: "Addendum shipped 2026-XX-XX
  in PRs #1654 → #NNNN — chip-controlled drop of empty rows
  + cross-card consistency sweep. Pill plan dropped — see
  the Why-this-exists callout for the cost analysis."
- `guide/todo_master.md` — Done entry summarising the
  chip-controlled-drop slice + the consistency sweep + the
  pill drop.
- `guide/codebase_assessment_30may.md` — strike the Q4
  conservative-interpretation flag (the assessment surfaced
  the need; the addendum closes it via PR 6).

**Done when.** The Q4 pin is gone from the codebase
assessment, the spec reflects the new contract (chip-
controlled drop, no pill), and the plan is archived.

### Risks and open questions

1. **Two-state pill semantics on the three existing chips.**
   The current chips are single-state ON/OFF toggles
   (`is-selected` + `aria-pressed="true"` flips off). Moving
   to a two-state cycling pill keeps the same underlying
   `?all=0` / `?all_rows=0` URL contract — only the chip
   label / `data-state` model changes. Existing tests that
   key off `is-selected` / `aria-pressed` need their
   selectors updated; the URL-contract tests are untouched.
2. **Drop is not directly visible until Download.** Without
   the pill, an operator who flips the chip OFF sees no
   immediate indicator that rows will drop — they find out
   when they download the CSV (or compare against the
   `All rows` version). Acceptable for the pre-MVP single
   operator. If pilot use shows this matters, a lighter-
   touch snapshot column (`last_row_count: int | None` set
   on Download) layers in cleanly without per-render cost.
3. **Default direction on `include_empty_rows`.** `True`
   (= "All rows") matches today's behaviour and the metadata
   cards' default. Migration server-default + payload
   default both `True`. No-op for any existing operator.
4. **Cross-card chip label drift.** The three existing
   chips currently surface a single label that's accurate
   in the ON state but ambiguous in the OFF state ("All
   reviewers" with `aria-pressed="false"` reads as "not all
   reviewers"). The two-state cycling pill resolves this by
   surfacing the actual OFF-state label. Acceptable surface
   change; documented in PR 9 spec sweep.

### Sequencing notes

- **Independent of every other queued item** (URL remodel,
  14B, 19, 20). No cross-dependencies.
- **4 PRs across one focused stretch.** PR 6 shipped
  2026-05-30 (#1654); PR 7 reverts the placeholder pill;
  PR 8 sweeps the three existing chips into the cycling-pill
  pattern; PR 9 is docs.
- **PR 7 can ship any time.** The placeholder pill is inert —
  removing it has no functional impact, just tidies the
  surface.
- **PR 8 third** — UI sweep depending only on the cycling-
  pill pattern already in PR 6 as the reference.
- **PR 9 last** — closes Q4 + archives the plan.

### Done when

- Every Data shape sub-card surfaces an `All rows` /
  `Rows with data` cycling-pill chip; default `All rows`.
- Flipping the chip drops rows whose `_Acc.is_empty()` on
  per-individual / per-tag-combo shapes; single-summary
  unaffected; `both` drops only when both halves are empty.
- The placeholder `Number of data rows: —` pill is gone
  from every Data shape sub-card (template, saved-shape
  loop, initial-blank fallback) along with its CSS and
  test.
- The three existing empty-row-drop chips on By instrument
  / Reviewer response metadata / Reviewee response metadata
  read as two-state cycling pills with explicit labels per
  state.
- `spec/extract_data.md`, `spec/settings_inventory.md`, and
  `guide/todo_master.md` reflect the new contracts.
- The Q4 conservative-interpretation flag is gone from
  `guide/codebase_assessment_30may.md`.
- Plan archived to `guide/archive/self_review_consolidate.md`
  with the addendum-shipped banner appended.
