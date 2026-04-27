# Segment 13 Plan — Production Hardening

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 13 of the low-intensity workplan  
**Purpose:** Make the application safer, more observable, more supportable, and more credible for a real internal pilot

---

## 1. Segment goal

Segment 13 hardens the application after the core functional loop exists.

By this point, the app should already support session setup, imports, assignments, reviewer responses, invitations, monitoring, export, and retention. Segment 13 improves operational readiness.

This is not about adding new Review Robin features. It is about making the existing system more reliable and supportable.

---

## 2. Success criteria

Segment 13 is complete when:

1. Production/staging deployment path is defined.
2. App settings are documented and separated by environment.
3. Structured logging exists.
4. Application Insights or equivalent monitoring is configured.
5. Common error paths show useful user-facing messages.
6. Database indexes are reviewed for main workflows.
7. Backup/restore expectations are documented.
8. Permission checks are reviewed.
9. Destructive actions are confirmed and audited.
10. Basic accessibility review is completed for the reviewer table.
11. Operator runbook exists.
12. Developer setup and troubleshooting notes are updated.

---

## 3. Deliberately out of scope

Do not include:

- major new features;
- new assignment modes;
- analytics dashboards;
- large UI redesign;
- institutional SIEM integration unless required;
- full penetration test;
- full WCAG audit, unless this is moving into institutional production.

---

## 3.1 Inherited from Segment 4A

Segment 4 (per `guide/segment_04A.md`) deliberately used cross-dialect column
types so the same migration runs on SQLite (tests) and PostgreSQL (deployed).
The following Postgres-specific optimizations were deferred here:

- **Migrate JSON columns to `JSONB`.** `AuditEvent.detail` and any other
  JSON columns introduced in later segments should be moved to `JSONB` for
  indexing and operator-friendly queries. Postgres-only migration; tests
  continue to run on SQLite using `JSON`.
- **Migrate string-UUID columns to native `UUID`.** Where Segment 4 used
  `String(36)` for UUID-shaped columns, swap to Postgres `UUID` for storage
  efficiency and constraint correctness. Add explicit casting in
  application code if needed.
- **Add a Postgres-against-Docker CI job.** Segment 4's `ci.yml` runs
  `pytest` against SQLite. Add a parallel job that spins up a Postgres
  service container (GitHub Actions `services:` block) and runs the test
  suite against it, so dialect drift is caught in CI rather than on
  deploy.
- **Review and add Postgres-specific indexes.** GIN indexes on `JSONB`
  columns where queried; partial indexes for frequently-filtered subsets;
  expression indexes if any.
- **Consider DB-level enums.** Where Segment 4 used `String` + Python enum
  validation (e.g. `AuditEvent.event_type`, `AuditEvent.severity`), decide
  per column whether a Postgres `ENUM` type is worth the migration cost.

These items belong in this segment because they only matter once the app is
heading toward a real internal pilot.

---

## 4. Branch strategy

This segment may be too broad for one PR. Prefer several smaller PRs.

Suggested branches:

```text
segment-13-logging-monitoring
segment-13-deployment-hardening
segment-13-permission-review
segment-13-runbooks-docs
segment-13-accessibility-pass
```

If using one branch:

```bash
git checkout -b segment-13-production-hardening
```

Suggested umbrella PR title:

```text
Segment 13: Production hardening pass
```

---

## 5. Hardening areas

## 5.1 Deployment hardening

Add or confirm:

- dev environment;
- staging slot or staging App Service;
- production environment plan;
- manual approval for production deployment;
- rollback or slot-swap notes;
- app settings per environment;
- secret-handling documentation.

Recommended production deployment flow:

```text
main branch → deploy to dev/staging → verify → manually approve production → deploy/swap
```

---

## 5.2 Configuration hardening

Document required environment variables:

- app environment;
- database URL;
- fake-auth setting;
- email mode;
- storage settings;
- Easy Auth assumptions;
- logging level;
- allowed hostnames, if enforced.

Add startup checks for missing critical settings in non-local environments.

---

## 5.3 Logging and observability

Add structured logs for:

- session activation;
- import failures;
- invitation send failures;
- reviewer save errors;
- export generation failures;
- permission denials;
- retention/deletion actions.

Configure Application Insights or Azure Monitor integration.

Distinguish:

- application logs;
- audit events;
- user-facing validation messages.

---

## 5.4 Error handling

Add user-friendly error pages or messages for:

- unauthorized access;
- session not found;
- invalid invitation link;
- expired/revoked link;
- validation failure;
- save failure;
- export failure.

Do not expose tracebacks or sensitive details to users.

---

## 5.5 Database performance and indexes

Review common query paths:

- sessions for operator;
- reviewers by session;
- reviewees by session;
- assignments by reviewer/session;
- responses by assignment;
- monitoring counts;
- export queries;
- audit events by session/date.

Add indexes where needed.

Write a short note explaining why each index exists.

---

## 5.6 Permission review

Review all routes and API endpoints.

Confirm:

- operator routes require operator permission;
- reviewer routes require matching reviewer identity or valid access link policy;
- admin routes require admin permission;
- export routes are protected;
- retention/deletion routes are protected;
- POST endpoints do not trust client-side identifiers without server verification.

Add tests for the most important denial paths.

---

## 5.7 Destructive action review

Review actions such as:

- delete response data;
- close session;
- reopen session;
- replace imported reviewers/reviewees;
- replace assignments;
- delete instrument;
- revoke link.

Confirm they require:

- explicit confirmation;
- permission check;
- audit event;
- clear user-facing warning.

---

## 5.8 Accessibility pass

Perform a basic accessibility pass, especially on the reviewer table.

Check:

- keyboard navigation;
- visible focus state;
- labels for form fields;
- sufficient contrast;
- error messages tied to fields;
- screen-reader reasonable structure;
- no mouse-only critical action.

This is not a full WCAG audit, but it should catch obvious problems before a pilot.

---

## 5.9 Backup and restore notes

Document:

- database backup mechanism;
- export file storage location;
- whether uploaded/import files are retained;
- what can be restored;
- who can restore;
- how long backups are retained;
- limitations.

For a personal/dev environment, this can be a simple note. For institutional deployment, this must align with institutional policy.

---

## 5.10 Runbooks and documentation

Add or update:

- operator runbook;
- developer setup guide;
- deployment guide;
- troubleshooting guide;
- known limitations;
- data retention note;
- security/compliance posture note.

---

## 6. Files to add or modify

```text
app/
  config.py
  logging_config.py
  web/
    error_handlers.py
  services/
    permission_service.py
    audit_service.py

docs/
  deployment.md
  operations_runbook.md
  troubleshooting.md
  backup_restore.md
  security_notes.md
  accessibility_notes.md
  known_limitations.md

.github/workflows/
  deploy-prod.yml
```

Database migration files may be added for indexes.

---

## 7. Tests to add

Minimum tests:

1. unauthorized operator route is denied;
2. reviewer cannot save another reviewer's response;
3. export route denies non-operator;
4. retention action denies non-operator;
5. destructive action writes audit event;
6. invalid invitation link shows safe error;
7. app fails fast on missing production-critical setting.

---

## 8. AI-assisted prompts

### Logging prompt

```text
Add structured logging for key Review Robin Web operations.

Do not replace audit events. Application logs and audit events should remain separate.
Add logs for activation, invitation send failure, response save failure, export failure, permission denial, and retention action.
```

### Permission review prompt

```text
Review all routes and API endpoints for authorization gaps.

Check specifically:
- operator session access
- reviewer response saving
- export access
- retention/deletion actions
- admin-only routes

Suggest tests for missing denial paths.
```

### Deployment hardening prompt

```text
Review the GitHub Actions deployment workflows and propose a production-safe version.

Requirements:
- dev deploy remains easy
- production deploy requires manual approval
- no secrets in repo
- environment-specific settings documented
```

### Accessibility prompt

```text
Review the reviewer table markup for basic accessibility.

Check keyboard navigation, labels, focus state, required-field messages, and screen-reader structure.
Suggest small fixes only.
```

---

## 9. Suggested GitHub issues

### Issue 1 — Add structured logging and monitoring hooks

Acceptance criteria:

- key operations logged;
- logs distinguish operation failures from audit records;
- docs updated.

### Issue 2 — Add production deployment workflow

Acceptance criteria:

- production deployment requires manual approval;
- environment settings documented;
- rollback notes exist.

### Issue 3 — Review and test permissions

Acceptance criteria:

- route permission review completed;
- denial tests added;
- gaps fixed.

### Issue 4 — Add operator runbook and troubleshooting docs

Acceptance criteria:

- operator can follow runbook for a test cycle;
- common errors documented.

### Issue 5 — Add accessibility pass for reviewer table

Acceptance criteria:

- keyboard/focus/labels checked;
- obvious issues fixed;
- notes documented.

---

## 10. Common mistakes to avoid

- Adding new features instead of hardening existing ones.
- Treating logs as audit records.
- Hiding permission failures behind generic errors.
- Enabling fake auth in production.
- Deploying to production automatically on every push.
- Forgetting to document restore limits.
- Overclaiming security or accessibility compliance.

---

## 11. Completion note template

```markdown
## Segment 13 completion note

Completed:
- deployment hardening
- environment setting documentation
- structured logging
- monitoring hooks
- permission review
- destructive action review
- accessibility pass
- runbooks and troubleshooting docs

Verified:
- key denial tests pass
- production deploy path is controlled
- fake auth disabled outside local/dev
- logs are visible
- audit events remain separate from logs

Deferred:
- full penetration test
- full WCAG audit
- institutional SIEM integration
- enterprise support model
```

---

## 12. Final checkpoint

- [ ] Deployment path is documented.
- [ ] Production deploy is controlled.
- [ ] Logs are useful.
- [ ] Monitoring is available.
- [ ] Permission checks are reviewed.
- [ ] Destructive actions are confirmed and audited.
- [ ] Basic accessibility pass completed.
- [ ] Operator runbook exists.
- [ ] Troubleshooting guide exists.
- [ ] Known limitations are documented.

After Segment 13, the application is ready for a cautious internal pilot, subject to institutional policy and data-classification approval.

