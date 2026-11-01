# Operations runbook

Day-to-day procedures for operating Review Robin Web. Re-scoped
2026-11-01 (segment 20A): the service runs on the institutional Azure
host, mounted under Cordware, and that host's procedures (deploying a
release, restarting, App Settings and secrets, logs, re-running a
failed release) are kept in the private repository that deploys it, not
here. The personal dev slot is dormant; its procedures are
`docs/deployment_dev.md`'s.

What stays here is what an administrator does **in the app**, and what
holds on any host. For symptom-driven diagnosis of the application see
`docs/troubleshooting.md`.

## Health check

```text
GET https://<host>/reviewrobin/health  →  {"status": "ok"}
```

Each mounted application's health path is excluded from Easy Auth, so
it answers without sign-in. A non-200 means the worker is not up, or
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
Settings seed the two columns **on a user's first sign-in only**; a
super-admin self-heals to full rights on every sign-in. Name people by
their **mail address**: the host reads the mail claim, which can differ
from the sign-in name. An admin listed after their first sign-in is not
promoted by the list; promote them on Accounts Management instead.

**In-app management shipped (Segment 18S).** The Sys Admin → Accounts
Management page (`/operator/sys-admin/users`) admits, revokes, promotes,
demotes, and removes accounts (`app/services/users.py`), so revoking
access is no longer a manual DB `UPDATE`. Guards: promote/demote require a
super-admin actor; demote/revoke/remove refuse a super-admin *target*
(`protected_super_admin`) and can't drop below the last-admin floor.
Remove also refuses anyone who created a session or acted in the audit
log (`has_history`): to take someone's access away, revoke it.

## Backups and data

Database backups, restore, and data-retention details are in
`docs/backup_restore.md`.
