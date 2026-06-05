# Weaknesses and bugs found by Codex

Assessment date: 2026-06-05.

This note extracts the **Weaknesses and risks** and **Bugs / likely defects found** sections from the Codex codebase assessment requested on 2026-06-04. It is intentionally narrow: it is not a replacement for the fuller rolling assessments in `guide/codebase_assessment_*.md`.

## Weaknesses and risks

### 1. Email remains the biggest product gap

The last truly in-flight piece is Segment 14B email infrastructure, including reviewee/observer notifications and magic-link landings. The architecture still describes `email_outbox` as a dev-mode replacement and says real SMTP / production email is deferred.

### 2. Some major UI/template files remain very large

The latest file-split work retired the 1,300+ LOC band for production Python, but the template layer still has very large files. A local line-count scan found:

| LOC | File |
|---:|---|
| 5,343 | `app/web/templates/operator/instruments_index.html` |
| 3,231 | `app/web/templates/base.html` |
| 2,610 | `app/web/templates/operator/session_extract_data.html` |

The practical risk is not runtime correctness; it is maintainability, reviewability, and accidental UI regressions.

### 3. Pilot-readiness depends on operational polish

The codebase is close to a pilotable v1, but pilot readiness depends on operator-facing polish, runbooks, and recovery guidance. The remaining “operator polish + documentation” work matters for a citizen project because an app can be functionally complete while still being difficult to operate under real-world pressure.

### 4. Some docs/comments are stale after rapid feature completion

Rapid feature completion has left some stale implementation comments. For example, `app/web/routes_reviewer/_results.py` still describes the reviewee results slice as Raw-mode-only and says anonymized / summarized modes and the observer surface ship later, while the current participant spec says reviewee results and observer collation are live.

This is not a functional defect, but it can mislead future agents or contributors.

## Bugs / likely defects found

### Bug 1 — Case-variant duplicate identities are possible through per-row CRUD

**Severity:** medium-high, because participant access is intentionally case-insensitive.

The participant gates compare authenticated email against roster identity case-insensitively for reviewers, reviewees, and observers. However, the single-row CRUD duplicate checks use exact equality:

- Reviewer `_email_taken` checks `Reviewer.email == email`.
- Reviewee `_identifier_taken` checks `Reviewee.email_or_identifier == identifier`.
- Observer `_email_taken` checks `Observer.email == email`.

The CSV import path is stricter and normalizes duplicate detection through `.lower()`, so the inconsistency is specifically in the per-row editor path.

**Impact:** an operator could create both `Alice@example.edu` and `alice@example.edu` as separate rows through per-row UI. The auth gates then treat both as the same person. Depending on route and query ordering, that could yield ambiguous access, duplicate role chips, duplicate assignments, or confusing review progress.

**Likely fix:** make the per-row services use case-insensitive duplicate checks, ideally with database-level support where practical. For email-bearing identities, normalize to lowercase on write or add lower-expression unique indexes in migrations for Postgres/SQLite-compatible behavior.

### Bug 2 — `get_or_create_user` is case-sensitive while other user-management code is case-insensitive

**Severity:** medium, because it can split one operator into multiple `users` rows if Easy Auth changes email casing.

The `users.email` column is unique but ordinary string uniqueness is case-sensitive on common database collations unless explicitly configured otherwise. `get_or_create_user` looks up users with exact equality: `User.email == current_user.email`.

By contrast, the sys-admin invite service explicitly says email matching is case-insensitive and uses `func.lower(User.email) == email_normalised.lower()`.

**Impact:** `Alice@example.edu` and `alice@example.edu` could become two different `User` rows. That can break operator/session access because session ownership and `SessionOperator` membership attach to one row, while the user may later sign in as the other casing.

**Likely fix:** align `get_or_create_user` with `users.invite`: case-insensitive lookup before insert, and either normalize email casing at write or add a lower-email uniqueness guard.

### Bug 3 — Stale implementation comment in reviewee results route

**Severity:** low, documentation/comment drift only.

`app/web/routes_reviewer/_results.py` says the slice ships Raw mode and that anonymized / summarized and observer surfaces ship later. The current participant spec says reviewee results are live in raw / anonymized / summarized mode and observer collation is live.

**Impact:** future maintainers or agents may misread the current surface contract and accidentally regress behavior.

**Likely fix:** update the module docstring to match the live participant model.
