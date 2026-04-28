# Segment 9 Plan — Invitation, Monitoring, Reminder, and Instrument Open/Close MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 9 of the low-intensity workplan  
**Purpose:** Allow operators to activate a session, invite reviewers, monitor progress, send simple reminders, and stop accepting responses on a per-Instrument basis (manually or by deadline)

---

## 1. Segment goal

Segment 9 connects the operator setup workflow to the reviewer workflow,
and gives the operator control over when an Instrument stops accepting
responses.

By the end of this segment, an operator should be able to:

- activate a configured session;
- generate invitation records;
- send invitation emails or simulate sending in development;
- monitor reviewer progress;
- send simple reminders to incomplete reviewers;
- stop and resume accepting responses on an Instrument, either by
  setting a deadline that closes the Instrument when it passes, or by
  manually toggling the state.

This is the first segment where Review Robin Web feels like an operational system rather than only a configuration tool.

The Instrument open/close gate is what stops the
"reviewers can submit a year after the session is over" failure mode.
It is per-Instrument (not per-session) so that, once multi-instrument
ships in Segment 13, different instruments under one session can close
on different schedules.

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
9. Each Instrument has an explicit accepting-responses state plus an
   optional `closes_at` deadline; reviewer save / submit are blocked at
   the route layer when the Instrument is not accepting responses.
10. Operator can toggle the Instrument's accepting-responses state and
    set / clear its deadline from a session sub-page.
11. Activation, invitation, reminder, and Instrument open/close
    actions write audit events.
12. Tests cover activation, invitation creation, and the Instrument
    open/close gate (including the route-level block on save / submit).

---

## 3. Deliberately out of scope

Do not include:

- production-grade bulk email tuning;
- bounce tracking unless easy;
- sophisticated reminder filters;
- Azure Functions if a simple development stub is sufficient first;
- complex magic-link policies;
- full retention/export workflow;
- per-session (rather than per-Instrument) open/close — the response
  window is owned by each Instrument, not the session as a whole;
- automatic re-open behaviour (e.g. extending a deadline as a
  reviewer submits late). The operator manually re-opens an
  Instrument if they want to allow more responses.

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

## 9A. Per-Instrument open/close

### Schema additions

Two new columns on `Instrument`:

- `accepting_responses: bool` — defaults to `true`. Authoritative
  flag the route layer reads.
- `closes_at: datetime | None` — optional deadline. When the
  current time passes `closes_at`, the Instrument is treated as
  not accepting responses regardless of the boolean.

The effective state is `accepting_responses AND (closes_at IS NULL
OR now() < closes_at)`. Service helper
`is_instrument_accepting(instrument, now=None)` centralises the
rule so the reviewer routes and the operator UI compute it the same
way.

Alembic migration adds the two columns with the
default-`true` / default-`null` values, so existing sessions
post-Segment 8 stay open by default after upgrade.

### Operator surface

A new section on the existing session detail page (or a small
sub-page `/operator/sessions/{id}/instruments/{instrument_id}`)
exposes per-Instrument state:

- Current effective state pill: `accepting` (green) /
  `not accepting` (grey).
- `closes_at` field (datetime input; clearable).
- Toggle button: **Stop accepting responses** /
  **Resume accepting responses**.

Until multi-instrument ships in Segment 13, each session has
exactly one Instrument (the Default), so the surface is
single-row.

### Route-layer enforcement

Reviewer routes added in Segment 8 gain a guard:

- `POST /reviewer/sessions/{id}/save` and
  `POST /reviewer/sessions/{id}/submit` look up the assignments'
  Instrument(s) and 409 if any of them are not accepting responses.
- `GET /reviewer/sessions/{id}` still renders, but read-only when
  the Instrument is not accepting (inputs disabled, banner shown,
  Save / Submit buttons hidden; Cancel still works).
- `POST /reviewer/sessions/{id}/clear` is also blocked while not
  accepting (clearing after closure could erase submitted data).

### Audit events

```python
AuditEvent(
    event_type="instrument.closed",
    summary=f"Stopped accepting responses on instrument {name}",
    detail={"instrument_id": ..., "session_id": ..., "reason": "manual" | "deadline"},
)
AuditEvent(
    event_type="instrument.reopened",
    summary=f"Resumed accepting responses on instrument {name}",
    detail={"instrument_id": ..., "session_id": ...},
)
AuditEvent(
    event_type="instrument.deadline_set",
    summary=f"Set deadline on instrument {name}",
    detail={"instrument_id": ..., "session_id": ..., "closes_at": iso8601},
)
```

A `reason: "deadline"` close event is written lazily — the first
time an authoritative request observes `now() >= closes_at` and
flips behaviour. Optional polish: a periodic job that emits the
event at the actual moment. Defer to a later segment if the lazy
approach is sufficient.

### Tests for the gate

- Reviewer save while accepting: 303 → ok.
- Reviewer save while `accepting_responses = false`: 409.
- Reviewer save after `closes_at` has passed: 409.
- Reviewer submit while not accepting: 409.
- Reviewer GET while not accepting: 200 with read-only banner;
  no Save / Submit buttons.
- Operator toggle to stop: pill flips; audit event written.
- Operator toggle to resume: pill flips; audit event written.
- Setting `closes_at` to a past time has the same effect as
  toggling off.
- Existing Segment 8 reviewer-flow tests still pass with the
  default `accepting_responses = true`.

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
    instruments.py                      # MODIFIED: is_instrument_accepting,
                                        # set/clear deadline, toggle helpers
    responses.py                        # MODIFIED: 409 when target
                                        # instrument is not accepting

  schemas/
    invitations.py
    monitoring.py
    instruments.py                      # NEW: deadline / toggle payloads

  web/
    routes_operator.py                  # MODIFIED: instrument open/close routes
    routes_reviewer.py                  # MODIFIED: route-layer gate
    templates/operator/
      session_activate.html
      session_monitor.html
      session_invitations.html
      session_instrument.html           # NEW: single-instrument open/close UI
    templates/reviewer/
      review_surface.html               # MODIFIED: read-only banner

alembic/versions/
  XXXXXXXX_add_instrument_open_close.py # NEW

tests/
  unit/
    test_activation_service.py
    test_invitation_service.py
    test_monitoring_service.py
    test_instrument_open_close.py       # NEW
  integration/
    test_activation_invitation_flow.py
    test_instrument_open_close_flow.py  # NEW
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
- [ ] Operator can stop / resume accepting responses on an
  Instrument.
- [ ] Operator can set / clear an Instrument's `closes_at`.
- [ ] Reviewer save / submit are 409'd when the Instrument is
  not accepting responses (manual or deadline).
- [ ] Reviewer surface renders read-only when the Instrument is
  not accepting responses.
- [ ] Audit events written for activation, reminders, and
  Instrument open/close.
- [ ] Tests pass.

Next segment: **Export, audit, and retention MVP**.

