# ApplyDesk as the host sees it

> **Built so far:** segment AD1 item 1 built "The registry entry",
> "Health" and "Running alone". "The URL map" is item 2's contract.

ApplyDesk's contract with the Cordware host. The host's side is
`cordware/spec/host.md`; this file states only what ApplyDesk adds. The
rulings behind it are `applydesk/guide/todo_master.md`.

## The registry entry

| | |
|---|---|
| Registry name | `applydesk` |
| Mount path | `/applydesk` |
| Factory | `applydesk.main:create_app` |
| Logger prefix | `applydesk` |
| Landing-page title | `ApplyDesk` |
| Icon | A white application sheet on a rose (`#be123c`) tile, running off the bottom-right, a tick cut in rose (author, 2026-11-02). The source is `applydesk/templates/applydesk/base.html`, copied to `cordware/web/app_icons.py` |

- The registry lists it after Residential's two applications and before
  Utilities, which stays last.
- The factory is a zero-argument callable returning a new `FastAPI`
  application with no schema pages (`/docs`, `/redoc`,
  `/openapi.json`). It reads no setting and opens no database.

## Health

`GET /applydesk/health` returns `{"status": "ok"}`, route name
`applydesk_health`, with no sign-in, setting or database. Excluding it
from Easy Auth is a deployment step.

## Running alone

`CORDWARE_APPS=applydesk` starts with ApplyDesk alone; an unset value
mounts it beside every other application. Its records are stamped
`application: applydesk` in the host's logs.

## The URL map

Item 2's contract (`applydesk/guide/segment_AD1_skeleton.md`, "The URL
map"): operators under `/operator/exercises`, participants under `/me`,
an exercise named by a 10-character public ID in RRW's alphabet, and a
profile page named by its own ID, never the application's.
