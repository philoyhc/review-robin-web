# Prioritized weaknesses and bugs found by Codex

Assessment date: 2026-06-05.

This note turns the Codex assessment follow-ups into one deconflicted, priority-ordered work list. It is intentionally narrow: it does not replace the fuller rolling assessments in `guide/codebase_assessment_*.md`, and it does not claim every item is a confirmed runtime bug. Items marked **Bug / likely defect** should be investigated with regression coverage before or alongside remediation; items marked **Risk / gap** are product, maintainability, or operational-readiness concerns.

## P0 — Normalize identity lookups and uniqueness

**Type:** Bug / likely defect  
**Why this is first:** participant and operator access both depend on email identity. Case drift can create duplicate people, ambiguous participant access, or split operator ownership.

### P0.1 — Case-variant duplicate participant rows through per-row CRUD

The participant gates intentionally compare authenticated email against roster identity case-insensitively for reviewers, reviewees, and observers. The single-row CRUD duplicate checks, however, use exact equality:

- Reviewer `_email_taken` checks `Reviewer.email == email`.
- Reviewee `_identifier_taken` checks `Reviewee.email_or_identifier == identifier`.
- Observer `_email_taken` checks `Observer.email == email`.

The CSV import path is stricter and normalizes duplicate detection through `.lower()`, so the inconsistency is specifically in the per-row editor path.

**Impact:** an operator could create both `Alice@example.edu` and `alice@example.edu` as separate rows through per-row UI. The auth gates then treat both as the same person. Depending on route and query ordering, that could yield ambiguous access, duplicate role chips, duplicate assignments, or confusing review progress.

**Recommended remediation:** make the per-row services use case-insensitive duplicate checks, and back that behavior with regression tests for reviewer, reviewee, and observer create/update flows. Prefer a storage-level rule as well: either normalize email-bearing identities on write or add lower-expression uniqueness guards that work in both Postgres and SQLite migrations.

### P0.2 — `get_or_create_user` is case-sensitive while admin invite lookup is case-insensitive

The `users.email` column is unique, but ordinary string uniqueness is case-sensitive on common database collations unless configured otherwise. `get_or_create_user` looks up users with exact equality: `User.email == current_user.email`.

By contrast, the sys-admin invite service explicitly performs case-insensitive matching with `func.lower(User.email) == email_normalised.lower()`.

**Impact:** `Alice@example.edu` and `alice@example.edu` could become two different `User` rows. That can break operator/session access because session ownership and `SessionOperator` membership attach to one row, while the user may later sign in as the other casing.

**Recommended remediation:** align `get_or_create_user` with the user-invite behavior: perform a case-insensitive lookup before insert, add tests for first sign-in after a differently-cased pre-seed, and decide whether to normalize stored user emails or enforce lower-email uniqueness in the database.

## P1 — Finish production email and participant entry paths

**Type:** Risk / gap  
**Why this is next:** the core review workflow is largely present, but pilot deployment depends on getting participants into the right surfaces reliably.

The last truly in-flight product gap is Segment 14B email infrastructure, including reviewee / observer notifications and magic-link landings. The architecture still describes `email_outbox` as a dev-mode replacement and says real SMTP / production email is deferred.

**Impact:** without this work, the app can be exercised by knowledgeable operators, but a real pilot still depends on manual coordination or incomplete participant notification flows, especially for non-reviewer audiences.

**Recommended remediation:** land Segment 14B email activation before further polish-heavy work. Treat reviewee / observer notification call sites and magic-link schema decisions as part of the same delivery path so the participant model has a complete operational entry story.

## P2 — Prepare the app for pilot operation

**Type:** Risk / gap  
**Why this follows email:** once identity and email entry paths are solid, the next bottleneck is safe human operation under pilot pressure.

The codebase is close to a pilotable v1, but pilot readiness still depends on operator-facing polish, runbooks, recovery guidance, and clear state explanations. The remaining operator-polish/documentation work matters for a citizen project because an app can be functionally complete while still being hard to operate when something goes wrong.

**Impact:** operators may be able to complete the happy path but struggle with recovery, edge states, or explaining workflow state to participants.

**Recommended remediation:** after email lands, write the operator start-here/runbook material and tighten visible workflow copy around states, recovery actions, and expected next steps.

## P3 — Reduce large-template maintenance risk

**Type:** Maintainability risk  
**Why this is lower priority:** large templates are not a known runtime defect, but they raise the cost and risk of future UI changes.

The latest file-split work retired the 1,300+ LOC band for production Python, but the template layer still has very large files. A local line-count scan found:

| LOC | File |
|---:|---|
| 5,343 | `app/web/templates/operator/instruments_index.html` |
| 3,231 | `app/web/templates/base.html` |
| 2,610 | `app/web/templates/operator/session_extract_data.html` |

**Impact:** the risk is maintainability, reviewability, and accidental UI regressions rather than immediate runtime correctness.

**Recommended remediation:** do not block pilot on template splitting, but when touching one of these pages for functional work, carve out obvious partials/macros in the same PR-sized slice. Avoid pure churn unless it materially reduces an upcoming change's risk.

## P4 — Clean stale comments and docs near touched code

**Type:** Documentation drift  
**Why this is last:** stale comments can mislead future contributors, but the example found is not a functional defect.

Rapid feature completion has left some stale implementation comments. For example, `app/web/routes_reviewer/_results.py` still describes the reviewee results slice as Raw-mode-only and says anonymized / summarized modes and the observer surface ship later, while the current participant spec says reviewee results and observer collation are live.

**Impact:** future maintainers or agents may misread the current surface contract and accidentally regress behavior.

**Recommended remediation:** update stale implementation comments opportunistically when editing nearby code, and prefer citing the current spec surface rather than preserving phase-history comments in live modules.
