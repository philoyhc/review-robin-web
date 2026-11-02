# Operations runbook

Day-to-day procedures for operating Review Robin Web. Re-scoped
2026-11-01 (segment 20A): the service runs on the institutional Azure
host, mounted under Cordware, and that host's procedures (deploying a
release, restarting, App Settings and secrets, logs, re-running a
failed release) are kept in the private repository that deploys it, not
here; the dormant personal dev slot's notes are archived there too
(2026-11-02). What RRW needs from any host is `docs/deployment.md`.

What stays here is what an administrator does **in the app**, what
holds on any host, and the application's own failure modes.

## Health check

```text
GET https://<host>/reviewrobin/health  →  {"status": "ok"}
```

Each mounted application's health path is meant to be excluded from
Easy Auth (the host's setting), so it answers without sign-in. A non-200 means the worker is not up, or
the application is switched off on the host.

## Logs

Application logs are structured JSON (one object per line), each
stamped with the application that wrote it (`cordware/logging.py`).
Where the host collects them is the host's documentation.

## Managing the operator / sys-admin allowlist

Access is a **three-tier hierarchy** (Segment 18S): operator
(`users.is_operator`) ⊂ admin (`users.is_sys_admin`) ⊂ super-admin
(derived from the `SUPER_ADMIN_EMAILS` App Setting, never a DB column —
`app/auth/roles.py`). The `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` App
Settings seed the two columns **only when a person's account row is
created** at sign-in; a super-admin self-heals to full rights on every
sign-in. Name people by their **mail address**: the host reads the mail
claim, which can differ from the sign-in name. Someone listed after
their row exists (they signed in, or were invited, first) is not
promoted by the list; promote them on Accounts Management instead.

**In-app management (Segment 18S).** The Sys Admin → Accounts Management
page (`/operator/sys-admin/users`) invites, admits, revokes, promotes,
demotes and removes accounts (`app/services/users.py`). Its guards:

- nobody acts on their own row (`self_action`);
- promoting, demoting or inviting an admin needs a super-admin, once a
  super-admin is configured; until then any admin can;
- a super-admin target is refused (`protected_super_admin`);
- demote and remove keep at least one admin (`last_admin`);
- revoke, and a demote that would take operator access, refuse while
  the person still owns sessions (`still_owner`): clear them with
  *Remove from all sessions* first;
- remove refuses anyone who owns a session (`owns_sessions`), created
  one or acted in the audit log (`has_history`). To take someone's
  access away, revoke it.

**Fixing roles from the database.** The settings seed a row only when it
is created, so someone listed after signing in is not promoted by the
list. Use Accounts Management; failing that, `UPDATE users SET
is_sys_admin = true WHERE email = '<mail address>'` (or `is_operator`),
which leaves no audit row. Never `DELETE` a user row: the foreign keys
that reference `users.id` have no `ON DELETE`, so it fails for anyone who
owns or created a session or has an audit row.

## Secrets the app reads

`SMTP_ENCRYPTION_KEY` is needed by no page since segment 14C Item 1
removed the Settings page's SMTP cards. It still decrypts any SMTP
password saved before then, so keep it set where one exists: rotating
it leaves those passwords undecryptable. How the host stores and
rotates settings is the host's documentation.

## Data the app keeps, and for how long

Database backups and restores are the host's (kept privately with the
deployment): there is no application-level backup, and restoring is
whole-server. What the application itself writes and keeps:

### Export files

CSV exports (`/operator/sessions/{id}/export/*.csv`,
`bundle.zip`) and the audit-log CSV are **generated on demand and
streamed** to the operator's browser. The app does not write them
to server-side storage and does not retain them — there is no
blob storage configured (application blob storage is deferred, see
`guide/blob_storage_candidates.md` and `guide/segment_18Q_blob.md`). The only copy of an export is the
file the operator downloaded.

### Import files

Uploaded roster / assignment / config CSVs are **parsed in
memory and discarded** once the import completes. The app does
not keep the uploaded file; only the resulting rows
(reviewers / reviewees / assignments / …) are persisted.

The one exception is **Rehydrate** (off by default,
`REHYDRATE_ENABLED`): it stashes the uploaded file set in the
`rehydrate_stashes` table between its Validate and Rehydrate
requests. A stash expires after an hour and is deleted after a
successful rehydrate, when an expired token is next read, or with
its operator's `users` row; nothing sweeps abandoned stashes on a
schedule. A rehydrate that drops responses stashes one more file, the
dropped-responses CSV it hands the operator. It is written after the
successful-rehydrate delete, so it lapses only on expiry or with its
operator's `users` row.

The other exception is an **upload that asks a question**:
a replace sent without its tick, a relationships replace that would
clear group answers, or a Settings file that would delete instruments.
It holds the files of that submit in the `held_uploads` table so the
operator can answer without choosing them again. A held file belongs to
one operator and one session, is capped at 1 MiB, and lasts an hour. It
is deleted once the import goes through, when the file is then refused
as unreadable (or, on Quick Setup, for any reason that is not a
question), or when the operator dismisses the ask; with its
session or its operator's `users` row; and by the sweep each new hold
runs first.

### Data retention

What the application database holds and how it is removed:

- **Sessions, rosters, instruments, assignments, responses** —
  persist until an operator deletes them. "Delete Data" clears a
  session's responses; "Delete Session" removes the session and
  its dependent rows; the lobby's Delete removes selected `draft`,
  `validated` or `expired` sessions, and the archived page's Delete
  selected archived ones. All are confirm-gated and audited.
- **`audit_events`** — append-only in normal operation. Rows are
  removed only by the selective purge (which can target the
  audit log) or by a whole-session delete.
- **`users`** — created on first sign-in, participants included;
  removed in-app via the Sys Admin → Accounts Management page
  (`remove_user`, Segment 18S), which guards against removing a
  super-admin or the last admin, and refuses any user who created a
  session or acted in the audit log (`has_history`). Removal is for
  accounts with no activity; Revoke takes an operator's access away
  and keeps their attribution.

There is no automatic time-based expiry of any data — nothing is
purged on a schedule. Retention is entirely operator-driven.

## When something goes wrong

The host's failures (a release, the database's reachability, sign-in
configuration) are diagnosed in the host's documentation. These are
RRW's own.

### A page answers 500

The app renders a friendly error page and never leaks a
traceback (Segment 14A PR 2). The traceback **is** logged: look in the
application's logs for the
`"unhandled exception"` JSON record — it carries the path and
the full traceback. Reproduce locally with the same input if the
log isn't enough.

### A signed-in user is bounced to `/me` from an operator page

The user is authenticated but not on the operator/sys-admin
allowlist (`users.is_operator` / `is_sys_admin` both false), so an
operator URL bounces them to `/me` (18R Item 6; was `/request-access`,
retired). This is expected for non-operators — `/me` shows their reviews
(or an empty dashboard), and `/about` carries the "how to get access"
note. If the bounce is wrong for this user, the usual cause is the
**first-sign-in-only** bootstrap rule: editing `OPERATOR_EMAILS` does
not re-promote an account that already has a `users` row. Promote them on
Accounts Management, or set the flag directly ("Fixing roles from the
database" above).

### RRW won't start after a settings change

Settings are read at process start, so a new one only takes effect
after a restart. If it still won't start and the log shows a `ConfigurationError`, the PR 6a startup check
(`validate_critical_settings`) is refusing to boot — in a
non-local environment both `OPERATOR_EMAILS` and `SYS_ADMIN_EMAILS`
are empty. Set at least one and restart.
