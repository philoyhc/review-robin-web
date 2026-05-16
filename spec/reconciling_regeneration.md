# Reconciling assignment regeneration

**Status: proposed.** The code does not implement this yet. This
file is the target contract for a follow-up to PR #1066.

## Problem

`assignments.replace_assignments(...)` materialises `Assignment`
rows from each instrument's pinned rule. Its per-instrument worker,
`_materialise_one_instrument` (`app/services/assignments.py`), does
a **wholesale replace**: delete every `Assignment` row for the
instrument, then insert the engine's full pair fan-out. Since
`Assignment.responses` cascades, that delete takes every saved
response with it.

PR #1066 guarded the super-button against this with a binary
confirmation:

- **Activate without regenerating** (`regen_choice=keep`) — skip
  Generate entirely.
- **Regenerate & activate** (`regen_choice=regenerate`) — run the
  wholesale replace, deleting *every* response.

Neither choice serves the common mid-cycle case: the operator
reverted to draft, **added or removed a reviewer / reviewee**, and
wants the affected pairs generated or dropped while every unchanged
pair keeps its responses. Today that operator must either lose all
responses or skip generation (and never get the new pairs).

## The reconciling algorithm

Replace the wholesale delete-then-insert in
`_materialise_one_instrument` with a **diff-and-reconcile** against
the existing rows. Per instrument:

1. Run the engine as today → a new pair set. Reduce it to
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
     their `Response` rows first, then the `Assignment` rows —
     reusing the FK-safe delete order from PR #1065.
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
pairs (`is_self_review(reviewer, reviewee)`) take
`review_session.self_reviews_active`; all other pairs are `True`.

On reconcile:

- `to_insert` rows compute `include` the same way.
- `to_keep` rows: recompute the expected `include`; if it differs
  from the stored value (operator toggled `self_reviews_active`
  during the pause), `UPDATE` the single column in place. This is
  metadata-only and never touches responses. Non-self-review pairs
  are always `include=True`, so only self-review `to_keep` pairs
  can ever change.

## `created_by_mode`

`to_keep` rows retain their original `created_by_mode`. `to_insert`
rows get the current run's `mode`.

## Reconcile is the only materialisation path

`_materialise_one_instrument` should **always** reconcile — there
is no separate "full reset" mode and none is needed:

- For a session with **no responses**, reconcile produces exactly
  the same final `Assignment` set as today's delete-then-insert;
  only the SQL differs.
- When the engine output **fully diverges** from the existing rows
  (a reshuffle), `to_keep` is empty, so reconcile deletes
  everything stale and inserts everything new — the same end state
  as a wholesale wipe.

So reconcile strictly subsumes both the old wholesale replace and a
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

`assignments.generated` keeps its envelope but its `counts` payload
changes from the wholesale `new` / `replaced` pair to reconcile
terms:

- `new` — `len(to_insert)`
- `deleted` — `len(to_delete)`
- `kept` — `len(to_keep)`
- `responses_deleted` — `Response` rows removed with `to_delete`
- `pairs` / `instruments` / `excluded_*` — unchanged.

Register any new keys in the `EVENT_SCHEMAS` allowlist
(`app/services/audit.py`) so the strict-mode test gate accepts the
emit.

## Super-button confirmation

With reconcile, the binary keep / regenerate confirmation from
PR #1066 is no longer the right model:

- "Regenerate" no longer means "lose everything" — it preserves
  every unchanged pair's responses.
- "Keep" (skip Generate) becomes nearly redundant: reconciling a
  session with no roster/rule change produces an empty `to_delete`,
  so no response is lost anyway.

The confirmation should become **impact-driven** rather than
"responses exist at all":

1. Before running, dry-run the reconcile — run the engine and
   compute the diff per instrument **without writing** — to get the
   total `responses_deleted` that a real run would cause.
2. If `responses_deleted == 0`: no confirmation. The super-button
   runs straight through (Generate → Validate → Activate).
3. If `responses_deleted > 0`: 303 to the host page with the
   confirmation banner, but with precise copy — e.g. *"Regenerating
   drops N saved response(s) on M pair(s) that the current setup no
   longer produces. Responses on unchanged pairs are kept."* — and
   a single **Regenerate & activate** / **Cancel** choice. The
   `regen_choice=keep` skip-Generate path can be retired, since
   reconcile no longer destroys unchanged data.

A dedicated dry-run helper (e.g.
`assignments.reconcile_impact(db, review_session)` returning the
per-instrument `(to_insert, to_delete, to_keep, responses_deleted)`
counts) keeps both the confirmation builder and any future
Assignments-page preview on one code path. The engine evaluation is
in-memory and cheap, so a dry-run plus a real run per click is
acceptable.

## Suggested PR slices

1. **Reconcile core.** Rewrite `_materialise_one_instrument` to
   diff-and-reconcile; update the `assignments.generated` counts +
   `EVENT_SCHEMAS`. Behaviour-preserving for sessions without
   responses; existing `replace_assignments` tests stay green. Add
   tests for the add / remove / unchanged reviewer cases asserting
   `to_keep` responses survive.
2. **Impact-driven confirmation.** Add `reconcile_impact(...)`;
   rework the super-button detour to dry-run, skip the confirmation
   when `responses_deleted == 0`, and show the precise count
   otherwise; retire `regen_choice=keep`. Update
   `spec/workflow_card.md`.

## Source-of-truth pointers

- Materialisation: `app/services/assignments.py`
  (`_materialise_one_instrument`, `replace_assignments`).
- Rule engine: `app/services/rules/engine.py` (`evaluate`,
  `EvaluationResult`).
- FK-safe response delete order: PR #1065.
- Super-button + current confirmation: `spec/workflow_card.md`
  ("Saved-response confirmation detour"),
  `app/web/routes_operator/_workflow.py`.
- Audit registry: `app/services/audit.py` (`EVENT_SCHEMAS`).
