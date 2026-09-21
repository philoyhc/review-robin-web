# Reconciling assignment regeneration

How `assignments.replace_assignments(...)` materialises `Assignment`
rows from each instrument's rule without destroying saved responses.

## Why a reconcile and not a replace

`Assignment.responses` is `cascade="all, delete-orphan"`, so a
wholesale replace — delete every `Assignment` row for the instrument,
then insert the engine's full pair fan-out — takes **every saved
response** with it, including responses on pairs the re-run produces
again unchanged.

That makes a **binary** confirmation the wrong shape too: offered only
"skip Generate" or "regenerate and lose everything", the operator has no
move for the common mid-cycle case — reverted to draft, **added or
removed a reviewer / reviewee**, wanting the affected pairs generated or
dropped while every unchanged pair keeps its responses. Reconcile is
what makes that case expressible, so neither the wholesale replace nor a
keep-or-lose prompt may come back.

## The reconciling algorithm

`_materialise_one_instrument`
(`app/services/assignments/_generate.py`) **diffs and reconciles**
against the existing rows. Per instrument:

1. Run the engine → a new pair set. Reduce it to
   `N = { (reviewer_id, reviewee_id) }`.
2. Load the existing `Assignment` rows for
   `(session_id, instrument_id)` into `E`, keyed by
   `(reviewer_id, reviewee_id)`.
3. Diff:
   - **`to_insert = N - E`** — newly eligible pairs. Insert one
     `Assignment` row each (current `mode` as `created_by_mode`,
     `include` computed as below).
   - **`to_delete = E - N`** — pairs the rule no longer produces
     (e.g. a removed reviewer, or a relationship change). Delete
     their `Response` rows first, then the `Assignment` rows. The
     order is load-bearing: these are bulk Core `delete`s, which
     bypass the ORM `delete-orphan` cascade, so deleting the
     assignments first leaves the responses behind and breaks the FK.
   - **`to_keep = N ∩ E`** — pairs present before and after. Leave
     the `Assignment` row **and its responses** untouched. Refresh
     `include` in place only if it changed (see below).
4. Emit the `assignments.generated` audit event with reconcile
   counts (see "Audit" below).

A pair's identity is `(reviewer_id, reviewee_id)` within the
`(session_id, instrument_id)` scope — exactly the tuple the
`uq_assignment_unique` constraint already enforces.

## The `include` flag

`_materialise_one_instrument` sets `include` per pair: self-review
pairs take `review_session.self_reviews_active`; all other pairs are
`True`.

**What counts as a self-review is not a pair-level test.** On a
group-scoped instrument the engine applies the **whole-group** rule —
the reviewer reviewing a group they belong to is a self-review for
every member of it, not only for their own row. `spec/assignments.md`
§*Self-review policy* is the contract; this file describes when
`include` is set, not what the rule is.

On reconcile:

- `to_insert` rows compute `include` the same way.
- `to_keep` rows: recompute the expected `include`; if it differs
  from the stored value (operator toggled `self_reviews_active`
  during the pause), `UPDATE` the single column in place. This is
  metadata-only and never touches responses. The expected value is
  `True` for every non-self-review pair, so a row an operator
  inactivated by hand is reset to `True` here too — the
  round-trip gap `spec/roundtrip_coverage.md` records, not a
  self-review-only path.

## `created_by_mode`

`to_keep` rows retain their original `created_by_mode`. `to_insert`
rows get the current run's `mode`.

The engine is the only writer, and `AssignmentMode` has one member, so
every row it inserts carries `rule_based`. The column's own default
covers direct construction only; it must never name a mechanism that
cannot write — a row nobody made by hand may not be labelled as one.

## Reconcile is the only materialisation path

`_materialise_one_instrument` **always** reconciles — there is no
separate "full reset" mode and none is needed:

- For a session with **no responses**, reconcile produces exactly
  the same final `Assignment` set a delete-then-insert would; only
  the SQL differs.
- When the engine output **fully diverges** from the existing rows
  (a reshuffle), `to_keep` is empty, so reconcile deletes
  everything stale and inserts everything new — the same end state
  as a wholesale wipe.

So reconcile strictly subsumes both a wholesale replace and a
hypothetical full-reset option.

## Determinism and random rules

- **Deterministic rules** (Full Matrix, tag predicates): the pair
  set is stable under unrelated edits, so adding one reviewer
  yields a small `to_insert`, an empty `to_delete`, and a large
  `to_keep` — almost every response is preserved. This is the case
  reconcile is built to serve.
- **Seeded-random rules**: changing the engine's input (adding a
  reviewer) can legitimately reshuffle the whole set. Reconcile
  still works — the diff degrades gracefully to a near-complete
  `to_delete` + `to_insert` — but few responses survive. That is
  inherent to what a random rule means; reconcile does not try to
  pin a random rule's output across input changes. Out of scope.

## Audit

`assignments.generated` carries a `counts` payload in reconcile
terms, one event per instrument (`refs.instrument_id`):

- `new` — `len(to_insert)`
- `deleted` — `len(to_delete)`
- `kept` — `len(to_keep)`
- `responses_deleted` — `Response` rows removed with `to_delete`
- `pairs` / `instruments` / `excluded_*`.

`replace_assignments` returns a `(replaced, new)` 2-tuple, where
`replaced` counts the pairs the reconcile **deleted**.

Register any new keys in the `EVENT_SCHEMAS` allowlist
(`app/services/audit.py`) so the strict-mode test gate accepts the
emit. (The `counts` slot is freeform, so the keys above needed no
registry change.)

## The confirmation is impact-driven, not "responses exist"

The confirmation gates on what a run would actually destroy, because
with reconcile the two halves of a keep-or-regenerate prompt have both
lost their meaning: "regenerate" no longer means "lose everything", and
"skip Generate" is near-redundant when reconciling an unchanged roster
produces an empty `to_delete`.

The **Prepare session** button (`POST
/operator/sessions/{id}/workflow/prepare`, which runs Generate → Validate →
`mark_validated`) therefore:

1. Skips the dry-run entirely when `lifecycle.session_has_responses`
   is false — a first preparation has nothing to lose, and this keeps
   the common path off the engine.
2. Otherwise dry-runs the reconcile — engine plus diff per instrument,
   **without writing** — through
   `assignments.reconcile_impact(db, review_session)`, which returns
   the `new` / `deleted` / `kept` / `responses_deleted` counts a real
   run would cause, **aggregated across the session** — the banner is
   the only consumer and asks one question, "what will this cost?".
   A per-instrument shape exists separately as
   `staleness_by_instrument`, which returns
   `dict[int, InstrumentReconcileState]`; a per-instrument preview
   should read that rather than widen this one. `reconcile_impact`
   shares `_diff_one_instrument` / `_load_reconcile_inputs` with
   `replace_assignments`, so the confirmation and the run cannot
   disagree about the diff. `staleness_by_instrument` no longer shares
   the call unconditionally — it may serve a cached verdict — and
   agrees instead because its stamp covers every input the diff reads
   (`spec/assignments.md` § *Staleness*).
3. Runs straight through when `responses_deleted == 0`.
4. 303s to the host page when `responses_deleted > 0`, where the
   Workflow card renders the `prepare_confirm` banner with both counts
   named — *"Preparing will delete N saved responses"* over
   *"Regenerating drops M assignment pairs that the current setup no
   longer produces, along with their saved responses. Responses on
   unchanged pairs are kept."* — and offers **Regenerate & prepare** /
   **Cancel**. Acknowledgement rides back as
   `acknowledge_response_loss=true`; there is no skip-Generate choice,
   because reconcile does not destroy unchanged data.

The engine evaluation is in-memory, and it is **not** cheap at roster
scale: one walk is seconds per instrument on a 1,000 × 1,000 roster, and
this path pays for two — the dry-run and the run. That is accepted
because the dry-run is what makes a destructive write confirmable, and
the confirmation has to come from the same engine the run will use.

**The staleness cache does not apply here.** It caches
`staleness_by_instrument`'s per-instrument verdict against a content
stamp (`spec/assignments.md` § *Staleness*); `reconcile_impact` asks a
different question — the aggregate cost of a run — on a confirmation
path rather than a render, and always walks the engine. Generate
invalidates the cached verdict by writing the fresh one through, so the
Prepare path leaves no stale badge behind it.

## Source-of-truth pointers

- Materialisation: `app/services/assignments/_generate.py`
  (`_materialise_one_instrument`, `replace_assignments`,
  `_diff_one_instrument`, `_load_reconcile_inputs`,
  `reconcile_impact`).
- Rule engine: `app/services/rules/engine.py` (`evaluate`,
  `EvaluationResult`).
- Prepare button + the confirmation detour: `spec/workflow_card.md`
  ("Saved-response confirmation detour"),
  `app/web/routes_operator/_workflow.py`.
- Audit registry: `app/services/audit.py` (`EVENT_SCHEMAS`).
