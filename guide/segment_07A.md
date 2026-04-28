# Segment 7A — Assignment Generation MVP (Agreed Plan)

**Project:** Review Robin Web
**Repository:** <https://github.com/philoyhc/review-robin-web>
**Parent plan:** `guide/segment_07_assignment_generation_mvp_plan.md`
**Purpose:** Lock in the implementation choices for Segment 7 — including
the FullMatrix and ManualAssignment flows, the placeholder Instrument
question, and the preview pattern — so the implementation sessions can
ship without re-litigating design.

This document is a **delta** on the parent plan. The parent plan still
governs scope, success criteria, and out-of-scope items.

---

## 1. Scope (unchanged from parent plan)

- Assignment hub page at `/operator/sessions/{id}/assignments`.
- FullMatrix generation with self-review exclusion option.
- ManualAssignment CSV import.
- Preview-before-save for both modes.
- Replace-all save policy with explicit confirm.
- Placeholder default Instrument (since `Assignment.instrument_id` is
  `NOT NULL` and Segment 8 has not shipped yet).
- New `assignment_mode` column on `sessions`.

---

## 2. Branch and PR strategy

Two PRs against `main`, in order:

### PR 1 — FullMatrix + hub (`claude/segment-7-full-matrix`)

`assignment_mode` migration; placeholder default-Instrument helper;
FullMatrix generation; assignment hub page; preview/save flow;
`require_session_operator`-guarded routes; tests.

### PR 2 — Manual CSV (`claude/segment-7-manual-assignments`)

ManualAssignment CSV import (parse + preview + save), reusing the
hub page from PR 1. Tests.

---

## 3. Decisions

### 3.1 Placeholder default Instrument

`Assignment.instrument_id` is `NOT NULL`. Segment 8 (instruments) has
not shipped, so there is nothing to point at. **PR 1 introduces a
helper `get_or_create_default_instrument(db, session)` that returns
the session's existing default Instrument or creates one** named
`Default` with no display fields and no response fields, `order=0`.

Every assignment created in this segment references this Instrument.
Segment 8 will let operators rename it, add fields, and create
additional instruments; the FK from `Assignment` to `Instrument`
stays valid through that.

### 3.2 `assignment_mode` column on `sessions`

Add a nullable `String(32)` column `assignment_mode` to the `sessions`
table via Alembic migration. Set when assignments are first generated
or imported. `null` until then. Values: `"full_matrix"` or `"manual"`
in this segment; `"rule_based"` reserved for Segment 12.

We do this even though `Assignment.created_by_mode` already records
the per-row mode, because the parent plan explicitly calls for it
(§2.1) and because pre-positioning the column avoids a future
migration in the segment that ships RuleBased (per the user
"preposition what's needed later" guidance).

### 3.3 Self-review default

The FullMatrix form has a checkbox **"Exclude self-review"** that
defaults to **on**. Self-review is detected when:

- the reviewee's `email_or_identifier` contains `@`, **and**
- it matches a reviewer's `email` case-insensitively.

When the checkbox is on, those `(reviewer, reviewee)` pairs are
skipped during generation. When off, every reviewer × reviewee pair is
created. Reviewees with non-email identifiers (e.g. `dan-2026`) are
unaffected by the toggle either way.

### 3.4 Preview-before-save

Both FullMatrix and ManualAssignment go through a preview step before
any rows are written. This deviates from the 6A pattern (one-shot)
because, as the user noted, "some errors need a preview to catch" —
specifically, FullMatrix can produce thousands of rows the operator
didn't expect, and Manual can have coverage gaps (reviewees with no
assignments) that aren't blocking errors but the operator should see
before committing.

#### FullMatrix preview implementation

**No server-side draft state.** FullMatrix is purely deterministic
from the current reviewer/reviewee rosters and the
`exclude_self_review` flag, so:

1. Operator opens hub, ticks `Exclude self-review`, clicks
   **Preview**.
2. POST `/operator/sessions/{id}/assignments/full-matrix` with
   `dry_run=true`.
3. Server computes counts (`new_count`, `excluded_self_count`) but
   writes no rows; renders the preview page with a hidden form
   carrying the same parameters.
4. Operator clicks **Confirm and generate** (and ticks
   `confirm_replace` if existing assignments > 0).
5. POST same endpoint with `dry_run=false`. Server re-computes (still
   deterministic) and saves.

The race window between preview and confirm is acceptable for a
single-operator MVP. If reviewers/reviewees change in another tab,
the saved counts may differ slightly from the preview — that's a
correctness property, not a bug.

#### Manual preview implementation

**Re-upload pattern, no draft table.** Reasons: avoids a new
`assignment_drafts` table + cleanup concerns; CSV is small (1 MiB
cap); the friction is "pick the file again."

1. Operator opens hub, clicks **Import manual**.
2. Upload form: file input, **Preview** button.
3. POST `/operator/sessions/{id}/assignments/manual/import` with
   `dry_run=true`. Server parses, validates, computes coverage,
   renders preview HTML (no rows written, no draft persisted).
4. Preview page shows: counts, blocking errors, warnings, plus a
   second file input and a note: *"To save, upload the same file
   again and tick replace-confirm if relevant."*
5. POST same endpoint with `dry_run=false` (and `confirm_replace=true`
   if existing > 0). Server re-parses, validates, saves.

The "what gets saved is exactly what was just uploaded" property is
preserved by re-parsing. If the operator uploads a different file the
second time, that's the new operator intent — saved as-is. (No
warning for that — keeps the flow simple.)

### 3.5 Replace policy

For each save (FullMatrix or Manual): in one transaction, delete all
existing `Assignment` rows for the session, insert the new ones, set
`session.assignment_mode = <mode>`, write an `assignments.generated`
audit event, commit.

Replace-guardrail: when existing count > 0, the save POST must
include `confirm_replace=true`. Without it, return 400 and re-render
the preview with the warning. (Same shape as Segment 6.)

### 3.6 Manual CSV format

| Column                | Required | Purpose                          |
|-----------------------|----------|----------------------------------|
| `ReviewerEmail`       | yes      | Must match an existing reviewer in this session (case-insensitive) |
| `RevieweeEmail`       | yes      | Must match an existing reviewee's `email_or_identifier` (case-insensitive) |
| `IncludeAssignment`   | no       | `true`/`false`/`yes`/`no`/`1`/`0`; default `true` if absent or empty; anything else is a blocking error |
| `AssignmentContext1`  | no       | Stored as `context["context_1"]` |
| `AssignmentContext2`  | no       | Stored as `context["context_2"]` |
| `AssignmentContext3`  | no       | Stored as `context["context_3"]` |

Blocking errors:

- Missing required column.
- Empty `ReviewerEmail` or `RevieweeEmail` cell.
- Unknown reviewer (no `Reviewer` row in this session matches the email).
- Unknown reviewee (no `Reviewee` row in this session matches the identifier).
- Duplicate `(reviewer, reviewee)` pair within the file.
- Unparseable `IncludeAssignment` value.

Non-blocking warnings:

- Reviewer in roster has no assignments in the file (info-level
  "coverage" warning, shown in preview but doesn't block).
- Reviewee in roster has no assignments in the file (same).

Manual rows are **never** allowed to create missing reviewers or
reviewees — the parent plan §12 calls this out, and we honour it.

### 3.7 FullMatrix generation order

Deterministic:

```python
for reviewer in sorted(reviewers, key=lambda r: r.id):
    for reviewee in sorted(reviewees, key=lambda r: r.id):
        if exclude_self_review and _is_self(reviewer, reviewee):
            continue
        yield (reviewer, reviewee)
```

Predictable order makes assertions in tests trivial and rollback
diffs readable.

### 3.8 Audit event

```python
AuditEvent(
    event_type="assignments.generated",
    severity="info",
    summary=f"Generated {new_count} assignments via {mode} (replaced {replaced})",
    actor_user_id=user.id,
    session_id=session.id,
    detail={
        "mode": mode,                      # "full_matrix" | "manual"
        "replaced_count": replaced,
        "new_count": new_count,
        "excluded_self_count": excluded,   # 0 for manual
        "filename": filename,              # null for full_matrix
    },
    correlation_id=request_correlation_id(),
)
```

Single event_type for both modes; `mode` lives in `detail` so
downstream queries can filter cleanly.

### 3.9 Service / schema layout

- `app/services/assignments.py` — `generate_full_matrix`,
  `parse_manual_csv`, `replace_assignments`, `existing_count`,
  `coverage_stats`, `get_or_create_default_instrument`.
  `coverage_stats(session, assignments) -> dict` returns the counts
  the preview page renders.
- `app/schemas/assignments.py` — `AssignmentMode` enum,
  `ManualAssignmentRow` pydantic model.

### 3.10 UI / templates

- New page `/operator/sessions/{id}/assignments` is the hub.
  - Shows current assignment count and assignment mode (or "No
    assignments yet").
  - Section A: **FullMatrix** form (self-review checkbox + Preview
    button).
  - Section B: **Manual CSV** form (file picker + Preview button).
  - Existing assignment count + warning + replace-confirm checkbox
    when count > 0 (echoed in both sections so the operator sees it
    regardless of which path they pick).
- `session_detail.html` "Setup" card adds a new line:
  `Assignments: <strong>N</strong> &middot; <a href="...">Manage</a>`.
  When count > 0, also shows the mode pill (`full_matrix` etc.).
- New preview templates:
  - `operator/assignments_preview_full_matrix.html`
  - `operator/assignments_preview_manual.html`
  Both extend `base.html`, render coverage stats and the
  `validation_results.html` partial.

### 3.11 Test strategy

Same as Segment 6: pure parse / generation logic in `tests/unit/`;
end-to-end via `TestClient` in `tests/integration/`. Re-uses the
savepoint-isolated `db` fixture and `make_client` factory introduced
in Segment 5.

---

## 4. File and folder layout

### Added in PR 1 (FullMatrix + hub)

```text
alembic/versions/
  <rev>_add_assignment_mode_to_sessions.py            # NEW

app/
  db/models/review_session.py                         # MODIFIED: assignment_mode
  schemas/
    assignments.py                                    # NEW (AssignmentMode enum)
  services/
    assignments.py                                    # NEW (generate, replace, default-instrument helper)
  web/
    routes_operator.py                                # MODIFIED: 4 new endpoints
    templates/operator/
      session_detail.html                             # MODIFIED: assignments line
      session_assignments.html                        # NEW (hub)
      assignments_preview_full_matrix.html            # NEW

tests/
  unit/
    test_assignments_full_matrix.py                   # NEW
  integration/
    test_assignment_routes.py                         # NEW
```

### Added in PR 2 (Manual CSV)

```text
app/
  schemas/assignments.py                              # MODIFIED: ManualAssignmentRow
  services/assignments.py                             # MODIFIED: parse_manual_csv, manual save
  web/
    routes_operator.py                                # MODIFIED: 1 new endpoint (manual import)
    templates/operator/
      session_assignments.html                        # MODIFIED: enable manual section
      assignments_preview_manual.html                 # NEW

tests/
  unit/
    test_assignments_manual.py                        # NEW
  integration/
    test_assignment_routes.py                         # MODIFIED: append manual tests
```

---

## 5. Routes

### PR 1

| Method | Path                                                   | Form fields                                              | What it does |
|--------|--------------------------------------------------------|----------------------------------------------------------|--------------|
| GET    | `/operator/sessions/{id}/assignments`                  | —                                                        | Hub page (counts + both forms) |
| POST   | `/operator/sessions/{id}/assignments/full-matrix`      | `exclude_self_review` (checkbox), `dry_run`, `confirm_replace` | dry_run=true → preview HTML; dry_run=false → save + 303 → hub |

### PR 2

| Method | Path                                                  | Form fields                                              | What it does |
|--------|-------------------------------------------------------|----------------------------------------------------------|--------------|
| POST   | `/operator/sessions/{id}/assignments/manual/import`   | `file` (CSV), `dry_run`, `confirm_replace`               | dry_run=true → preview HTML; dry_run=false → save + 303 → hub |

---

## 6. Tests

### PR 1 (10 tests on top of 56 existing)

**Unit (`tests/unit/test_assignments_full_matrix.py`)**

1. `generate_full_matrix` produces `len(reviewers) × len(reviewees)`
   rows when `exclude_self_review=False`.
2. `generate_full_matrix` excludes self-review when configured
   (reviewer email matches reviewee email_or_identifier).
3. `generate_full_matrix` does not exclude when reviewee identifier
   is not an email (no `@`), regardless of toggle.
4. `get_or_create_default_instrument` creates an Instrument on first
   call and returns the same one on second call.

**Integration (`tests/integration/test_assignment_routes.py`)**

5. POST `full-matrix?dry_run=true` returns 200 with the expected
   count and writes no `Assignment` rows.
6. POST `full-matrix?dry_run=false` (no existing rows) saves +
   redirects, sets `session.assignment_mode = "full_matrix"`, writes
   `assignments.generated` audit event with the correct detail.
7. Re-running save without `confirm_replace=true` returns 400 and
   does not touch existing assignments.
8. Re-running save with `confirm_replace=true` replaces; audit event
   records `replaced_count > 0`.
9. The hub page (`GET /assignments`) renders the assignment count
   and mode pill after a successful generation.
10. Non-operator gets 403 on the hub page and on
    `POST .../full-matrix`.

### PR 2 (9 tests)

**Unit (`tests/unit/test_assignments_manual.py`)**

11. Valid manual CSV parses to the expected rows.
12. Unknown `ReviewerEmail` is a blocking error pointing at the row.
13. Unknown `RevieweeEmail` (no matching `email_or_identifier`) is a
    blocking error.
14. Duplicate `(reviewer, reviewee)` pair across rows is a blocking
    error.
15. `IncludeAssignment` parses the documented truthy/falsy strings;
    unparseable values are blocking; absent column defaults to true.
16. `AssignmentContext1`/`2`/`3` land in `Assignment.context` JSON
    under `context_1`/`2`/`3`.

**Integration (`tests/integration/test_assignment_routes.py`)**

17. POST `manual/import?dry_run=true` returns 200 with parsed counts
    and writes no rows.
18. POST `manual/import?dry_run=false` saves + writes
    `assignments.generated` with `mode="manual"`, `filename` set.
19. Non-operator gets 403 on `POST .../manual/import`.

---

## 7. Documentation

- `docs/imports.md` — extended with a "ManualAssignment CSV" section
  (column reference + example block + truthy/falsy table for
  `IncludeAssignment`). **PR 2.**
- A new `docs/assignments.md` is **not** added in this segment — the
  hub page itself documents the workflow well enough; a user-facing
  guide can land alongside the activation segment.

---

## 8. Out of scope (per parent plan §3 + new deferrals)

Carried over from parent plan:

- RuleBased assignment builder, random allocation, multi-instrument
  assignments, activation, invitations, reviewer response UI.

Newly clarified deferrals:

| Item                                                | Deferred to |
|-----------------------------------------------------|-------------|
| Server-side draft table for partially-uploaded imports | Not planned (re-upload pattern is sufficient at MVP scale) |
| Append / merge assignment policy                    | Possibly Segment 12 if RuleBased re-runs need it |
| Multiple Instruments per session                    | Segment 8 |
| Renaming the "Default" Instrument                   | Segment 8 |
| Per-assignment instrument selection in CSV          | Segment 8 |
| Coverage warnings as blocking errors                | Activation gate (Segment 9 or later) |

---

## 9. Verification checklist

### PR 1

- [ ] `pytest` green locally (56 existing + 10 new = 66 minimum).
- [ ] CI green: `test`, `postgres-migration` (round-trips the
  `assignment_mode` migration on `postgres:16`).
- [ ] After deploy: `migrate` job applies `assignment_mode`
  migration cleanly against Azure Postgres.
- [ ] After deploy: signed-in operator on a session with reviewers +
  reviewees can preview a FullMatrix and see expected counts; no
  `assignments` rows yet.
- [ ] After deploy: confirming the preview saves; hub page shows
  count + mode; `audit_events` row visible
  (`event_type='assignments.generated'`, `detail->>'mode'='full_matrix'`).
- [ ] After deploy: re-generating without `confirm_replace` blocked;
  with checkbox replaces and audit records `replaced_count > 0`.
- [ ] After deploy: a different signed-in account hits 403 on the
  hub URL.

### PR 2

- [ ] `pytest` green (66 + 9 = 75 minimum).
- [ ] CI green.
- [ ] After deploy: operator uploads a 3-row manual CSV → preview
  shows 3 rows + 0 errors → re-uploads + saves → hub page shows
  count and `manual` mode pill.
- [ ] After deploy: a CSV with an unknown reviewer email blocks at
  preview and never writes rows.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| FullMatrix generates a huge number of rows (e.g. 100×100=10000) and the operator doesn't notice | Preview shows the count before save (§3.4). Replace-guardrail forces explicit consent on re-generation. |
| Operator wrote a manual CSV against last semester's roster — unknown emails everywhere | Preview shows blocking errors per row before save; nothing is written. |
| Race between preview and save changes the underlying roster | Acceptable for single-operator MVP. Saved counts may differ slightly from preview (FullMatrix re-computes; Manual re-parses the freshly re-uploaded file). |
| Placeholder "Default" Instrument confuses operators in Segment 8 | Segment 8 will replace/rename the placeholder. Until then, the name "Default" makes its purpose clear. |
| `Assignment.UniqueConstraint(session_id, reviewer_id, reviewee_id, instrument_id)` is violated by accidental dupes in code | All saves go through `replace_assignments`, which deletes-then-inserts in one transaction. The constraint is defence-in-depth. |
| Migration breaks on Postgres but works on SQLite | The `ci-postgres-migration.yml` job from Segment 5 PR 1 round-trips the migration on `postgres:16` before merge. |
| Permission check missed on a new assignment route | All new routes depend on `require_session_operator` (introduced 6A). |

---

## 11. Done when

### PR 1

- Migration adds `assignment_mode` and round-trips on SQLite +
  Postgres.
- Placeholder `Default` Instrument helper works.
- FullMatrix preview + save flow works end-to-end on the deployed
  dev environment.
- Replace-guardrail blocks unconfirmed re-generation.
- `assignments.generated` audit events are written with the correct
  detail.
- All 10 PR-1 tests pass.

### PR 2

- ManualAssignment CSV preview + save flow works end-to-end.
- Unknown / duplicate / unparseable rows block at preview.
- All 9 PR-2 tests pass.

Next segment after both PRs merge: **Segment 8 — Reviewer review-surface MVP**.
