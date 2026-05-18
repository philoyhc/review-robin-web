# Deferred infrastructure & platform hardening

Infrastructure- and database-platform hardening that has been
**deferred** — items that need the Azure portal, or destructive
Postgres-only migrations, and so sit outside the in-app feature
and hardening segments.

Carved out of **Segment 14A — Production hardening**
(`guide/archive/segment_14A_production_hardening.md`) on 2026-05-18.
14A's PR ladder is the *in-app* hardening — logging, error
handling, indexes, permissions, accessibility, runbooks; the
items below are out of that ladder. They are inherited debt
from Segments 4A and 5A.

There is **no single "deferred infra" segment** — each item
lands opportunistically as its own small change with its own
verification, when a real pilot deployment forces the question.
14A's runbook (PR 6) documents the Azure items as deployment
prerequisites.

---

## 1. Azure infrastructure (needs the Azure portal)

Not agent-implementable — these require Azure portal / IaC
actions. Inherited from Segment 5A
(`guide/archive/segment_05A.md`), which provisioned dev Postgres
with the simplest acceptable infrastructure choices.

- **Move `DATABASE_URL` (and any other secrets) to Key Vault
  references.** Segment 5A stored the connection string as a
  plain App Service App Setting and as a GitHub Actions secret.
  For staging/production, switch the App Setting to a Key Vault
  reference and assign the App Service a managed identity with
  `Get` permissions on the relevant secrets.
- **VNet integration / private endpoints for Azure Postgres.**
  Segment 5 used public access with firewall rules. For
  staging/production, put the database behind a private
  endpoint, integrate the App Service into the VNet, and remove
  "Allow Azure services" plus the developer-IP firewall rules.
- **Migration-on-deploy safety controls.** Segment 5A's
  migrate-on-deploy step fails the workflow if migration fails,
  but does not gate destructive migrations. Add: a
  manual-approval gate for staging/production deploys, a
  "long migration" detector, and a documented rollback
  playbook.
- **Staging slot / environment.** A staging App Service slot (or
  separate App Service) so the deploy flow is
  `main → dev/staging → verify → manual-approve → production`.
- **Application Insights resource.** Segment 14A PR 1 ships
  structured logging that is App-Insights-ingestible;
  provisioning the resource and wiring its connection string is
  the remaining portal step.

---

## 2. Postgres platform migrations (destructive, Postgres-only)

Inherited from Segment 4A (`guide/archive/segment_04A.md`),
which deliberately used cross-dialect column types so the same
migration runs on SQLite (tests) and PostgreSQL (deployed).
The items below break that contract — they are Postgres-only
and need their own careful pass.

- **Migrate JSON columns to `JSONB`.** `AuditEvent.detail` and
  the other JSON columns should move to `JSONB` for indexing
  and operator-friendly queries. Postgres-only migration; tests
  continue on SQLite using `JSON`.
- **Migrate string-UUID columns to native `UUID`.** Where
  Segment 4 used `String(36)` for UUID-shaped columns, swap to
  Postgres `UUID` for storage efficiency and constraint
  correctness; add explicit casting in application code if
  needed.
- **Consider DB-level enums.** Where Segment 4 used `String` +
  Python enum validation (e.g. `AuditEvent.event_type` /
  `severity`), decide per column whether a Postgres `ENUM` type
  is worth the migration cost.
- **Postgres-specific indexes.** GIN indexes on `JSONB` columns
  where queried; partial indexes for frequently-filtered
  subsets; expression indexes if any. These depend on the
  `JSONB` migration above. (14A's index review, by contrast,
  adds only cross-dialect B-tree indexes.)

The Postgres-against-Docker CI job — also a Segment 4A
deferral — has since **shipped**: the `ci-postgres` workflow
runs the full `pytest` suite against `postgres:16`, so dialect
drift is caught in CI.

---

## 3. Other inherited debt (deferred, not strictly infra)

- **CSS extraction + design pass.** `base.html` carries inline
  `<style>` blocks; extract to static assets, decide on a
  design language, and migrate `me_debug.html` to extend
  `base.html`. Per `CLAUDE.md`, CSS extraction is a
  Segment-14-era concern. Cosmetic — no functional dependency.
- **First-time-user creation auditing.** First sign-in creates
  a `User` row without writing an audit event. Decide whether
  first-sign-in deserves its own audit event, or whether the
  Easy-Auth-side sign-in record is sufficient.

---

## See also

- `guide/archive/segment_14A_production_hardening.md` — the in-app
  hardening 14A *does* cover, and its 6-PR ladder.
