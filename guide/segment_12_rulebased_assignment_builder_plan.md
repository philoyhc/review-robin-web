# Segment 12 Plan — RuleBased Assignment Builder

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 12 of the low-intensity workplan  
**Purpose:** Add rule-based assignment generation, preserving the core Review Robin concept in web-app form

---

## 1. Segment goal

Segment 12 adds RuleBased assignment generation after the simpler end-to-end loop works.

By the end of this segment, an operator should be able to define rules using reviewer and reviewee attributes, preview generated assignments, and apply them to a session.

This segment should emphasize correctness and explainability over UI sophistication.

---

## 2. Success criteria

Segment 12 is complete when:

1. Rule schema exists.
2. Operator can create and edit basic rules.
3. Rules can select reviewers and reviewees by status/attribute fields.
4. Include/exclude criteria are supported.
5. Self-review policy is supported.
6. Allocate-all policy is supported.
7. Rule preview shows generated assignment counts.
8. Applying rules writes assignments.
9. Rule generation is deterministic and test-covered.
10. Audit event records rule application.

---

## 3. Deliberately out of scope

Do not include at first:

- complex visual rule builder;
- unlimited criteria;
- advanced random allocation;
- weighted allocation;
- optimization algorithms;
- cross-session rule libraries;
- multi-instrument complexity unless Segment 13 has already landed.

---

## 4. Branch strategy

```bash
git checkout -b segment-11-rulebased-builder
```

Suggested PR title:

```text
Segment 12: Add RuleBased assignment builder
```

---

## 5. Rule model

A rule should minimally include:

- session id;
- rule id or order;
- rule name;
- enabled flag;
- target instrument, if applicable;
- criteria rows;
- policy rows;
- created/updated metadata.

A criterion row includes:

- side: Reviewer or Reviewee;
- field name;
- operator: Include or Exclude;
- field value.

A policy row includes:

- policy name;
- policy value.

Initial supported policies:

- AllowSelfReview: true/false;
- AllocateAll.

Add RandomNPerReviewer later only after AllocateAll is correct.

---

## 6. Rule preview

Rule preview should show:

- generated assignment count;
- reviewers selected;
- reviewees selected;
- reviewers with no generated assignments;
- reviewees with no generated assignments;
- self-review rows excluded;
- duplicate rows removed or warned;
- rule-specific warnings.

Preview must not write assignments unless the operator explicitly applies it.

---

## 7. Files to add or modify

```text
app/
  services/
    rule_engine.py
    assignment_service.py
    validation_service.py

  schemas/
    rules.py

  db/models/
    rule.py

  web/
    routes_operator.py
    templates/operator/
      session_rules.html
      session_rule_preview.html

tests/
  unit/
    test_rule_engine.py
  integration/
    test_rulebased_assignment_flow.py
```

---

## 8. Tests

Minimum tests:

1. Rule selects reviewers by reviewer Status1.
2. Rule selects reviewees by reviewee Status1.
3. Include criterion works.
4. Exclude criterion works.
5. AllowSelfReview=false removes self-review rows.
6. AllocateAll creates reviewer × reviewee rows after criteria.
7. Disabled rule produces no assignments.
8. Empty rule produces warning.
9. Preview does not save assignments.
10. Apply saves assignments and writes audit event.

---

## 9. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 12 RuleBased assignment builder.

Add:
- rule data model
- rule_engine.py
- rule editor page
- rule preview
- apply-generated-assignments action
- tests

Initial supported features:
- Reviewer/Reviewee criteria over Status1/Status2/Status3
- Include/Exclude criterion operators
- AllowSelfReview policy
- AllocateAll policy

Constraints:
- Do not implement random allocation yet.
- Keep preview side-effect free.
- Keep rule engine testable without rendering templates.
```

### Review prompt

```text
Review this RuleBased PR.

Check:
- Is the rule engine deterministic?
- Is preview side-effect free?
- Are include/exclude semantics clear?
- Is self-review handled correctly?
- Are tests covering edge cases?
- Is the operator able to understand the preview?
```

---

## 10. Suggested GitHub issues

### Issue 1 — Add rule model and schema

Acceptance criteria:

- rules and criteria can be stored;
- migration applies;
- tests pass.

### Issue 2 — Add rule engine for AllocateAll

Acceptance criteria:

- criteria filter reviewer/reviewee sets;
- generated pairs are correct;
- tests cover include/exclude and self-review.

### Issue 3 — Add rule preview UI

Acceptance criteria:

- preview counts shown;
- preview does not save assignments.

### Issue 4 — Add apply rules action

Acceptance criteria:

- generated assignments save;
- audit event written.

---

## 11. Common mistakes to avoid

- Letting preview mutate assignments.
- Making rules too flexible before core semantics are stable.
- Implementing random allocation before deterministic AllocateAll.
- Hiding why a rule produced zero assignments.
- Failing to audit rule application.

---

## 12. Completion note template

```markdown
## Segment 12 completion note

Completed:
- RuleBased model
- rule engine
- rule preview
- apply rules action
- tests

Verified:
- include/exclude criteria work
- self-review policy works
- preview is side-effect free
- apply writes assignments and audit event
- tests pass

Deferred:
- random allocation
- advanced rule UI
- reusable rule libraries
```

---

## 13. Final checkpoint

- [ ] Rules can be defined.
- [ ] Rule preview works.
- [ ] Rule application writes assignments.
- [ ] Rule engine tests pass.
- [ ] Operator can understand generated counts.

Next segment: **Multi-instrument sessions**.

