# Deployment: the general picture

What Review Robin Web (RRW) needs from the host that serves it, and
where the rest is kept. Written 2026-11-02 (`guide/post_azure_todo_checklist.md`,
item 2, author: "keeping one document describing a general picture"), when
the Azure-specific documents left this repository: the institutional
host's resources, procedures, backups and diagnosis are kept in the
private repository that deploys it, and the dormant personal dev slot's
notes are archived there.

## The shape

RRW is one server-rendered FastAPI application, mounted at
`/reviewrobin` by the **Cordware host** (`cordware/main.py`), which also
mounts Residential Operations, Support Logs and Cordware Utilities. The
host runs as one Azure App Service (Linux, Python 3.12) behind
institutional Microsoft Entra ID sign-in, with one managed PostgreSQL
server holding each application's database.

**This repository never deploys.** A private repository imports an
allowlisted snapshot of one `main` commit whose CI is green, and
releases it: build, then **migrate, then deploy**, so the application
never runs against a stale schema. A release is dispatched by hand,
behind its own approval, and runs on whichever commit it imports; there
is no staging slot. No cloud credential, deploy workflow
or institutional identifier lives here, and nothing here can reach the
deployment (`CONTRIBUTING.md`).

## What the host provides

- **Sign-in: App Service Easy Auth** (Entra ID), with the token store on.
  It injects the `X-MS-CLIENT-PRINCIPAL*` headers that `cordware/identity.py`
  parses, and holds the delegated Microsoft Graph token the directory
  features use (`cordware/spec/identity.md`). The application has no
  login code and no password store (`docs/security_posture.md`). Each
  mount's `/health` is meant to be excluded from sign-in, the host's
  setting. A deep link through sign-in is Easy Auth's redirect, so it is
  checked on a deployment, not in this repository's tests.
- **The database:** PostgreSQL 16, reached through `RRW_DATABASE_URL`
  (`docs/database.md`). The release runs `alembic upgrade head` before
  the new code starts.
- **Settings:** read from App Settings at process start, so a change takes
  effect on restart. The ones RRW reads are below; values are the
  deployment's, never this repository's.
- **Logs:** RRW writes structured JSON to stdout, one object per line,
  each stamped with its application (`cordware/logging.py`); the host
  collects them.

**Nothing lives outside the database.** RRW keeps no session or cache
state in memory or on disk between requests (no Redis, no cache tier, no
blob store yet), so an instance can restart or a second be added without
losing anything. The clock is a loop that holds no state either: a
restart or a second instance costs at most one pass, and a step missed
while the app was down fires on the next pass or request (a release-window stamp only within a day of its moment).

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | A deployment sets anything but `local`: that turns on the startup checks (`validate_critical_settings`), forbids fake auth, and logs `super_admin.unconfigured` when no super-admin is listed. |
| `RRW_DATABASE_URL` | local SQLite file | RRW's database. `DATABASE_URL` is the older name; the environment is read before `.env`, so an exported `DATABASE_URL` beats an `RRW_DATABASE_URL` in `.env` (`spec/settings_inventory.md`). |
| `CORDWARE_APPS` | every registered app | Which applications the host mounts, comma-separated; empty runs the host alone. |
| `CORDWARE_PUBLIC_ORIGIN` | unset | The address users reach the host at, when a gateway sends the App Service's own host name (`cordware/spec/host.md`). |
| `CORDWARE_INSTITUTION_NAME` | unset | The top bar's top line (`docs/header_chrome.md` §6); unset shows none. |
| `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` | empty | First-sign-in seeds for the operator and admin flags. Outside `local`, at least one must be set or RRW refuses to start (`docs/operations_runbook.md`). |
| `SUPER_ADMIN_EMAILS` | empty | The protected top tier, derived on every request, never stored. |
| `PARTICIPANT_TOKEN_SALT` | built-in default | The per-deployment salt in every participant token; a deployment should set its own (`spec/settings_inventory.md`). |
| `OPERATOR_CONTACT_EMAIL` | unset | The contact shown on `/about`. |
| `LOG_LEVEL` | `INFO` | The root log level (the host's logging). |
| `SMTP_ENCRYPTION_KEY` | unset | Decrypts SMTP passwords saved before segment 14C Item 1; keep it where one exists. |
| `SCHEDULED_OPERATIONAL_LEAD_HOURS` / `REVIEWER_NOTICE_MIN_HOURS` | `1` | Scheduling floors (`spec/settings_inventory.md` §2). |
| `REHYDRATE_ENABLED` | `false` | Opens the deferred Rehydrate surface. |
| `SCHEDULER_INTERVAL_SECONDS` | `120` | Seconds between passes of RRW's in-app clock, which starts with the app and fires scheduled activation, the close at a review's end and the release-window stamps with no page view. `0` turns it off; the page-view trigger then does the same work on the next request. Each pass takes a Postgres advisory lock, so several instances run one pass at a time (`spec/lifecycle.md` §8.3). |
| `RRW_BULK_SEND` | `false` | Whether the Workflow card's Send invites and Send reminders may email every reviewer at once. Off until sending is paced (segment 14G): the two buttons are disabled and point operators to the session link, and per-row Send and Send reminder still email one reviewer. Leave it off. |
| `RRW_SCHEDULED_SEND` | `false` | Whether scheduled invitations and reminders may fire. Off until mail can go on the clock: the two auto-send fields are disabled and fire nothing. Leave it off (`spec/lifecycle.md` §8.1). |
| `ALLOW_FAKE_AUTH` | `false` | Local only; the host refuses to start with it on outside `APP_ENV=local`. |
| `APP_VERSION` | `dev` | Labels the build beside About, for operators. |

`AUDIT_STRICT_MODE` and the `FAKE_AUTH_*` settings are for tests and
local runs (`docs/local_setup.md`).

## Where things are

- **Running RRW locally:** `docs/local_setup.md`.
- **Administering it in the app** (accounts, data, exports, application
  failure modes): `docs/operations_runbook.md`.
- **The database and its migrations:** `docs/database.md`.
- **Security posture and the identity trust model:** `docs/security_posture.md`.
- **The host's own contract:** `cordware/spec/host.md`, `cordware/spec/identity.md`.
- **The institutional host's resources, releases, backups and
  troubleshooting:** kept privately with the deployment.
