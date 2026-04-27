# Segment 8 Plan — Reviewer Review-Surface MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 8 of the low-intensity workplan  
**Purpose:** Allow a reviewer to access assigned work, enter tabular responses, save, and submit

---

## 1. Segment goal

Segment 8 builds the heart of the reviewer experience.

By the end of this segment, a reviewer should be able to:

- access their assigned review work;
- see assigned reviewees in a table;
- enter responses;
- save responses;
- return later and see saved data;
- submit completed work.

Start with a plain HTML table. Introduce AG Grid only after the server-side response logic works.

---

## 2. Success criteria

Segment 8 is complete when:

1. Reviewer dashboard exists.
2. Reviewer access is scoped to the authenticated reviewer.
3. A single-instrument review table renders assignments.
4. Response fields render as editable inputs.
5. Responses can be saved.
6. Saved responses reload correctly.
7. Submit action validates required fields.
8. Completion status updates after submit.
9. Tests cover reviewer access, response save, and submission.

---

## 3. Deliberately out of scope

Do not include:

- polished AG Grid behavior at first;
- multi-instrument tabs;
- autosave conflict handling;
- reminder emails;
- export generation;
- anonymous public access;
- complex late-submission policies.

---

## 4. Branch strategy

```bash
git checkout -b segment-8-reviewer-surface
```

Suggested PR title:

```text
Segment 8: Add reviewer response surface MVP
```

---

## 5. Reviewer workflow

1. Reviewer signs in or is represented by local fake identity during development.
2. System matches reviewer email to reviewer records.
3. Reviewer sees assigned session(s).
4. Reviewer opens a session review page.
5. Reviewer sees table of assigned reviewees.
6. Reviewer enters response values.
7. Reviewer saves.
8. Reviewer submits when complete.

---

## 6. Required pages and endpoints

### 6.1 Reviewer dashboard

```text
GET /reviewer
```

Shows:

- active sessions assigned to reviewer;
- deadline;
- completion state;
- link to review surface.

### 6.2 Review surface

```text
GET /reviewer/sessions/{session_id}
```

Shows:

- session name;
- instructions;
- assigned reviewees;
- response fields;
- save/submit controls.

### 6.3 Save responses

For first MVP, this can be a form post:

```text
POST /reviewer/sessions/{session_id}/save
```

Later, this can become a JSON autosave endpoint:

```text
POST /api/reviewer/responses/save
```

### 6.4 Submit

```text
POST /reviewer/sessions/{session_id}/submit
```

---

## 7. Files to add or modify

```text
app/
  services/
    response_service.py
    reviewer_service.py
    permission_service.py

  schemas/
    responses.py

  web/
    routes_reviewer.py
    templates/reviewer/
      dashboard.html
      review_surface.html
      review_submitted.html

  api/
    autosave.py  # optional, can wait until after form post works

tests/
  integration/
    test_reviewer_response_flow.py
  unit/
    test_response_service.py
```

---

## 8. Response field assumptions for MVP

To keep Segment 8 manageable, support a limited set of response types first:

- short text;
- long text;
- integer rating;
- yes/no or choice, if easy.

Required-field validation should work for text and simple rating fields.

---

## 9. Access control rules

The reviewer must only see assignments where:

- reviewer email matches authenticated identity; and
- assignment belongs to the session; and
- session is active or otherwise accessible.

Server-side checks are required on every reviewer route and save endpoint.

Do not rely on hidden form fields for authorization.

---

## 10. Tests

Minimum tests:

1. Reviewer sees only their assigned sessions.
2. Reviewer cannot access another reviewer's session surface.
3. Review table renders assigned rows.
4. Save creates response records.
5. Save updates existing response records.
6. Required-field validation blocks submit.
7. Submit succeeds when required responses are present.
8. Submitted status is recorded.

---

## 11. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 8 reviewer response surface MVP.

Start with a plain HTML table, not AG Grid.
Add:
- reviewer dashboard
- single-session review surface
- response save form post
- submit action with required-field validation
- reviewer-only access checks
- tests

Constraints:
- One instrument only for now.
- Do not add invitations or email yet.
- Do not add export yet.
- Keep response logic in response_service.py.
```

### Upgrade-to-grid prompt, later in the segment

```text
Replace the plain reviewer response table with a minimal AG Grid implementation.
Keep the same server-side response save logic.
Do not add new business rules.
```

### Review prompt

```text
Review this reviewer surface PR.

Check:
- Can a reviewer see only their own assignments?
- Are save and submit server-authorized?
- Are required fields validated server-side?
- Is the response data model preserved?
- Are tests sufficient?
```

---

## 12. Suggested GitHub issues

### Issue 1 — Add reviewer dashboard

Acceptance criteria:

- reviewer sees assigned sessions;
- non-assigned sessions are hidden and inaccessible.

### Issue 2 — Add plain HTML review table

Acceptance criteria:

- assigned reviewees render;
- response fields render;
- existing responses load.

### Issue 3 — Add response save and submit

Acceptance criteria:

- responses save;
- required validation works;
- submit status updates.

### Issue 4 — Optional: replace table with grid component

Acceptance criteria:

- grid renders same data;
- save endpoint still works;
- tests remain focused on server behavior.

---

## 13. Common mistakes to avoid

- Introducing AG Grid before response save logic works.
- Trusting reviewer id from a form field.
- Making submit only a client-side validation.
- Building multi-instrument UI too early.
- Losing saved responses when the page reloads.

---

## 14. Completion note template

```markdown
## Segment 8 completion note

Completed:
- reviewer dashboard
- reviewer review surface
- response save
- submit action
- required-field validation
- reviewer access tests

Verified:
- reviewer sees only own assignments
- responses persist
- submit status updates
- tests pass

Deferred:
- AG Grid polish
- multi-instrument UI
- invitations
- reminders
- export
```

---

## 15. Final checkpoint

- [ ] Reviewer dashboard works.
- [ ] Review surface works.
- [ ] Save works.
- [ ] Submit works.
- [ ] Access control tests pass.
- [ ] Plain table or first grid implementation is usable.

Next segment: **Invitation, monitoring, and reminder MVP**.

