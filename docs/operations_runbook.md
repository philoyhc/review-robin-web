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

## Secrets the app reads

`SMTP_ENCRYPTION_KEY` is needed by no page since segment 14C Item 1
removed the Settings page's SMTP cards. It still decrypts any SMTP
password saved before then, so keep it set where one exists: rotating
it leaves those passwords undecryptable. How the host stores and
rotates settings is the host's documentation.

## Backups and data

Database backups, restore, and data-retention details are in
`docs/backup_restore.md`.
