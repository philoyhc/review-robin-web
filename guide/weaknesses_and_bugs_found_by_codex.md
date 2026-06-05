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

### Slice A — `get_or_create_user` case-insensitive lookup (P0.2)

**Land first.** Smallest patch, highest-leverage: every authenticated request flows through this dependency, so an inconsistent collation here can split operator identity across sessions.

- Change `app/web/deps.py:58-60` to look up via `func.lower(User.email) == current_user.email.lower()` (mirror the pattern at `app/services/users.py:430` and `app/web/routes_operator/_session_home.py:557`).
- Add a regression test: pre-seed a `User` row with `Alice@example.edu`, drive a request with `FAKE_AUTH_EMAIL=alice@example.edu`, assert the existing row is reused (no second insert).
- Add a second test for the reverse casing to confirm symmetry.
- Audit-event impact: none (no schema change, no new emitter).
- Storage-level normalization (lower-expression unique index on `users.email`) is **deferred** to Slice D; this slice is service-layer only so it can ship behind a small PR.

### Slice B — Per-row roster duplicate checks (P0.1)

- Update `_email_taken` in `app/services/reviewers.py:97-110` and `app/services/observers.py:100-113` to compare `func.lower(<col>) == email.lower()`.
- Update `_identifier_taken` in `app/services/reviewees.py:102-115` to apply `.lower()` **only when `"@"` is in the identifier**, matching the CSV import branch at `app/services/csv_imports.py:483,513`. Anonymous (non-email) identifiers remain case-sensitive — operators may legitimately use opaque tokens whose case is meaningful.
- Cover both create and update paths in all three services with regression tests:
  - Create rejects `alice@x.com` when `Alice@x.com` already exists (reviewer, reviewee email, observer).
  - Update rejects re-casing onto another row's email.
  - Reviewee with anonymous identifier `Token-AB` does **not** collide with `token-ab` (negative test guarding the `"@"` branch).
- Audit-event impact: none (rejection happens before the mutating write).
- Can ship in the same PR as Slice A, or immediately after; no ordering dependency between them.

### Slice C — `_results.py` docstring rewrite (P4, targeted)

The Codex example is actively misleading about what the module does today, so do not defer this one until "next time we're in the neighborhood" — fold it into Slice A or B since both already touch participant/identity code paths.

- Rewrite the module docstring at `app/web/routes_reviewer/_results.py:1-17` to describe current behavior: gated by `require_reviewee_in_session`; body built by `build_reviewee_results_context` which resolves Raw / Anonymized / Summarized via `app/services/visibility_policies.py`; includes the `acknowledge` POST.
- Reference `spec/participant_model.md` rather than phase-history wording.
- Five-line edit, no test impact.

### Slice D — Storage-level uniqueness guard (P0 follow-up, deferred)

After A + B land and bake on the dev slot, add a defense-in-depth migration:

- Either normalize email-bearing identities on write (preferred for portability) or add a lower-expression unique index. Both must round-trip on SQLite and Postgres per the migration-portability note in CLAUDE.md.
- This is its own slice — do **not** bundle with A/B. The behavioral fix is the urgent part; the schema guard is durable but lower-priority.
- Open question to resolve before drafting: does normalize-on-write require a one-time data migration to lower-case existing rows, and how many duplicate clusters does that surface in production? Run a read-only count first.

### Slice E — Opportunistic template carves (P3, no dedicated PR)

Do not schedule. Policy reminder for future PRs touching the three offenders:

| LOC (2026-06-05) | File | Suggested first carve when next touched |
|---:|---|---|
| 5,342 | `app/web/templates/operator/instruments_index.html` | Per-band partials (`_band1.html` / `_band2.html` / `_band3.html`) |
| 3,231 | `app/web/templates/base.html` | None — CSS extraction is deferred; avoid churn here unless the change is functional |
| 2,610 | `app/web/templates/operator/session_extract_data.html` | Per-instrument lens-card macro |

Carve only the cohesive partial nearest your functional change. No pure-churn refactors.

### Slice F — Other stale comments (P4, opportunistic)

A repo-wide scan for "follow-on slices" / "Raw-mode-only" / "ships later" turned up only the one site in Slice C, so there is no systemic sweep to schedule. Continue the standing policy: when editing a module, fix any nearby comment that contradicts the current spec, and cite spec surfaces rather than phase history.

### Ordering and PR shape

1. **PR 1 (Slices A + B + C):** identity case-normalization + the `_results.py` docstring. Single coherent slice — all touch participant identity contracts and share the regression-test setup.
2. **PR 2 (Slice D):** storage-level guard, after PR 1 has baked. Drives the open-question audit first.
3. **No PR for Slices E or F:** standing policy, applied opportunistically.

### Exit criteria

This addendum is satisfied when:
- `get_or_create_user` and all three per-row roster services use case-insensitive identity comparison, with regression tests guarding both directions.
- `app/web/routes_reviewer/_results.py` module docstring describes current (Raw + Anonymized + Summarized + Acknowledge) behavior.
- Slice D is either landed or has an explicit follow-up issue with the data-migration question answered.
- The three large templates are unchanged unless a functional PR happened to touch them; LOC has not grown materially.
