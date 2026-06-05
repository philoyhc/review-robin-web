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

## Addendum — Action plan (2026-06-05)

Plan covers P0, P3, P4. P1 (Segment 14B email) and P2 (pilot-readiness polish) are deliberately out of scope here — they are tracked elsewhere and follow their own segment plans.

All four findings below were re-verified against `main` on the assessment date.

### Slice A — `get_or_create_user` case-insensitive lookup (P0.2) — **Done (PR #1836)**

Landed in PR #1836 (`claude/p0-identity-normalization`). `app/web/deps.py` now looks up via `func.lower(User.email) == current_user.email.lower()`. Regression tests in `tests/integration/test_operator_allowlist_gate.py` cover both casings. **Note:** the historical-duplicates tolerance fix (`.order_by(User.id).limit(1)`) was prepared as `b26cf82` but missed the #1836 merge; it ships in PR #1837 — see the Codex P1 follow-up section below.

### Slice B — Per-row roster duplicate checks (P0.1) — **Done (PR #1836)**

Landed in PR #1836. `_email_taken` in `app/services/reviewers.py` and `app/services/observers.py`, and `_identifier_taken` in `app/services/reviewees.py`, all compare via `func.lower(<col>) == value.lower()`. Reviewee identifiers are lowercased unconditionally — matching the existing CSV in-CSV dedup at `app/services/csv_imports.py:330,353` and the policy resolved in PR #1835. (For context: an earlier draft of this slice prescribed an `"@"`-guarded check, which would have re-introduced the editor-vs-CSV inconsistency. The `"@"` branch at `csv_imports.py:483,513` is a *cross-role* collision check, not a within-reviewees policy.) Side effect of unconditional lower-casing: anonymous reviewee identifiers like `Token-AB` and `token-ab` collide everywhere — matches existing CSV behavior, not a regression.

Regression coverage: `tests/integration/test_reviewers_crud.py`, `tests/integration/test_reviewees_crud.py`, and the new `tests/integration/test_observers_crud_dedup.py` cover create + update paths for both email-shaped and anonymous identifiers.

### Slice C — `_results.py` docstring rewrite (P4, targeted) — **Done (PR #1836)**

Landed in PR #1836. `app/web/routes_reviewer/_results.py` module docstring now describes the live surface (Raw + Anonymized + Summarized + Acknowledge, per `spec/participant_model.md`) instead of the original "Raw-mode-only" phase note.

### Codex P1 follow-up on PR #1836 — **In flight (PR #1837)**

Codex review on PR #1836 flagged that the new case-insensitive lookup would crash sign-in with `MultipleResultsFound` if two case-variant `User` rows already existed (possible from the old exact-match path on the dev slot). A fix (`.order_by(User.id).limit(1)` so the oldest matching row wins deterministically) was committed to the #1836 branch as `b26cf82` but the PR was merged before that commit reached the merge — only `ab04331` shipped. The Codex P1 concern is therefore **still live on `main`** until PR #1837 lands.

PR #1837 re-applies the `b26cf82` change against `main`, plus the regression test `test_get_or_create_user_resolves_historical_case_variant_duplicates` in `tests/integration/test_operator_allowlist_gate.py`.

### Slice D — Storage-level uniqueness guard (P0 follow-up, deferred)

**Status:** not started. Gating on:

1. PR #1836 baking on the dev slot — the b26cf82 tolerance fix is unverified end-to-end. Slice D's migration should not run before that fix is proven, because if the tolerance fix had a bug, the migration could compound the damage.
2. A read-only duplicate-cluster audit against production data. The migration shape depends on the answer: zero clusters → clean unique-index migration; non-zero → deduplication step first, with operator-visible decisions about which row to keep.

When picked up: either normalize email-bearing identities on write (preferred for portability) or add a lower-expression unique index. Both must round-trip on SQLite and Postgres per the migration-portability note in CLAUDE.md.

### Slice E — Large templates (P3) — **Not scheduled, by decision**

Re-examined 2026-06-05 after PR #1836 landed. The 5,342 / 3,231 / 2,610 LOC files were re-verified; LOC has not changed.

Decision: **no PR, no implicit queue.** A real plan for carving these (4 PRs, snapshot-test infra build-out, ordering across cross-band JS dependencies) was sketched and costed. The cost is concrete and present (4 PRs of pure-churn diff review, render-regression risk, opportunity cost vs P1); the benefit is speculative and future ("easier reviews of changes that may or may not happen"). No known runtime defect is traced to template size. `base.html` is 87% one `<style>` block whose extraction CLAUDE.md explicitly defers.

What would flip this decision:

- A real functional change queued against one of the offenders — then carving a cohesive partial in the same PR is cheap because the reviewer is already in that file.
- Measured friction: repeated reports of "I lost my place in this file" or "I shipped a bug because I missed a downstream consumer." Right now those reports do not exist.

If either condition holds later, the earlier draft plan (Band 3 first, then Band 1, then Band 2, then the extract-data lens card; explicit snapshot tests; include-with-context over macros for high-arity blocks) is captured in this session's transcript and can be revived.

### Slice F — Other stale comments (P4, opportunistic)

Status unchanged. A repo-wide scan for "follow-on slices" / "Raw-mode-only" / "ships later" found only the one site Slice C resolved. No systemic sweep to schedule. Standing policy: when editing a module, fix any nearby comment that contradicts the current spec, and cite spec surfaces rather than phase history.

### Status summary

| Slice | Item | Status |
|---|---|---|
| A | `get_or_create_user` case-insensitive lookup | Done (PR #1836) |
| B | Per-row roster duplicate checks | Done (PR #1836) |
| C | `_results.py` docstring rewrite | Done (PR #1836) |
| — | Codex P1 follow-up: tolerate historical duplicates | In flight (PR #1837) — `b26cf82` missed the #1836 merge |
| D | Storage-level uniqueness guard | Deferred — gated on dev-slot bake + duplicate-cluster audit |
| E | Large template carves | Set aside by decision — opportunistic only, no implicit queue |
| F | Other stale comments | Standing policy — no scheduled work |

### Ordering and PR shape

1. **PR 1 (Slices A + B + C):** merged as #1836 on 2026-06-05.
2. **PR 1a (Codex P1 follow-up):** in flight as #1837. Re-applies the `b26cf82` historical-duplicates tolerance that missed the #1836 merge.
3. **PR 2 (Slice D):** deferred. Pre-work: run the duplicate-cluster audit once PR #1837 has landed and baked on the dev slot.
4. **No PRs for Slices E or F.**

### Exit criteria

- [x] `get_or_create_user` and all three per-row roster services use case-insensitive identity comparison, with regression tests guarding both directions.
- [ ] `get_or_create_user` tolerates pre-existing case-variant duplicate rows without raising `MultipleResultsFound` (PR #1837).
- [x] `app/web/routes_reviewer/_results.py` module docstring describes current (Raw + Anonymized + Summarized + Acknowledge) behavior.
- [ ] Slice D is either landed or has an explicit follow-up issue with the data-migration question answered.
- [x] The three large templates are unchanged unless a functional PR happened to touch them; LOC has not grown materially. (Re-verified 2026-06-05.)
