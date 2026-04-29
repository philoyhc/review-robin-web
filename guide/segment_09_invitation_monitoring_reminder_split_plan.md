# Segment 9 (Superseding Plan) — split into 9.1 / 9.2 / 9.3

**Status:** This document supersedes `guide/segment_09_superseded_single_plan.md`.

## Why split Segment 9
Based on the current codebase, `assumptions.md`, and the resolved decisions in `seg9stuff`, Segment 9 is too broad for a single PR-sized delivery. It mixes lifecycle controls, reviewer-access gating, invitations/email plumbing, monitoring, and reminders.

This superseding plan breaks Segment 9 into smaller deliverables that can each ship safely with focused tests.

---

## Segment 9.1 — Session readiness + activation lifecycle + response-window control

### Goal
Ship the operator controls that determine when a session is review-ready and when responses are accepted.

### Scope
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

### Out of scope
- Invitation generation/sending.
- Monitoring dashboard.
- Reminders.
- Magic-link/anonymous auth (Easy Auth sign-in remains required).

### Deliverable shape
One PR focused on lifecycle and gating mechanics with migration(s), service updates, route guards, and tests.

---

## Segment 9.2 — Invitations + dev outbox + reviewer-access links

### Goal
Ship invitation creation and delivery plumbing needed to bring reviewers into active sessions.

### Scope
- Invitation model/table and statuses (minimal MVP state machine).
- Invitation generation for assigned reviewers on activation-ready sessions.
- Token strategy aligned with decisions:
  - Strong token generation/hash approach.
  - Lifetime model without short expiry cutoff in this segment.
- Delivery behavior:
  - Dev-mode outbox table as primary implementation in this segment.
  - Real SMTP/provider integration deferred.
- Operator invitation visibility/actions sufficient for MVP.
- Audit coverage for invitation actions.

### Out of scope
- Monitoring aggregates.
- Reminder sends.
- Production email backend/provider hardening.

### Deliverable shape
One PR that is data-model + service + operator workflow focused, independent of reminder/dashboard complexity.

---

## Segment 9.3 (optional but recommended) — Monitoring + reminders

### Goal
Ship operator feedback loops after invitations are in place.

### Scope
- Monitoring page with per-reviewer progress and summary counts.
- “Send reminder to incomplete reviewers” action.
- Incomplete targeting includes:
  - not submitted, and
  - required missing cases (including warn-and-override path decision).
- Reminder audit events + last-reminder tracking.

### Out of scope
- Advanced analytics/charts.
- Complex reminder segmentation rules.
- Queue-based bulk delivery infrastructure.

### Deliverable shape
One PR focused on reporting + reminder behavior, using invitation plumbing from 9.2.

---

## Recommended sequencing
1. **9.1 first** — establishes authoritative session/instrument gating and lifecycle safety.
2. **9.2 second** — adds invitation mechanics on top of stable activation behavior.
3. **9.3 third (optional split)** — complete operator monitoring/reminder loop.

If only two pieces are desired, combine **9.2 + 9.3** into a single second PR after 9.1.

---

## Notes captured from assumptions and seg9 decisions
- Ready→Draft reversion is allowed.
- Block edits while Ready for this segment set.
- Easy Auth sign-in required; magic links deferred to Segment 16.
- Session deadline supersedes instrument acceptance timing.
- Dev outbox table is preferred in this phase.
- Lazy deadline-close audit emission is acceptable.
- Two-PR minimum split is desired; this plan supports both 2-part and 3-part execution.
