# Segment 9.5A Implementation Plan — Setup-readiness lifecycle states

## Deferred to Segment 9.5 — Setup-readiness lifecycle states

Locked here so 9.4B's UI doesn't paint itself into a corner. **Not implemented in 9.4B.** Segment 9.5 will add a new stored state `validated` to the existing `SessionStatus` enum and rewire the activation flow against it.

- **D1 — `validated` is a stored state**, not derived. Sticky across renders so the inline summary card has a real home (rather than one-shot per validate POST).
- **D2 — Invalidation triggers (`validated → draft`):** every setup-mutating route that can affect validation outcome. Today's set: reviewer import + delete-all, reviewee import + delete-all, assignment generate + delete-all, session edit (name/code/description/deadline). Instrument open/close/visibility do **not** invalidate (they don't change validation results).
- **D3 — Acknowledge-warnings is implicit in `validated`.** Entering the `validated` state means "no blocking conditions" — warnings, if any, are acknowledged at the moment of transition. No separate `warnings_acknowledged_at` column.
- **D4 — Revert from `ready` lands on `draft`**, not `validated`. Forces the operator to re-run validation before the next activation.
- **D5 — "Locked but invalid" is unreachable.** Activation requires `can_activate` (no errors); revert always drops to `draft`. No transition reaches "locked + invalid."
- **D6 — Scope split.** 9.4B ships against today's two-state semantics (`draft`/`ready`); 9.5 introduces `validated` and rewrites every mutating route's invalidation hook. Keeps 9.4B's diff focused on UI restructure.

Full-state target after 9.5: `draft` → `validated` → `ready` → `expired` (Segment 9.3+) → `archived` (Segment 11+).
