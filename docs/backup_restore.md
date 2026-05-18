# Backup, restore, and data retention

Scoped to the current single Azure **dev** slot. This is a pilot
/ dev deployment, so the notes below are deliberately simple; an
institutional deployment would need to align them with
institutional policy.

## Database backup

The application database is **Azure Database for PostgreSQL
Flexible Server**. Azure takes automated backups of the server —
the dev server uses the **default 7-day retention** with no
geo-redundancy and no high-availability replica (see
`docs/deployment_dev.md` → "Azure resources").

There is no application-level backup job; the platform's
automated backup is the only mechanism.

## What can be restored

Azure Flexible Server supports **point-in-time restore** to any
moment within the retention window. A restore creates a **new**
server — it does not overwrite the existing one. Recovering then
means either repointing `DATABASE_URL` at the restored server or
copying data across.

Restore granularity is the whole database. There is no
per-session or per-table restore; recovering one accidentally
deleted session means restoring the whole server to a point
before the deletion and extracting that session's rows.

## Who can restore

Anyone with Azure RBAC rights on the resource group
`rg-review-robin-web-dev` (the project owner, in practice). The
restore is done from the Azure Portal; the app has no in-app
restore affordance.

## Export files

CSV exports (`/operator/sessions/{id}/export/*.csv`,
`bundle.zip`) and the audit-log CSV are **generated on demand and
streamed** to the operator's browser. The app does not write them
to server-side storage and does not retain them — there is no
blob storage configured (storage is a deferred item, see
`docs/security_posture.md`). The only copy of an export is the
file the operator downloaded.

## Import files

Uploaded roster / assignment / config CSVs are **parsed in
memory and discarded** once the import completes. The app does
not keep the uploaded file; only the resulting rows
(reviewers / reviewees / assignments / …) are persisted.

## Data retention

What the application database holds and how it is removed:

- **Sessions, rosters, instruments, assignments, responses** —
  persist until an operator deletes them. "Delete Data" clears a
  session's responses; "Delete Session" removes the session and
  its dependent rows; the lobby bulk actions delete selected
  (archived) sessions. All are confirm-gated and audited.
- **`audit_events`** — append-only in normal operation. Rows are
  removed only by the selective purge (which can target the
  audit log) or by a whole-session delete.
- **`users`** — created on first sign-in; removed only by a
  manual DB operation (no in-app user delete yet).

There is no automatic time-based expiry of any data — nothing is
purged on a schedule. Retention is entirely operator-driven.

## Limitations

- 7-day backup window — data older than 7 days before a deletion
  cannot be recovered from platform backups.
- No geo-redundant backup; a region-level loss is unrecovered.
- No tested restore drill — restore is documented but has not
  been rehearsed on this deployment.
- Single environment — there is no separate production database
  with its own backup policy yet.
