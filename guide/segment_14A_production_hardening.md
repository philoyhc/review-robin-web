# Segment 14A — Production Hardening

**Project:** Review Robin Web
**Repository:** <https://github.com/philoyhc/review-robin-web>
**Purpose:** Make the application safer, more observable, more
supportable, and more credible for a real internal pilot

> **Carved out of the original Segment 14 (2026-05-11).** The
> original `segment_14_production_hardening_plan.md` bundled
> three concerns: production hardening, email infrastructure,
> and reminders workflow. The split landed in three sibling
> plans:
>
> - **14A** (this file) — production hardening proper.
> - **14B** — `guide/segment_14B_email_infrastructure.md` (absorbs
>   the former `segment_14-1_email_infra.md`).
> - **14C** — `guide/segment_14C_reminders_workflow.md` (auto /
>   scheduled reminder cadence on top of 14B's transport).
>
> Inherited-debt items from earlier segments (4A / 5A) that
> describe Postgres-specific optimisations + secret management
> + VNet integration + CI hardening live in **this file** since
> they're load-bearing for production credibility.

---

## 1. Segment goal

Segment 14A hardens the application after the core functional loop exists.

By this point, the app should already support session setup, imports, assignments, reviewer responses, invitations, monitoring, export, and retention. Segment 14A improves operational readiness.

This is not about adding new Review Robin features. It is about making the existing system more reliable and supportable.

---

## 2. Success criteria

Segment 14A is complete when:

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

Email infrastructure (transport activation, backend swaps,
correlation_id, bulk-send worker, generalised Outbox) lives in
**14B**, not here. Reminder cadence + auto-scheduled reminders
live in **14C**, not here.

---

## 3.1 Inherited from Segment 4A

Segment 4 (per `guide/archive/segment_04A.md`) deliberately used cross-dialect column
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
  deploy. *(Largely shipped — the `ci-postgres` workflow runs the full
  pytest suite against `postgres:16`; remaining hardening lives here.)*
- **Review and add Postgres-specific indexes.** GIN indexes on `JSONB`
  columns where queried; partial indexes for frequently-filtered subsets;
  expression indexes if any.
- **Consider DB-level enums.** Where Segment 4 used `String` + Python enum
  validation (e.g. `AuditEvent.event_type`, `AuditEvent.severity`), decide
  per column whether a Postgres `ENUM` type is worth the migration cost.

These items belong in this segment because they only matter once the app is
heading toward a real internal pilot.

---

## 3.2 Inherited from Segment 5A

Segment 5 (per `guide/archive/segment_05A.md`) provisioned dev Postgres with the
simplest acceptable infrastructure choices. The following hardening items
were deferred here:

- **Move `DATABASE_URL` (and any other secrets) to Key Vault references.**
  Segment 5A stored the connection string as a plain App Service App
  Setting and as a GitHub Actions secret. For staging/production, switch
  the App Setting to a Key Vault reference and assign the App Service a
  managed identity with `Get` permissions on the relevant secrets.
- **VNet integration / private endpoints for Azure Postgres.** Segment 5
  used public access with firewall rules. For staging/production, put the
  database behind a private endpoint, integrate the App Service into the
  VNet, and remove "Allow Azure services" plus the developer-IP firewall
  rules.
- **Migration-on-deploy safety controls.** Segment 5A's migrate-on-deploy
  step fails the workflow if migration fails, but does not gate
  destructive migrations. Add: a manual-approval gate for staging/production
  deploys, a "long migration" detector, and a documented rollback playbook.
- **CSS extraction and design pass.** Segment 5A used inline `<style>`
  blocks in `base.html`. Extract to static assets, decide on a design
  language, and migrate `me_debug.html` to extend `base.html`.
- **First-time-user creation auditing.** Segment 5A creates a `User` row
  on first sign-in without writing an audit event. Decide whether
  first-sign-in deserves its own audit event, or whether the
  Easy-Auth-side sign-in record is sufficient.

---

## 4. Branch strategy

This segment may be too broad for one PR. Prefer several smaller PRs.

Suggested branches:

```text
segment-14A-logging-monitoring
segment-14A-deployment-hardening
segment-14A-permission-review
segment-14A-runbooks-docs
segment-14A-accessibility-pass
```

Suggested umbrella PR title:

```text
Segment 14A: Production hardening pass
```

---

## 4.1 Implementation PR ladder (planned 2026-05-18)

### Scoping decisions

Three decisions narrowed the segment from the full §5 list:

1. **Type migrations deferred.** The §3.1 inherited Postgres
   type migrations — JSON→`JSONB`, `String(36)`→`UUID`,
   `String`→DB `ENUM` — are *all* deferred out of 14A to a
   future DB-performance pass. The §5.5 index review therefore
   adds plain B-tree indexes only — no `JSONB` GIN indexes.
2. **CSRF — document, don't tokenise.** No anti-CSRF token
   machinery. Azure Easy Auth + same-site session cookies is
   the standing mitigation; the dependence is written up in
   the security-posture note (PR 6) rather than coded around.
3. **Azure infra is out of the ladder.** Key Vault references,
   VNet / private endpoints, the staging slot, the Application
   Insights *resource*, and the migration-approval deploy gate
   need the Azure portal and are not agent-implementable. They
   are documented as deployment prerequisites in the runbook
   (PR 6), not built here. Structured logging itself (PR 1)
   *is* in scope and is App-Insights-ingestible once the
   resource exists.

So 14A as laddered here is the **pure in-app hardening**:
logging, error handling, indexes, permission / destructive-
action review, accessibility, and the config + runbook
documentation. §3.1, §3.2 and §5.1 (deployment-slot work) are
out; §5.9 folds into PR 6's docs.

### PRs

Independent — no ordering constraint — each PR-sized.

**PR 1 — Structured logging + observability (§5.3).** A
structured-logging setup (JSON-shaped records, level from
config) with explicit log lines at the §5.3 points — session
activation, import failures, permission denials,
retention / deletion actions, reviewer-save / export failures.
Keeps the three streams distinct: application logs vs
`audit_events` vs user-facing validation messages. No App
Insights resource wiring (infra); the records are structured
so ingestion is a later config-only step.

**PR 2 — Error handling (§5.4).** A global exception handler in
`app/main.py` that renders a friendly error page and never
leaks a traceback, plus specific handling for the §5.4 cases —
unauthorized, session-not-found, invalid / expired invitation
link, validation / save / export failure. Closes the
assessment's "sparse boundary error handling — raw 500s"
weakness. New `error.html` template (status-specific variants).

**PR 3 — Database indexes (§5.5).** Review the common query
paths (sessions-for-operator, reviewers / reviewees by session,
assignments by reviewer / session, responses by assignment,
monitoring counts, audit events by session / date); add the
missing B-tree indexes in one migration, each with a one-line
rationale. Cross-dialect — no Postgres-only index types (those
wait on the deferred type migrations).

**PR 4 — Permission + destructive-action review (§5.6 + §5.7).**
Audit every operator / reviewer / sys-admin / export /
retention route's permission dependency; add explicit
denial-path tests for the load-bearing ones. Confirm each
destructive action (delete responses, close / reopen session,
replace rosters / assignments, delete instrument, purge,
revoke link) carries confirm + permission + audit + a clear
warning; fix any gap found. Largely a verification +
test-writing PR — the assessment already read the auth gating
as clean.

**PR 5 — Accessibility pass (§5.8).** A basic pass — keyboard
navigation, visible focus state, form-field labels, contrast,
error-message-to-field association — focused on the reviewer
response table. Not a full WCAG audit.

**PR 6 — Config hardening + runbooks + docs (§5.2, §5.9,
§5.10).** Startup checks that fail fast on missing critical
settings in non-local environments; document every required
environment variable. Then the documentation set: operator
runbook, deployment guide (with the deferred Azure-infra
prerequisites spelled out), troubleshooting guide,
backup / restore note, known-limitations page, data-retention
note, and the **security / compliance posture note** — which
records the Easy-Auth trust model, the CSRF posture
(decision 2), the `ALLOW_FAKE_AUTH` gating, and the deferred
infra items.

### Success-criteria coverage

The ladder satisfies 14A success criteria **1–3, 5–12**.
**#4 (Application Insights configured)** is the one criterion
the in-app ladder cannot meet — it needs the Azure resource
and is documented as a deployment prerequisite in PR 6's
runbook.

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
- email mode (cross-reference 14B);
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
- invitation send failures (cross-reference 14B);
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
## Segment 14A completion note

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

After Segment 14A (in conjunction with 14B + 14C), the application is ready for a cautious internal pilot, subject to institutional policy and data-classification approval.
