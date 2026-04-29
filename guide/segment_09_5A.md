# Segment 9.5A Implementation Plan — Setup-readiness lifecycle states

## Decisions

Segment 9.5A adds a new stored state `validated` to the existing `SessionStatus`
enum and rewires the activation flow against it.

- **D1 — `validated` is a stored state**, not derived. Sticky across renders so
  the inline summary card has a real home (rather than one-shot per validate
  POST).
- **D2 — Invalidation triggers (`validated → draft`):** every setup-mutating
  route that can affect validation outcome. The locked set:
  - reviewer import + delete-all
  - reviewee import + delete-all
  - assignment generate + delete-all
  - session edit (name / code / description / deadline)

  Instrument open/close/visibility do **not** invalidate (they don't change
  validation results). `POST /delete-data` does **not** invalidate either —
  it wipes responses but preserves setup, and is allowed in any status.
- **D3 — Acknowledge-warnings is implicit in `validated`.** Entering the
  `validated` state means "no blocking conditions" — warnings, if any, are
  acknowledged at the moment of transition. No separate
  `warnings_acknowledged_at` column.
- **D4 — Revert from `ready` lands on `draft`**, not `validated`. Forces the
  operator to re-run validation before the next activation.
- **D5 — "Locked but invalid" is unreachable.** Activation requires
  `can_activate` (no errors); revert always drops to `draft`. No transition
  reaches "locked + invalid."
- **D6 — Scope split.** 9.4B shipped against the two-state semantics
  (`draft`/`ready`); 9.5A introduces `validated` and rewrites every mutating
  route's invalidation hook.

## Transition mechanics (resolved 2026-04-29)

- **T1 — `draft → validated` trigger.** The existing
  `GET /operator/sessions/{id}?validated=1` flips status to `validated` as a
  side-effect when validation returns zero errors. Idempotent in
  `validated`. The legacy `GET /operator/sessions/{id}/validate` deep-dive
  page stays **read-only** and never transitions status.
- **T2 — Activation precondition.** `activate_session` requires
  `is_validated`, not `is_draft`. The operator must pass through
  `validated` explicitly before activation.
- **T3 — Mutating-route gates.** Routes currently gated on `_require_draft`
  accept either `draft` or `validated` and flip status back to `draft` as
  part of the same commit when invoked from `validated`.
- **T4 — New sessions start `draft`** (unchanged). Revert from `ready`
  lands on `draft` per D4 — `validated` is reachable only via T1.
- **T5 — Audit events.** Dedicated `session.validated` and
  `session.invalidated` events; per-route invalidation events (e.g.
  `reviewers.imported`) are not overloaded with the side-effect.

Full-state target after 9.5A: `draft` → `validated` → `ready` →
`expired` (Segment 9.3+) → `archived` (Segment 11+).
