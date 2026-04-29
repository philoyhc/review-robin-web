# Segment 9.1 Plan — Session readiness, activation lifecycle, and response-window control

**Status:** Part 1 of the Segment 9 superseding split plan.

## Goal
Ship the operator controls that determine when a session is review-ready and when responses are accepted.

## Scope
- Session lifecycle foundation for MVP:
  - Introduce/confirm session states for **Draft** and **Ready** in this segment.
  - Keep **Expired** / **Archived** reserved for later segments, with optional lightweight pre-positioning only if low-cost.
- Activation flow:
  - Readiness validation gates activation.
  - Activation creates auditable state transition to Ready.
  - Allow revert from Ready back to Draft (per assumptions/decisions), also audited.
- Edit policy:
  - Block operator edits while Ready (no edit-while-active workflow yet).
- Per-instrument acceptance controls:
  - Keep `accepting_responses: bool` model.
  - Session deadline is authoritative for response acceptance.
  - Add `responses_visible_when_closed: bool` pre-position toggle.
  - Manual stop/resume accepting responses via operator sub-page.
- Reviewer route-level enforcement:
  - Save/submit/clear blocked when instrument/session is not accepting.
  - Reviewer page can render read-only state.
- Audit coverage:
  - Activation/revert and instrument open/close actions audited.
  - Lazy deadline-close audit event allowed.

## Out of scope
- Invitation generation/sending.
- Monitoring dashboard.
- Reminders.
- Magic-link/anonymous auth (Easy Auth sign-in remains required).

## Deliverable shape
One PR focused on lifecycle and gating mechanics with migration(s), service updates, route guards, and tests.

## Notes captured from assumptions and seg9 decisions
- Ready→Draft reversion is allowed.
- Block edits while Ready for this segment set.
- Easy Auth sign-in required; magic links deferred to Segment 16.
- Session deadline supersedes instrument acceptance timing.
- Lazy deadline-close audit emission is acceptable.
