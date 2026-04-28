# Segment 11 Plan — Export, Audit, and Retention MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 11 of the low-intensity workplan  
**Purpose:** Produce the final dataset and support basic audit and retention/deletion workflows

---

## 1. Segment goal

Segment 11 completes the first end-to-end Review Robin Web loop.

By the end of this segment, an operator should be able to export collected responses as CSV and/or Excel, review basic export readiness information, and apply a simple retention or deletion action.

This segment does not add analytics. The goal is clean data output for downstream analysis.

---

## 2. Success criteria

Segment 11 is complete when:

1. Long-format CSV export works.
2. Wide-format CSV or Excel export works.
3. Export includes reviewer, reviewee, instrument, assignment, response, and completion metadata.
4. Export readiness summary exists.
5. Export action writes an audit event.
6. Basic response-data deletion or retention action exists.
7. Deletion/retention action writes an audit event.
8. Tests verify export shape and deletion behavior.

---

## 3. Deliberately out of scope

Do not include:

- analytical dashboards;
- ranking/scoring;
- Power BI integration;
- anonymized export unless specifically required;
- scheduled retention jobs;
- legal-hold workflows;
- complex archival UI.

---

## 4. Branch strategy

```bash
git checkout -b segment-10-export-audit-retention
```

Suggested PR title:

```text
Segment 11: Add export, audit, and retention MVP
```

---

## 5. Export formats

### 5.1 Long-format export

One row per response value.

Suggested columns:

```text
SessionId
SessionCode
SessionName
InstrumentId
InstrumentName
ReviewerId
ReviewerName
ReviewerEmail
RevieweeId
RevieweeName
RevieweeEmail
AssignmentId
AssignmentContext1
AssignmentContext2
AssignmentContext3
ResponseFieldKey
ResponseFieldLabel
ResponseValue
SavedAt
SubmittedAt
AssignmentSubmitted
```

### 5.2 Wide-format export

One row per assignment.

Suggested columns:

```text
SessionId
SessionCode
SessionName
InstrumentName
ReviewerName
ReviewerEmail
RevieweeName
RevieweeEmail
AssignmentContext1
AssignmentContext2
AssignmentContext3
[one column per response field]
AssignmentSubmitted
LastSavedAt
SubmittedAt
```

For Excel export, each instrument can later become its own sheet. For MVP, a single worksheet is acceptable.

---

## 6. Export readiness summary

Before export, show:

- total reviewers;
- total assignments;
- submitted assignments;
- incomplete assignments;
- missing required responses;
- last response timestamp;
- whether session is active or closed;
- warning if exporting before all reviewers submit.

The operator may export incomplete data, but the export must include completion status.

---

## 7. Retention/deletion MVP

Add one conservative action first:

```text
Delete response data after export
```

The action should:

- require explicit confirmation;
- delete response values, not necessarily session configuration;
- preserve audit records;
- record who performed the action and when;
- make clear that deletion is irreversible within the app.

Do not automate scheduled deletion yet.

---

## 8. Files to add or modify

```text
app/
  services/
    export_service.py
    retention_service.py
    audit_service.py

  exports/
    csv_export.py
    excel_export.py
    shapes.py

  schemas/
    exports.py
    retention.py

  web/
    routes_operator.py
    templates/operator/
      session_export.html
      session_retention.html

tests/
  unit/
    test_export_shapes.py
    test_retention_service.py
  integration/
    test_export_generation.py
```

---

## 9. Tests

Minimum tests:

1. Long export includes expected rows.
2. Wide export includes one row per assignment.
3. Incomplete assignments are included with completion status.
4. Required missing responses appear in readiness summary.
5. Export action writes audit event.
6. Deletion removes response values but preserves session metadata.
7. Deletion writes audit event.

---

## 10. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 11 export, audit, and retention MVP.

Add:
- long-format CSV export
- wide-format CSV export
- export readiness summary
- export audit event
- delete-response-data action with confirmation
- retention audit event
- tests

Constraints:
- Do not add analytics or charts.
- Include incomplete assignments with completion status.
- Preserve audit records when response data is deleted.
```

### Review prompt

```text
Review this export/retention PR.

Check:
- Does export include enough metadata for downstream analysis?
- Are incomplete assignments represented clearly?
- Are response values deleted without deleting audit records?
- Are destructive actions confirmed and audited?
- Are tests sufficient?
```

---

## 11. Suggested GitHub issues

### Issue 1 — Add long-format export

Acceptance criteria:

- one row per response value;
- includes reviewer/reviewee/instrument metadata;
- tests pass.

### Issue 2 — Add wide-format export

Acceptance criteria:

- one row per assignment;
- response fields become columns;
- incomplete assignments included.

### Issue 3 — Add export readiness summary

Acceptance criteria:

- shows submitted/incomplete counts;
- warns on missing required responses.

### Issue 4 — Add delete-response-data action

Acceptance criteria:

- explicit confirmation;
- response values deleted;
- audit records preserved;
- action audited.

---

## 12. Common mistakes to avoid

- Exporting only submitted responses and silently omitting incomplete assignments.
- Losing assignment context in export.
- Deleting session configuration when only response data should be deleted.
- Treating application logs as audit records.
- Adding analysis features before export is solid.

---

## 13. Completion note template

```markdown
## Segment 11 completion note

Completed:
- long-format export
- wide-format export
- export readiness summary
- export audit event
- delete response data action
- retention audit event
- tests

Verified:
- export includes complete metadata
- incomplete assignments are represented
- deletion preserves audit records
- tests pass

Deferred:
- analytics
- scheduled retention
- anonymized exports
- production storage hardening
```

---

## 14. Final checkpoint

- [ ] Long export works.
- [ ] Wide export works.
- [ ] Export readiness summary works.
- [ ] Audit events are written.
- [ ] Response deletion works and is audited.
- [ ] Tests pass.

Next segment: **RuleBased assignment builder**.

