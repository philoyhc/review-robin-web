# Segment 12 Plan — Multi-Instrument Sessions

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 12 of the low-intensity workplan  
**Purpose:** Allow a session to contain multiple review instruments, with reviewers completing the relevant tabular forms within one session

---

## 1. Segment goal

Segment 12 adds the multi-instrument capability.

By the end of this segment, a session should be able to contain more than one instrument. Assignments should target a specific instrument, reviewers should see separate review surfaces by instrument, and exports should clearly identify the instrument associated with each response.

Single-instrument sessions must continue to work simply.

---

## 2. Success criteria

Segment 12 is complete when:

1. Operators can create multiple instruments within a session.
2. Each instrument has its own display fields and response fields.
3. Assignments target an instrument.
4. FullMatrix generation can generate assignments by instrument.
5. ManualAssignment import can specify instrument.
6. Reviewer dashboard groups work by instrument.
7. Reviewer review surface supports multiple instruments through tabs, sections, or separate pages.
8. Exports include instrument metadata.
9. Single-instrument sessions remain unaffected.
10. Tests cover single- and multi-instrument workflows.

---

## 3. Deliberately out of scope

Do not include:

- unlimited instruments;
- complex visual instrument designer;
- cross-instrument dependencies;
- conditional response fields;
- instrument-level analytics;
- per-instrument permission models.

Keep the model bounded.

---

## 4. Branch strategy

```bash
git checkout -b segment-12-multi-instrument
```

Suggested PR title:

```text
Segment 12: Add multi-instrument session support
```

---

## 5. Functional model

A session contains one or more instruments.

Each instrument defines:

- name;
- order;
- description/instructions;
- display fields;
- response fields;
- required-field rules.

Each assignment belongs to exactly one instrument.

A reviewer may have:

- assignments under one instrument;
- assignments under multiple instruments;
- different reviewee sets for different instruments.

---

## 6. Operator workflow

The operator should be able to:

1. open session instruments page;
2. see existing instruments;
3. create a new instrument;
4. edit instrument name/description/order;
5. define response fields;
6. define display fields;
7. preview whether assignments exist for each instrument.

For MVP, instrument deletion should be restricted or blocked if assignments/responses exist.

---

## 7. Assignment changes

### 7.1 FullMatrix

The operator should choose which instrument(s) FullMatrix generation applies to.

Simple MVP option:

- generate FullMatrix assignments for all active instruments.

Alternative:

- operator selects target instrument before generation.

### 7.2 ManualAssignment

Manual assignment CSV gains an `Instrument` column.

Suggested columns:

```text
ReviewerEmail,RevieweeEmail,Instrument
```

If `Instrument` is absent and the session has only one instrument, default to that instrument.

If multiple instruments exist and `Instrument` is absent, show a blocking error.

### 7.3 RuleBased

If Segment 11 is already implemented, rules should target an instrument.

If not, this can be deferred until RuleBased and multi-instrument are both active.

---

## 8. Reviewer workflow

Reviewer dashboard should show work grouped by instrument:

```text
Session A
  Instrument 1: 10 rows, 80% complete
  Instrument 2: 3 rows, not started
```

Reviewer surface options:

- tabs within one page;
- separate page per instrument;
- sections on one page.

For low-intensity implementation, separate page per instrument may be easiest:

```text
GET /reviewer/sessions/{session_id}/instruments/{instrument_id}
```

Tabs can be added later.

---

## 9. Export changes

All exports must include:

- instrument id;
- instrument name;
- instrument order.

Wide Excel export may later use one worksheet per instrument. For MVP, one combined sheet with instrument columns is acceptable.

---

## 10. Files to add or modify

```text
app/
  services/
    instrument_service.py
    assignment_service.py
    response_service.py
    export_service.py

  schemas/
    instruments.py

  web/
    routes_operator.py
    routes_reviewer.py
    templates/operator/
      session_instruments.html
      instrument_edit.html
    templates/reviewer/
      dashboard.html
      review_surface.html

tests/
  unit/
    test_instrument_service.py
    test_multi_instrument_assignments.py
  integration/
    test_multi_instrument_reviewer_flow.py
    test_multi_instrument_export.py
```

---

## 11. Tests

Minimum tests:

1. Session can have two instruments.
2. Instrument response fields are independent.
3. ManualAssignment requires instrument when multiple instruments exist.
4. FullMatrix creates assignments for selected/all instruments.
5. Reviewer sees instrument grouping.
6. Reviewer can submit responses for one instrument without submitting another.
7. Export includes instrument metadata.
8. Single-instrument session still works without specifying instrument in assignment import.

---

## 12. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 12 multi-instrument support.

Add:
- operator instrument management page
- assignments targeting instruments
- manual assignment import with Instrument column
- reviewer dashboard grouped by instrument
- reviewer surface route per instrument
- export instrument metadata
- tests

Constraints:
- Single-instrument sessions must still work simply.
- Do not add unlimited instruments.
- Do not implement complex tabs until separate instrument pages work.
```

### Review prompt

```text
Review this multi-instrument PR.

Check:
- Does the single-instrument workflow still work?
- Are assignments always tied to an instrument?
- Does reviewer access remain scoped correctly?
- Do exports identify instrument clearly?
- Are tests covering both single- and multi-instrument cases?
```

---

## 13. Suggested GitHub issues

### Issue 1 — Add instrument management UI

Acceptance criteria:

- operator can create/edit instruments;
- single default instrument exists for new sessions.

### Issue 2 — Update assignments for instruments

Acceptance criteria:

- assignments require instrument;
- manual import supports Instrument column;
- FullMatrix supports instruments.

### Issue 3 — Update reviewer surface for instruments

Acceptance criteria:

- dashboard groups by instrument;
- reviewer can open each instrument surface.

### Issue 4 — Update exports for instruments

Acceptance criteria:

- all export rows identify instrument;
- tests pass.

---

## 14. Common mistakes to avoid

- Breaking single-instrument sessions.
- Allowing assignments without instrument in multi-instrument sessions.
- Mixing response fields between instruments.
- Making the UI too sophisticated before the data model works.
- Forgetting instrument metadata in exports.

---

## 15. Completion note template

```markdown
## Segment 12 completion note

Completed:
- multi-instrument model support
- instrument management UI
- instrument-aware assignments
- reviewer grouping by instrument
- instrument-aware exports
- tests

Verified:
- single-instrument sessions still work
- multi-instrument sessions work end to end
- exports include instrument metadata
- tests pass

Deferred:
- advanced instrument designer
- per-instrument analytics
- complex tab UI polish
```

---

## 16. Final checkpoint

- [ ] Multiple instruments can be created.
- [ ] Assignments target instruments.
- [ ] Reviewer workflow supports instruments.
- [ ] Exports include instruments.
- [ ] Single-instrument workflow still works.
- [ ] Tests pass.

Next segment: **Production hardening**.

