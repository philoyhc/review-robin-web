# Segment 6 Plan — Import and Validation MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 6 of the low-intensity workplan  
**Purpose:** Allow operators to populate reviewers and reviewees, then validate basic session setup

---

## 1. Segment goal

Segment 6 gives the operator a way to get real data into a session.

By the end of this segment, an operator should be able to upload simple CSV files for reviewers and reviewees, preview validation issues, save valid rows, and run a basic setup validation check.

This segment establishes the import/validation pattern that later assignment, instrument, and export checks can reuse.

---

## 2. Success criteria

Segment 6 is complete when:

1. Reviewer CSV upload exists.
2. Reviewee CSV upload exists.
3. Import preview shows parsed rows and issues.
4. Required columns are validated.
5. Duplicate identifiers are caught.
6. Email format is validated where applicable.
7. Valid rows can be saved to the session.
8. A setup validation page summarizes errors, warnings, and info.
9. Import and validation tests pass.

---

## 3. Deliberately out of scope

Do not include:

- Excel upload;
- complex column mapping UI;
- assignment import;
- instruments;
- activation;
- reviewer surface;
- email invitations.

CSV first. Keep it simple.

---

## 4. Branch strategy

```bash
git checkout -b segment-6-import-validation
```

Suggested PR title:

```text
Segment 6: Add reviewer/reviewee import and setup validation MVP
```

---

## 5. CSV formats

### 5.1 Reviewer CSV

Required columns:

```text
ReviewerName,ReviewerEmail
```

Optional columns for future use:

```text
Status1,Status2,Status3
```

### 5.2 Reviewee CSV

Required columns:

```text
RevieweeName,RevieweeEmail
```

Optional columns:

```text
PhotoLink,Status1,Status2,Status3
```

For Segment 6, custom columns may be ignored or stored later. Do not overbuild flexible schema handling yet unless already easy.

---

## 6. Files to add or modify

```text
app/
  services/
    import_service.py
    validation_service.py

  schemas/
    imports.py
    validation.py

  web/
    routes_operator.py
    templates/operator/
      session_import_reviewers.html
      session_import_reviewees.html
      session_validate.html
      partials/validation_results.html

tests/
  unit/
    test_import_service.py
    test_validation_service.py
  integration/
    test_import_routes.py
```

---

## 7. Validation result pattern

Create a reusable validation result object.

Recommended shape:

```text
ValidationIssue
- severity: Error | Warning | Info
- source: e.g. Reviewers, Reviewees, Session
- row_number: optional
- field: optional
- message
- detail: optional
```

This mirrors the existing Review Robin discipline of separating blocking errors from warnings and informational notes.

---

## 8. Import workflow

Recommended workflow:

1. Operator opens session detail.
2. Operator clicks Import Reviewers or Import Reviewees.
3. Operator uploads CSV.
4. System parses file.
5. System shows preview:
   - rows parsed;
   - valid rows;
   - row-level errors;
   - warnings.
6. Operator confirms save if no blocking errors.
7. System replaces or appends rows according to chosen simple policy.

For MVP, use replace-all-with-confirmation or append-only. Prefer replace-all before activation because it is simpler.

---

## 9. Setup validation MVP

Add a validation page for the session.

Checks:

- session has name and code;
- session has at least one reviewer;
- session has at least one reviewee;
- reviewer emails are unique;
- reviewee identifiers are unique;
- no malformed emails;
- no blocking structural issue.

Later checks for instruments, assignments, invitation templates, and export columns will be added in later segments.

---

## 10. Tests

Minimum tests:

1. Valid reviewer CSV parses successfully.
2. Missing `ReviewerEmail` column produces blocking error.
3. Duplicate reviewer email produces blocking error.
4. Invalid reviewer email produces blocking error.
5. Valid reviewee CSV parses successfully.
6. Missing `RevieweeName` column produces blocking error.
7. Setup validation fails when no reviewers exist.
8. Setup validation passes basic reviewer/reviewee checks.

---

## 11. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 6 import and validation MVP.

Add CSV import for reviewers and reviewees with preview and validation.
Add a reusable ValidationIssue model with severity Error/Warning/Info.
Add setup validation page for basic session readiness.

Constraints:
- CSV only.
- No Excel upload yet.
- No assignments or instruments yet.
- Keep import logic in import_service.py.
- Keep validation logic in validation_service.py.
- Add tests for malformed CSV and duplicate emails.
```

### Review prompt

```text
Review this import/validation PR.

Check:
- Are imports safe and bounded?
- Are row-level errors clear?
- Are duplicate identifiers caught?
- Is validation reusable for later segments?
- Are route handlers thin?
- Are tests sufficient?
```

---

## 12. Suggested GitHub issues

### Issue 1 — Add validation issue model

Acceptance criteria:

- Error/Warning/Info severities exist;
- validation result can be rendered in UI;
- tests cover severity counts.

### Issue 2 — Add reviewer CSV import

Acceptance criteria:

- valid CSV previews;
- invalid columns/rows show errors;
- rows can be saved.

### Issue 3 — Add reviewee CSV import

Acceptance criteria:

- valid CSV previews;
- invalid columns/rows show errors;
- rows can be saved.

### Issue 4 — Add basic setup validation page

Acceptance criteria:

- session validation summarizes errors/warnings/info;
- tests cover empty and populated sessions.

---

## 13. Common mistakes to avoid

- Building a flexible column mapper too early.
- Supporting Excel upload before CSV works.
- Saving invalid rows without clear operator confirmation.
- Hiding import errors in logs instead of showing them in the UI.
- Making validation logic route-specific instead of reusable.

---

## 14. Completion note template

```markdown
## Segment 6 completion note

Completed:
- reviewer CSV import
- reviewee CSV import
- import preview and row-level validation
- reusable validation issue model
- basic setup validation page
- tests

Verified:
- valid imports save
- malformed imports show errors
- setup validation works
- tests pass

Deferred:
- Excel upload
- assignment import
- instruments
- activation
```

---

## 15. Final checkpoint

- [ ] Reviewer import works.
- [ ] Reviewee import works.
- [ ] Import errors are visible.
- [ ] Setup validation works.
- [ ] Tests pass.
- [ ] No assignment or activation logic was added prematurely.

Next segment: **Assignment generation MVP**.

