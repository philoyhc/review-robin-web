# ApplyDesk as the host sees it

> **Built so far:** segment AD1 built "The registry entry", "Health",
> "Running alone" (item 1) and "The URL map" as placeholders on sample
> data (item 2), pending the author's approval in a browser.

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

The table is `applydesk/guide/segment_AD1_skeleton.md`, "The URL map":
operators under `/operator/exercises`, participants under `/me`.

- **Public IDs** (`applydesk/ids.py`): 10 symbols from RRW's alphabet,
  `23456789abcdefghjkmnpqrstuvwxyz`, drawn at random. A path whose ID has
  any other shape, or names nothing, is a 404 before anything is read.
- **The profile page** is named by its own ID, never the application's,
  and shows only the *Shown to reviewers* section. In a blind exercise it
  redacts the applicant's name and identifiers.
- **The chrome** is the shared bar (`docs/header_chrome.md`): the app
  icon, the workspace's top line over the area, a switcher of *Exercises*
  and *My ApplyDesk* then *All applications*, the Light/Dark toggle and the
  account menu. An exercise's operator pages add a row of tabs.
- **The gate** (`applydesk/gate.py`): every route but `/health` answers
  anyone on a local run and, deployed, only the platform super-admin,
  with a 404 for everyone else, until the segments that wire them.
