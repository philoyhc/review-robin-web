# Segment 9.1A Implementation Plan — Session readiness, activation, and response-window gates

**Status:** Draft implementation plan for Segment 9.1 (single PR).

## Positioning and naming
- Segment 9 is split into **three PR-sized blocks**: **9.1**, **9.2**, **9.3**.
- This file is the **A-plan** for Segment **9.1** and does **not** split 9.1 into 9.1A/9.1B execution slices.

## 9.1 outcome
Deliver one coherent PR that adds lifecycle control for when a session can accept reviewer responses, with auditable transitions and strict route gating.

## Decisions locked for 9.1
1. **Activation gate behavior**
   - Structural **errors block** activation.
   - **Warnings/informational findings do not hard-block**; operator can explicitly confirm and continue.
2. **Ready-state edit lock**
   - Block mutating setup operations while Ready (session edit/delete, reviewer/reviewee import or delete-all, assignment generate/delete-all).
   - Revert-to-Draft remains available and requires a confirmation checkbox.
3. **Lifecycle pre-positioning**
   - Reserve `Expired` and `Archived` in schema-level status constraints/enum only.
   - No UI transitions into those states in 9.1.
4. **Response visibility toggle semantics**
   - `responses_visible_when_closed` is operator-managed configuration.
5. **Deadline close audit**
   - Lazy deadline-close event can be emitted from first observer request, including reviewer GET routes.
6. **Write gating strictness**
   - Save/submit/clear require all of:
     - `instrument.accepting_responses == true`
     - `session.status == Ready`
     - `now() < session.deadline`

## Planned implementation slices (single PR)
1. **Data model + migration**
   - Add/confirm `Session.status` with Draft/Ready active use; include Expired/Archived as reserved values.
   - Add/confirm `Instrument.responses_visible_when_closed` default false.
2. **Validation + activation services**
   - Extend readiness result shape to distinguish blocking errors from non-blocking warnings/info.
   - Activation endpoint/service supports explicit override consent when only non-blocking findings exist.
   - Require confirmation payload for revert-to-draft.
3. **Operator route guardrails while Ready**
   - Enforce lock on setup mutation endpoints.
   - Preserve read-only pages and per-instrument open/close surface.
4. **Reviewer write-path gates**
   - Centralize acceptance predicate and apply to save/submit/clear.
   - Return clear non-accepting state messaging for blocked writes.
5. **Audit updates**
   - Emit audited events for activate/revert/open/close and lazy deadline close (idempotent).
6. **Tests**
   - Add/update tests for each gate and transition, including override activation path and revert confirmation requirement.

## Explicitly out of scope (9.2/9.3)
- Invitations and dev outbox workflows (9.2).
- Monitoring/reminder workflows (9.3).
