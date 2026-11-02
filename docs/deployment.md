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
never runs against a stale schema. No cloud credential, deploy workflow
or institutional identifier lives here, and nothing here can reach the
deployment (`CONTRIBUTING.md`).

## What the host provides

- **Sign-in: App Service Easy Auth** (Entra ID), with the token store on.
  It injects the `X-MS-CLIENT-PRINCIPAL*` headers that `cordware/identity.py`
  parses, and holds the delegated Microsoft Graph token the directory
  features use (`cordware/spec/identity.md`). The application has no
  login code and no password store (`docs/security_posture.md`). Each
  mount's `/health` is excluded from sign-in.
- **The database:** PostgreSQL 16, reached through `RRW_DATABASE_URL`
  (`docs/database.md`). The release runs `alembic upgrade head` before
  the new code starts.
- **Settings:** read from App Settings at process start, so a change takes
  effect on restart. The ones RRW reads are below; values are the
  deployment's, never this repository's.
- **Logs:** RRW writes structured JSON to stdout, one object per line,
  each stamped with its application (`cordware/logging.py`); the host
  collects them.

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | Anything but `local` turns on the startup checks (`validate_critical_settings`) and forbids fake auth. |
| `RRW_DATABASE_URL` | unset | RRW's database. `DATABASE_URL` is the older name, read when this is unset (local runs and CI). |
| `CORDWARE_APPS` | every registered app | Which applications the host mounts, comma-separated; empty runs the host alone. |
| `CORDWARE_PUBLIC_ORIGIN` | unset | The address users reach the host at, when a gateway sends the App Service's own host name (`cordware/spec/host.md`). |
| `CORDWARE_INSTITUTION_NAME` | unset | The top bar's top line (`docs/header_chrome.md` §6); unset shows none. |
| `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` | empty | First-sign-in seeds for the operator and admin flags. Outside `local`, at least one must be set or RRW refuses to start (`docs/operations_runbook.md`). |
| `SUPER_ADMIN_EMAILS` | empty | The protected top tier, derived on every request, never stored. |
| `OPERATOR_CONTACT_EMAIL` | unset | The contact shown on `/about`. |
| `LOG_LEVEL` | `INFO` | The root log level (the host's logging). |
| `SMTP_ENCRYPTION_KEY` | unset | Decrypts SMTP passwords saved before segment 14C Item 1; keep it where one exists. |
| `SCHEDULED_OPERATIONAL_LEAD_HOURS` / `REVIEWER_NOTICE_MIN_HOURS` | `1` | Scheduling floors (`spec/settings_inventory.md` §2). |
| `REHYDRATE_ENABLED` | `false` | Opens the deferred Rehydrate surface. |
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
