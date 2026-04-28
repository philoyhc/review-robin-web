# Segment 6A — Import and Validation MVP (Agreed Plan)

**Project:** Review Robin Web
**Repository:** <https://github.com/philoyhc/review-robin-web>
**Parent plan:** `guide/segment_06_import_validation_mvp_plan.md`
**Purpose:** Lock in the implementation choices for Segment 6 — import
flow shape, schema additions, validation primitive, naming — so the
implementation sessions can ship without re-litigating design.

This document is a **delta** on the parent plan. The parent plan still
governs scope, success criteria, and out-of-scope items.

---

## 1. Scope (unchanged from parent plan)

- Reviewer CSV import: parse, validate, save (replace-all per session).
- Reviewee CSV import: parse, validate, save (replace-all per session).
- Reusable `ValidationIssue` primitive.
- Setup validation page summarizing session readiness.
- Schema additions: three nullable tag columns on each of `reviewers`
  and `reviewees` (replaces the parent plan's `Status1/2/3` placeholder).

---

## 2. Branch and PR strategy

Two PRs against `main`, in order:

### PR 1 — Imports (`claude/segment-6-csv-imports`)

Schema migration adding tag columns; `ValidationIssue` primitive;
reviewer and reviewee CSV import routes, services, templates, and
tests; `require_session_operator` dependency extracted into
`app/web/deps.py`.

### PR 2 — Setup validation (`claude/segment-6-setup-validation`)

`validate_session_setup` service function; `/operator/sessions/{id}/validate`
route + template; tests. Lands once PR 1 is merged so the validation
checks have real reviewers/reviewees to look at.

---

## 3. Decisions

### 3.1 One-shot import with replace-guardrail

There is **no preview / dry-run step**. The single POST is the import:

- If the CSV has any blocking errors, no rows are written; the form
  re-renders with the issue list inline.
- If the CSV is clean and there are no existing rows, save and redirect
  to the session detail page.
- If the CSV is clean **and the session already has rows of this type**,
  the POST must include a `confirm_replace=true` form field. Without it,
  the route returns 400 and the form re-renders with the warning
  ("This will replace 23 existing reviewers — confirm to proceed").

The submit button on the form starts disabled when an existing-rows
warning is shown and enables only after the operator ticks the confirm
checkbox.

Rationale (reviewed and accepted, not preview-based): a preview screen
catches parse-level mistakes, but those are *also* caught one-shot.
What a preview cannot catch — operator uploaded the wrong file but it
parses cleanly — is better mitigated by an explicit "you are about to
nuke N rows" guardrail than by a preview the operator will click
through.

### 3.2 Per-table scope

Reviewer import only touches the `reviewers` table for that session.
Reviewee import only touches `reviewees`. These are independent routes,
independent transactions, independent forms — a failed reviewee parse
does not affect reviewers (and structurally cannot, even on a future
bug, because the two routes never open transactions on each other's
tables).

### 3.3 CSV format and parsing

- **Format:** CSV only. Excel upload is deferred (parent plan §3).
- **Charset:** UTF-8 with optional BOM (`utf-8-sig`).
- **Line endings:** any (`csv.reader` handles this).
- **Empty trailing rows:** stripped silently.
- **Required-field empty cell:** blocking error for that row.
- **Max upload size:** 1 MB. **Max row count:** 5000. Both checked
  before parsing; either limit produces a single blocking error
  ("File too large", "Too many rows") with no row enumeration.
- **Unknown columns:** silently ignored (forward-compatible).
- **Email validation:** `re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)`.
  Lightweight and reusable. We deliberately do **not** add the
  `email-validator` package or use `pydantic.EmailStr`.

### 3.4 CSV column names

#### Reviewer CSV (PhotoLink intentionally absent)

| Column         | Required | Maps to                       |
|----------------|----------|-------------------------------|
| `ReviewerName` | yes      | `reviewers.name`              |
| `ReviewerEmail`| yes      | `reviewers.email`             |
| `ReviewerTag1` | no       | `reviewers.tag_1`             |
| `ReviewerTag2` | no       | `reviewers.tag_2`             |
| `ReviewerTag3` | no       | `reviewers.tag_3`             |

#### Reviewee CSV

| Column            | Required | Maps to                          |
|-------------------|----------|----------------------------------|
| `RevieweeName`    | yes      | `reviewees.name`                 |
| `RevieweeEmail`   | yes      | `reviewees.email_or_identifier`  |
| `PhotoLink`       | no       | `reviewees.profile_link`         |
| `RevieweeTag1`    | no       | `reviewees.tag_1`                |
| `RevieweeTag2`    | no       | `reviewees.tag_2`                |
| `RevieweeTag3`    | no       | `reviewees.tag_3`                |

CSV column names carry the `Reviewer`/`Reviewee` prefix so an operator
filling in a spreadsheet cannot confuse which file they are on. DB
column names drop the prefix because the table name is already the
disambiguator (`reviewer.tag_1` reads cleanly).

### 3.5 Schema migration

A single Alembic migration adds three nullable `String(255)` columns to
each of `reviewers` and `reviewees`:

```python
op.add_column("reviewers", sa.Column("tag_1", sa.String(255), nullable=True))
op.add_column("reviewers", sa.Column("tag_2", sa.String(255), nullable=True))
op.add_column("reviewers", sa.Column("tag_3", sa.String(255), nullable=True))
op.add_column("reviewees", sa.Column("tag_1", sa.String(255), nullable=True))
op.add_column("reviewees", sa.Column("tag_2", sa.String(255), nullable=True))
op.add_column("reviewees", sa.Column("tag_3", sa.String(255), nullable=True))
```

No data backfill needed — all `tag_*` columns are nullable. The CI
`postgres-migration` job (added in Segment 5 PR 1) round-trips this
on Postgres before merge.

### 3.6 Validation primitive

`app/schemas/validation.py`:

```python
from enum import Enum
from typing import Any
from pydantic import BaseModel

class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"

class ValidationIssue(BaseModel):
    severity: Severity
    source: str           # "reviewers" | "reviewees" | "session"
    row_number: int | None = None  # 1-based, header is 0
    field: str | None = None
    message: str
    detail: dict[str, Any] | None = None
```

Pydantic (not dataclass) because routes pass these to Jinja templates
and `BaseModel` plays better with `model_dump()` for any future JSON
endpoint.

### 3.7 Replace-all save semantics

For each import:

1. Open a single transaction.
2. `DELETE` all existing rows for the session (`reviewers` or `reviewees`).
3. `INSERT` the parsed rows.
4. Write a `reviewers.imported` (or `reviewees.imported`) audit event
   with `detail = {"replaced_count": N_old, "new_count": N_new,
   "filename": <original-filename>}` and the per-request
   `correlation_id`.
5. Commit.

`replaced_count == 0` means it was a first-time import. `replaced_count
> 0` is the auditable record that the operator ticked the confirm
checkbox.

### 3.8 Permissions

Every new route depends on a new `require_session_operator` dependency
(extracted from the inline check in `routes_operator.session_detail`):

```python
# app/web/deps.py
def require_session_operator(
    session_id: int,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> ReviewSession:
    if not permissions.user_can_view_session(db, user, session_id):
        raise HTTPException(403, "You do not have access to this session")
    review_session = sessions.get_for_user(db, user, session_id)
    if review_session is None:
        raise HTTPException(404)
    return review_session
```

`session_detail` in `routes_operator.py` is refactored to use it
(no behavior change). All four new import routes and the validate
route depend on it. This is the dependency-injection pattern that 5A
§11 said to introduce "in Segment 6 or 7."

### 3.9 Service / schema layout (continues 5A §3.9 conventions)

- `app/services/csv_imports.py` — `parse_reviewer_csv`,
  `parse_reviewee_csv`, `save_reviewers`, `save_reviewees`. Short
  module name (not `import_service.py` — `import` is a Python
  keyword and would force `import importlib` gymnastics).
- `app/services/validation.py` — `validate_session_setup` (added in
  PR 2). The `ValidationIssue` model itself lives in `app/schemas/`
  because it crosses the route/template boundary.
- `app/schemas/imports.py` — `ReviewerImportRow`, `RevieweeImportRow`
  (pydantic models for the per-row parse output, separate from the
  ORM models).
- `app/schemas/validation.py` — `Severity`, `ValidationIssue`.

### 3.10 UI / templates

- All new templates extend `base.html` (added in 5A).
- `session_detail.html` (existing) is updated so the "Next steps" list
  links the Reviewers and Reviewees items to their new import routes.
  Instruments and Assignments stay greyed out.
- Import forms use a `multipart/form-data` POST with a single
  `<input type="file" name="file" accept=".csv">`, plus a hidden
  `confirm_replace` checkbox shown only when the existing-row count
  is > 0.
- Validation issues render via a `partials/validation_results.html`
  partial: an `<h3>` per source (Reviewers, Reviewees, Session)
  followed by a colour-coded list (red / amber / blue for
  error / warning / info).

### 3.11 Test strategy

- **Unit tests** (`tests/unit/`) for pure parse + validation logic. No
  DB, no `TestClient`. Each test feeds a CSV string and asserts on the
  parsed rows + issues.
- **Integration tests** (`tests/integration/`) for the routes. Reuse
  the savepoint-isolated `db` fixture from
  `tests/integration/conftest.py`. Use the `client` fixture to issue
  multipart POSTs with `files={"file": ("reviewers.csv", csv_bytes,
  "text/csv")}`.
- The Postgres-migration CI job from Segment 5 PR 1 catches
  any portability gap in the new tag-columns migration before merge.

---

## 4. File and folder layout

### Added in PR 1 (imports)

```text
alembic/versions/
  <rev>_add_tag_columns_to_reviewer_and_reviewee.py   # NEW

app/
  db/models/reviewer.py                               # MODIFIED: tag_1/2/3
  db/models/reviewee.py                               # MODIFIED: tag_1/2/3
  schemas/
    imports.py                                        # NEW
    validation.py                                     # NEW (Severity, ValidationIssue)
  services/
    csv_imports.py                                    # NEW
  web/
    deps.py                                           # NEW (require_session_operator)
    routes_operator.py                                # MODIFIED: 4 new routes; refactor detail to use deps
    templates/
      operator/
        session_detail.html                           # MODIFIED: link import pages
        session_import_reviewers.html                 # NEW
        session_import_reviewees.html                 # NEW
        partials/
          validation_results.html                     # NEW

tests/
  unit/
    __init__.py                                       # NEW
    test_csv_imports.py                               # NEW
  integration/
    test_import_routes.py                             # NEW
```

### Added in PR 2 (setup validation)

```text
app/
  services/
    validation.py                                     # NEW (validate_session_setup)
  web/
    routes_operator.py                                # MODIFIED: /validate route
    templates/operator/
      session_detail.html                             # MODIFIED: "Run validation" link
      session_validate.html                           # NEW

tests/
  unit/
    test_validation.py                                # NEW
  integration/
    test_validation_routes.py                        # NEW
```

---

## 5. Routes

### PR 1

| Method | Path                                                | Auth     | What it does |
|--------|-----------------------------------------------------|----------|--------------|
| GET    | `/operator/sessions/{id}/reviewers/import`          | operator | Empty form; shows `existing_count` warning if > 0 |
| POST   | `/operator/sessions/{id}/reviewers/import`          | operator | Parse + (if clean & guardrail satisfied) replace-all + audit + 303 → detail; otherwise re-render form with issues |
| GET    | `/operator/sessions/{id}/reviewees/import`          | operator | Same |
| POST   | `/operator/sessions/{id}/reviewees/import`          | operator | Same |

### PR 2

| Method | Path                                  | Auth     | What it does |
|--------|---------------------------------------|----------|--------------|
| GET    | `/operator/sessions/{id}/validate`    | operator | Renders all `ValidationIssue`s for the session |

---

## 6. Audit event shapes

```python
# Reviewer import
AuditEvent(
    event_type="reviewers.imported",
    severity="info",
    summary=f"Imported {N_new} reviewers (replaced {N_old})",
    actor_user_id=user.id,
    session_id=session.id,
    detail={"replaced_count": N_old, "new_count": N_new, "filename": filename},
    correlation_id=request_correlation_id(),
)

# Reviewee import
AuditEvent(
    event_type="reviewees.imported",
    summary=f"Imported {N_new} reviewees (replaced {N_old})",
    # ... same shape ...
)
```

No audit event is written on a failed import (the transaction never
commits). No audit event is written on `?confirm_replace` rejection
(no DB write happened).

---

## 7. Tests

### PR 1 (`tests/unit/test_csv_imports.py` + `tests/integration/test_import_routes.py`)

Per parent plan §10 + §3.6 of this doc:

1. Valid reviewer CSV parses successfully → 2 rows, 0 issues.
2. Missing `ReviewerEmail` column produces 1 blocking error, 0 rows.
3. Duplicate reviewer email produces a blocking error pointing at the
   duplicate row.
4. Invalid reviewer email (`alice@`, `bob`, `@example.edu`) produces a
   blocking error.
5. Valid reviewee CSV parses successfully → 2 rows, 0 issues, including
   `PhotoLink` populating `profile_link`.
6. Missing `RevieweeName` column produces 1 blocking error.
7. Successful import writes a `reviewers.imported` audit event with
   `replaced_count=0` and `new_count=2` (and the same shape for
   reviewees).
8. Non-operator user gets **403** on `POST /operator/sessions/{id}/reviewers/import`.
9. Replace guardrail: POSTing a clean CSV when 1 reviewer already
   exists, **without** `confirm_replace=true`, returns **400** and
   does not write any rows.
10. Replace guardrail satisfied: same POST **with** `confirm_replace=true`
    succeeds and audit event records `replaced_count=1`.
11. UTF-8 BOM tolerance: a CSV starting with `﻿` parses as if
    the BOM were absent.
12. Unknown columns are ignored: a CSV with an extra `Department`
    column parses normally.

### PR 2 (`tests/unit/test_validation.py` + `tests/integration/test_validation_routes.py`)

Per parent plan §10 items 7–8:

13. Setup validation on an empty session: returns errors for
    "no reviewers", "no reviewees", info for "no instruments yet".
14. Setup validation on a session with valid reviewers + reviewees:
    returns 0 errors.
15. `/operator/sessions/{id}/validate` renders 200 with the issue list.
16. Non-operator user gets **403** on `/validate`.

Total: 12 tests in PR 1, 4 in PR 2 → 16 new tests on top of the 32
that exist after Segment 5.

---

## 8. Documentation

- Add a short `docs/imports.md` explaining the CSV column names, the
  replace-all-with-confirmation behaviour, and the size/row caps. Two
  example CSV blocks. **PR 1.**
- `docs/database.md` does not need an update — adding nullable columns
  is a non-event for the operational story.
- `deployment_dev.md` does not need an update — no new infra.

---

## 9. Out of scope (per parent plan §3 + new deferrals)

Carried over from parent plan:

- Excel upload, complex column mapping UI, assignment import,
  instruments, activation, reviewer surface, email invitations.

Newly clarified deferrals:

| Item                                                | Deferred to |
|-----------------------------------------------------|-------------|
| Two-step preview / dry-run                          | Not planned (replaced by guardrail per §3.1) |
| Append / merge import policy                        | Possibly Segment 11 if RuleBased needs it |
| Many-to-many tags (vs the 3 fixed tag columns)      | Not planned — 3 slots is enough for RuleBased |
| `email-validator` strict checking                   | Segment 13 |
| Importing custom instruments / status fields        | Segment 8 (instruments) |

---

## 10. Verification checklist

### PR 1

- [ ] `pytest` green locally (32 existing + 12 new = 44 minimum).
- [ ] CI green: `test`, `postgres-migration`.
- [ ] After deploy: `migrate` job applies the new tag-columns migration
  cleanly against Azure Postgres.
- [ ] After deploy: signed-in operator can upload a 2-row reviewer CSV
  → see redirect to detail page → see audit event row in
  `audit_events` (`event_type='reviewers.imported'`).
- [ ] After deploy: re-uploading without `confirm_replace` is blocked.
- [ ] After deploy: re-uploading with the checkbox ticked replaces
  cleanly and the audit event records the old + new counts.
- [ ] After deploy: a different signed-in account hits 403 on the
  first user's import URL.

### PR 2

- [ ] `pytest` green (44 + 4 = 48 minimum).
- [ ] CI green.
- [ ] After deploy: validation page on an empty session lists the
  expected errors; validation page on a populated session lists 0
  errors.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Operator uploads the wrong file to a populated session and clicks through the guardrail | The guardrail is a meaningful click-through ("23 will be replaced"). Audit event records `replaced_count` so the destruction is at least retroactively visible. We accept this risk for dev/MVP; production hardening (e.g. soft-delete with restore) is Segment 13. |
| Large CSV blows up memory | 1 MB / 5000-row hard cap before parsing. |
| CSV with mixed encodings produces mojibake | Force `utf-8-sig` decode; non-UTF-8 bytes raise a single blocking error. Strict ASCII-or-fail is overkill; mixed-encoding strict tolerance is overkill the other way. |
| `tag_*` columns become a dumping ground for free-form text | Accepted. They are user-defined buckets; RuleBased (Segment 11) will impose match/exclude semantics on whatever the operator put there. |
| Permission check missed on a new import route | `require_session_operator` dependency is mandatory for all new operator routes; the dependency raises a clear 403 if the user is not an operator. |
| Migration breaks on Postgres but works on SQLite | The `ci-postgres-migration.yml` job from Segment 5 PR 1 round-trips the migration on `postgres:16` before merge. |

---

## 12. Done when

### PR 1

- Migration adds tag columns and round-trips on both SQLite and Postgres.
- Reviewer + reviewee CSV import routes work end-to-end in the deployed
  dev environment.
- Replace guardrail blocks unconfirmed replacements.
- `reviewers.imported` and `reviewees.imported` audit events are written.
- All 12 PR-1 tests pass.

### PR 2

- Setup validation page renders for any session the operator owns.
- Empty / populated sessions produce the expected issue lists.
- All 4 PR-2 tests pass.

Next segment after both PRs merge: **Segment 7 — Assignment generation MVP**.
