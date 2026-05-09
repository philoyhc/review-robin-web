# Segment 12C — Self-review revamp

**Status:** Planning. Stub created 2026-05-09 to capture
decisions and scope as they crystallise.

## Working notes

_Use this section as a running log — capture decisions,
constraints, links, and back-of-envelope sketches as they come
up. Once the shape settles, lift the durable parts into a
proper "Goal / Scope / PR sequence / Out of scope" structure
and archive the working-notes scratchpad._

- (placeholder)

## Open questions

- (placeholder)

## Related context

- 12A-1 PR 4a (#725, 2026-05-09) added the derived
  `SelfReview` column to the responses CSV. The canonical
  predicate lives in
  `is_self_review(reviewer, reviewee)`
  (`app/services/assignments.py`) — case-insensitive
  `reviewer.email` vs `reviewee.email_or_identifier`,
  `FALSE` for non-email reviewee identifiers.
- Existing self-review handling on assignment generation:
  `generate_full_matrix(..., exclude_self_review)` and
  the `exclude_self_review` toggle on the Assignments page;
  rule-based engine equivalent in
  `app/services/rules/engine.py` (separate
  `_is_self_review` helper, intentionally module-private).
- Counting helpers: `count_self_review_candidates`,
  `count_self_reviews_in_assignments` in
  `app/services/assignments.py`.
