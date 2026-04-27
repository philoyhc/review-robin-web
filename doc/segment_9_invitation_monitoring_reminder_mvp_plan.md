# Segment 9 Plan — Invitation, Monitoring, and Reminder MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 9 of the low-intensity workplan  
**Purpose:** Allow operators to activate a session, invite reviewers, monitor progress, and send simple reminders

---

## 1. Segment goal

Segment 9 connects the operator setup workflow to the reviewer workflow.

By the end of this segment, an operator should be able to:

- activate a configured session;
- generate invitation records;
- send invitation emails or simulate sending in development;
- monitor reviewer progress;
- send simple reminders to incomplete reviewers.

This is the first segment where Review Robin Web feels like an operational system rather than only a configuration tool.

---

## 2. Success criteria

Segment 9 is complete when:

1. Session activation action exists.
2. Readiness validation blocks activation when required setup is incomplete.
3. Invitation records are generated for reviewers.
4. Individualized reviewer links are generated.
5. Email invitation sending exists or is safely stubbed in development.
6. Invitation status is tracked.
7. Monitoring page shows reviewer progress.
8. Reminder action exists for incomplete reviewers.
9. Invitation, activation, and reminder actions write audit events.
10. Tests cover activation and invitation creation.

---

## 3. Deliberately out of scope

Do not include:

- production-grade bulk email tuning;
- bounce tracking unless easy;
- sophisticated reminder filters;
- Azure Functions if a simple development stub is sufficient first;
- complex magic-link policies;
- full retention/export workflow.

---

## 4. Branch strategy

```bash
git checkout -b segment-9-invitations-monitoring
```

Suggested PR title:

```text
Segment 9: Add activation, invitations, monitoring, and reminders MVP
```

---

## 5. Activation workflow

Activation should:

1. run readiness validation;
2. block if errors exist;
3. mark session active;
4. generate invitation records for reviewers with assignments;
5. record activation audit event;
6. make reviewer dashboard/review surface accessible.

For MVP, activation can be irreversible except through an admin/developer action. A later segment can add reopen/close lifecycle controls.

---

## 6. Invitation model

Each invitation should track:

- session;
- reviewer;
- token or token hash;
- invitation status;
- sent timestamp;
- opened timestamp;
- last reminder timestamp;
- failure message, if any.

Suggested statuses:

```text
Pending
Sent
Failed
Opened
```

Do not overbuild the state machine yet.

---

## 7. Email approach for MVP

Use a layered strategy:

### Development mode

Emails may be written to log or local outbox table instead of actually sent.

### First real send

Use institutional SMTP if available. If not available, keep email sending stubbed until the email provider decision is settled.

### Later production path

Bulk sends should move to Azure Storage Queue + Azure Functions, but Segment 9 can begin with a simple synchronous or background-task implementation for small test sessions.

---

## 8. Monitoring dashboard MVP

The operator monitoring page should show:

- total reviewers with assignments;
- invitations pending;
- invitations sent;
- opened/accessed;
- not started;
- in progress;
- submitted;
- incomplete.

A simple table by reviewer is enough:

| Reviewer | Email | Invitation | Started | Submitted | Last Activity |
|---|---|---|---|---|---|

Do not build charts yet.

---

## 9. Reminder MVP

Add a simple action:

```text
Send reminder to incomplete reviewers
```

Incomplete means:

- not submitted; or
- required responses missing.

The reminder should:

- use a simple template;
- record reminder timestamp;
- write audit event;
- avoid sending to submitted reviewers.

---

## 10. Files to add or modify

```text
app/
  services/
    activation_service.py
    invitation_service.py
    reminder_service.py
    monitoring_service.py
    email_service.py

  schemas/
    invitations.py
    monitoring.py

  web/
    routes_operator.py
    templates/operator/
      session_activate.html
      session_monitor.html
      session_invitations.html

tests/
  unit/
    test_activation_service.py
    test_invitation_service.py
    test_monitoring_service.py
  integration/
    test_activation_invitation_flow.py
```

---

## 11. Tests

Minimum tests:

1. Activation blocked if no reviewers.
2. Activation blocked if no assignments.
3. Activation succeeds for valid setup.
4. Activation creates invitation records.
5. Invitation links are unique.
6. Monitoring counts submitted and incomplete reviewers.
7. Reminder selects only incomplete reviewers.
8. Audit events are written for activation and reminders.

---

## 12. AI-assisted prompts

### Implementation prompt

```text
Implement Segment 9 activation, invitation, monitoring, and reminder MVP.

Add:
- activation service
- invitation record generation
- simple invitation email service or dev outbox stub
- monitoring dashboard counts
- reminder action for incomplete reviewers
- audit events
- tests

Constraints:
- Keep email sending simple for MVP.
- Do not implement Azure Functions yet unless necessary.
- Do not add export or retention.
- Do not add complex reminder filters.
```

### Review prompt

```text
Review this Segment 9 PR.

Check:
- Does activation run readiness validation?
- Are invitation links unique and scoped?
- Are submitted reviewers excluded from reminders?
- Is email sending safe in development?
- Are audit events written?
- Are tests sufficient?
```

---

## 13. Suggested GitHub issues

### Issue 1 — Add session activation

Acceptance criteria:

- readiness validation gates activation;
- session status changes to active;
- audit event written.

### Issue 2 — Add invitation records and links

Acceptance criteria:

- one invitation per assigned reviewer;
- links are unique;
- tests verify uniqueness.

### Issue 3 — Add monitoring dashboard

Acceptance criteria:

- operator sees reviewer progress counts;
- submitted/incomplete counts are correct.

### Issue 4 — Add reminder action

Acceptance criteria:

- reminders target incomplete reviewers;
- action is audited.

---

## 14. Common mistakes to avoid

- Sending real emails unintentionally during development.
- Allowing activation with no assignments.
- Making invitation links guessable.
- Treating email sent as equivalent to reviewer completed.
- Building a complex dashboard before basic counts work.

---

## 15. Completion note template

```markdown
## Segment 9 completion note

Completed:
- activation
- invitation records
- invitation link generation
- email/dev outbox path
- monitoring dashboard
- reminder action
- audit events
- tests

Verified:
- valid session activates
- invalid session is blocked
- invitations are created
- monitoring counts update
- reminders target incomplete reviewers
- tests pass

Deferred:
- production bulk email
- bounce tracking
- advanced reminder filters
- export
- retention
```

---

## 16. Final checkpoint

- [ ] Activation works.
- [ ] Invitations are generated.
- [ ] Email/dev outbox behavior is safe.
- [ ] Monitoring works.
- [ ] Reminder action works.
- [ ] Tests pass.

Next segment: **Export, audit, and retention MVP**.

