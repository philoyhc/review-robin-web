# Segment 9.3 Plan (optional) — Monitoring and reminders

**Status:** Optional Part 3 of the Segment 9 superseding split plan.

## Goal
Ship operator feedback loops after invitations are in place.

## Scope
- Monitoring page with per-reviewer progress and summary counts.
- “Send reminder to incomplete reviewers” action.
- Incomplete targeting includes:
  - not submitted, and
  - required missing cases (including warn-and-override path decision).
- Reminder audit events + last-reminder tracking.

## Out of scope
- Advanced analytics/charts.
- Complex reminder segmentation rules.
- Queue-based bulk delivery infrastructure.

## Deliverable shape
One PR focused on reporting + reminder behavior, using invitation plumbing from 9.2.

## Notes captured from assumptions and seg9 decisions
- Reminder targeting includes the agreed incomplete criteria.
- Two-piece execution remains valid by combining 9.2 + 9.3.
