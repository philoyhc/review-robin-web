# Segment 9.2 Plan — Invitations, dev outbox, and reviewer-access links

**Status:** Part 2 of the Segment 9 superseding split plan.

## Goal
Ship invitation creation and delivery plumbing needed to bring reviewers into active sessions.

## Scope
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

## Out of scope
- Monitoring aggregates.
- Reminder sends.
- Production email backend/provider hardening.

## Deliverable shape
One PR that is data-model + service + operator workflow focused, independent of reminder/dashboard complexity.

## Notes captured from assumptions and seg9 decisions
- Dev outbox table is preferred in this phase.
- Easy Auth sign-in remains required; magic links are deferred to Segment 16.
