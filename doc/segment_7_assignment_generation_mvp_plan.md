# Segment 7 Plan — Assignment Generation MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 7 of the low-intensity workplan  
**Purpose:** Allow operators to create reviewer-reviewee assignments using FullMatrix and ManualAssignment modes

---

## 1. Segment goal

Segment 7 turns reviewer and reviewee rosters into actual review work.

By the end of this segment, an operator should be able to generate FullMatrix assignments, import ManualAssignment rows, preview assignment counts, and save assignments to the database.

RuleBased mode is intentionally deferred.

---

## 2. Success criteria

Segment 7 is complete when:

1. Session has an assignment mode setting.
2. FullMatrix assignment generation works.
3. Self-review exclusion is supported.
4. Manual assignment CSV import works.
5. Assignment preview shows useful counts.
6. Invalid reviewer/reviewee references are caught.
7. Duplicate assignment rows are detected or handled explicitly.
8. Assignments can be saved.
9. Tests cover FullMatrix and ManualAssignment behavior.

---

## 3. Deliberately out of scope

Do not include:

- RuleBased assignment builder;
- random allocation policies;
- multi-instrument assignments unless required by the current model;
- activation;
- invitations;
- reviewer response UI.

---

## 4. Branch strategy

```bash
git checkout -b segment-7-assignment-generation
```

Suggested PR title:

```text
Segment 7: Add FullMatrix and ManualAssignment MVP
```

---

## 5. Assignment modes in this segment

### 5.1 FullMatrix

Every reviewer reviews every reviewee.

Option:

- exclude self-review when reviewer email equals reviewee email.

Generated assignment fields:

- session id;
- reviewer id;
- reviewee id;
- instrument id, if a default instrument already exists;
- include flag;
- created by mode = FullMatrix.

### 5.2 ManualAssignment

Operator uploads explicit rows.

Minimum CSV columns:

```text
ReviewerEmail,RevieweeEmail
```

Optional columns:

```text
IncludeAssignment,AssignmentContext1,AssignmentContext2,AssignmentContext3
```

For Segment 7, if `IncludeAssignment` is absent, default to true.

---

## 6. Files to add or modify

```text
app/
  services/
    assignment_service.py
    import_service.py
    validation_service.py

  schemas/
    assignments.py

  web/
    routes_operator.py
    templates/operator/
      session_assignments.html
      session_assignment_preview.html

tests/
  unit/
    test_assignment_service.py
  integration/
    test_assignment_routes.py
```

---

## 7. Assignment preview

The preview should show:

- total assignment rows;
- number of reviewers with at least one assignment;
- number of reviewees covered;
- reviewers with no assignments;
- reviewees with no assignments;
- duplicate assignment warnings;
- invalid references for manual uploads.

The operator should preview before committing assignments.

---

## 8. Save policy

For MVP, use a simple replace policy before activation:

- generating or importing assignments replaces existing assignments for the session;
- require clear confirmation in the UI;
- write an audit event.

Later, more nuanced append/update behavior can be added.

---

## 9. Tests

Minimum tests:

1. FullMatrix creates reviewer × reviewee assignments.
2. FullMatrix excludes self-review when configured.
3. FullMatrix includes self-review when configured.
4. ManualAssignment import resolves reviewer and reviewee references.
5. ManualAssignment import reports unknown reviewer.
6. ManualAssignment import reports unknown reviewee.
7. Duplicate manual assignment is detected.
8. Assignment preview counts are correct.
9. Saving assignments replaces prior assignments.

---

## 10. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 7 assignment generation MVP.

Add:
- FullMatrix assignment generation
- self-review exclusion option
- ManualAssignment CSV import
- assignment preview counts
- save/replace assignment action
- tests

Constraints:
- Do not implement RuleBased yet.
- Do not activate sessions yet.
- Keep generation logic in assignment_service.py.
- Use existing validation issue pattern.
```

### Review prompt

```text
Review this assignment generation PR.

Check:
- Is FullMatrix deterministic?
- Is self-review exclusion correct?
- Are manual assignment references validated?
- Are duplicate assignments handled?
- Is replace behavior clear and audited?
- Are tests sufficient?
```

---

## 11. Suggested GitHub issues

### Issue 1 — Add FullMatrix assignment generation

Acceptance criteria:

- generates expected row count;
- supports self-review exclusion;
- tests pass.

### Issue 2 — Add ManualAssignment CSV import

Acceptance criteria:

- valid rows preview;
- invalid references show errors;
- duplicates handled.

### Issue 3 — Add assignment preview and save action

Acceptance criteria:

- preview counts shown;
- assignments can be saved;
- audit event written.

---

## 12. Common mistakes to avoid

- Letting manual assignment rows create missing reviewers/reviewees automatically.
- Failing to handle self-review consistently.
- Saving assignments without preview.
- Adding RuleBased mode too early.
- Making assignment generation depend on UI state instead of data.

---

## 13. Completion note template

```markdown
## Segment 7 completion note

Completed:
- FullMatrix assignment generation
- self-review exclusion
- ManualAssignment import
- assignment preview
- assignment save/replace action
- tests

Verified:
- FullMatrix counts are correct
- manual references are validated
- assignments save to database
- tests pass

Deferred:
- RuleBased
- activation
- invitations
- reviewer surface
```

---

## 14. Final checkpoint

- [ ] FullMatrix works.
- [ ] ManualAssignment import works.
- [ ] Assignment preview works.
- [ ] Invalid references are caught.
- [ ] Assignments save correctly.
- [ ] Tests pass.

Next segment: **Reviewer review-surface MVP**.

