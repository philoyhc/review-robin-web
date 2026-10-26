# Residential applications

> **Built so far:** segment 1A built "Two applications, one package",
> "Health", "Running alone" and the per-application half of "Logging and
> lifespan". Segment 1B item 1 is building the screens as placeholders
> with sample data: so far the chrome, the Organization page and both
> rosters (`/rosters/`, `/rosters/staff`, `/rosters/ras`), and "URLs". The rest of "Pages" and the shared-code log
> stamps (Residential's own `get_logger`) are the contract for 1B and
> later.

The contract of the two Residential applications as the Cordware host
sees them: how each is built, where it mounts, what it answers before it
has any pages. The host's side is `cordware/spec/host.md`; this file
states only what Residential adds.

## Two applications, one package

| | Residential Operations | Support Logs |
|---|---|---|
| Registry name | `residentialops` | `supportlogs` |
| Mount path | `/residentialops` | `/supportlogs` |
| Factory | `residentialapps.ops.main:create_app` | `residentialapps.supportlogs.main:create_app` |
| Logger prefix | `residentialapps.ops` | `residentialapps.supportlogs` |
| Landing-page title | `Residential Operations` | `Support Logs` |
| Health | `GET /residentialops/health` | `GET /supportlogs/health` |

- Nothing mounts at `/residentialapps`; it names the package only
  (ruling 1).
- Each factory is a zero-argument callable returning a new `FastAPI`
  application, as the registry requires. It reads no setting and opens no
  database in 1A.
- The registry lists them after `reviewrobin`, in the order above, so an
  unset `CORDWARE_APPS` mounts all three in that order and the landing
  page lists them so.

## Pages

Not built; the contract for 1B and later. Ruled by the author, 2026-10-26. Each page shows what the viewer's role
allows; the table says only who reaches it. *Sys admin* is the system
role and *admin* the appointment (`residentialapps/docs/residentialapps_roles.md`,
"Terms"). Paths are under each mount, hyphenated as RRW's are.

**Residential Operations** (`/residentialops`; named RA Operations until
2026-10-26). Its four areas and who reaches them:

| Area | Path | Reached by |
|---|---|---|
| RA Leave Management | `/ra-leave/` | RAs, RFs, RSLMs, the Master and the admin, by appointment; Team Viewers, read-only; sys admins |
| RA Events Proposals | `/ra-events/` | As RA Leave |
| Rosters and setup | `/rosters/` | Sys admins only: Staff and RA rosters, appointments, the organization tree and its levels |
| Sys admin | `/sys-admin/` | Sys admins, for the audit log; the super-admin, for the audit log and to grant and revoke sys admin |

**Residential Operations page map** (author, 2026-10-26). Each page, what
staff and RAs do on it, and its device class (`docs/cordware_mobile_to_desktop.md` §3:
*mobile-critical*, *responsive*, *desktop-oriented*); `—` is a page that side
never reaches. Section numbers are the RA Leave spec's
(`residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`). RA
Events has no spec yet, so its rows are provisional.

| Page | Path | Staff | RA |
|---|---|---|---|
| Home | `/` | Approvers land on what awaits them · mobile-critical | Balance, current applications, Apply (§8) · mobile-critical |
| Not registered | any path | First sign-in not yet linked · mobile-critical | The same · mobile-critical |
| Apply for leave | `/ra-leave/apply` | — | Leave type, dates, covering RA (§9) · mobile-critical |
| Request extra leave | `/ra-leave/appeal` | — | Reason, dates, cover (§7, §15) · mobile-critical |
| Application detail | `/ra-leave/applications/{id}` | Read from the queue or team view · responsive | Status timeline, withdraw · mobile-critical |
| My cover | `/ra-leave/cover` | — | Confirm or decline being named as cover; notification links land here (§12, §23) · mobile-critical |
| My history | `/ra-leave/history` | — | Own applications and leave (§19) · responsive |
| Awaiting my decision | `/ra-leave/decide` | First approval (RF, RSLM), final approval (the admin), appeals (the Master), oldest first (§16, §24) · **mobile-critical** | — |
| Decide | `/ra-leave/decide/{id}` | Entitlement, cover status, team context; Approve or Reject with remarks in a few taps (§13–§15) · **mobile-critical** | — |
| Decided | `/ra-leave/decided` | The approver's own past decisions (§24) · responsive | — |
| Team leave | `/ra-leave/team` | Who is away, cover, clashes; calendar and list (§22) · desktop-oriented, with a this-week summary that is mobile-critical | — |
| Leave admin: cycles and entitlements | `/ra-leave/admin/cycles` | Cycle setup, entitlement import and preview, adjustments (§21.1, §21.3) · desktop-oriented | — |
| Leave admin: applications | `/ra-leave/admin/applications` | Search, correct, cancel, reassign, record external leave (§21.4) · desktop-oriented | — |
| Propose an event | `/ra-events/propose` | — | Provisional · mobile-critical |
| My proposals | `/ra-events/mine` | — | Provisional · responsive |
| Review proposals | `/ra-events/review` | Provisional · responsive | — |
| Events calendar | `/ra-events/` | Provisional · responsive | Provisional · responsive |
| Organization, Staff roster, RA roster | `/rosters/`, `/rosters/staff`, `/rosters/ras` | Sys admins · desktop-oriented | — |
| Sys admin | `/sys-admin/` | Audit log; sys admin grants (super-admin) · desktop-oriented | — |

- **Approver pages are mobile-critical** (author, 2026-10-26): Awaiting my
  decision and Decide must work one-handed on a phone. This raises the RA
  Leave spec's §2.5, which classed approver actions as responsive.
- **One chrome, phone first** (author, 2026-10-26, from the RA Leave
  mockups). Residential Operations is served to a browser, never as an
  installed app, so its chrome is one slim top bar at every width and no
  bottom bar, which would compete with a phone browser's own toolbar.
  This is Residential Operations' chrome; Support Logs' is settled at its
  UI spec's next version. The bar scrolls away with the page:
  - **On the left, the switcher**: the Unit's name (Example College in the
    mockups) above the current area's name. Its menu lists the areas the
    viewer reaches (Home, RA Leave, RA Events; Rosters and setup and Sys
    admin for sys admins), then the other applications Cordware mounts
    (Support Logs, Review Robin). Those are links only: Residential
    Operations cannot read the others' permissions, so each answers for
    itself when opened.
  - **On the right, the Light/Dark toggle and the account**: the toggle at
    every width, as in RRW; initials, with the viewer's name and role beside
    them at desktop width. Dark takes RRW's dark neutrals and the accent's
    dark-surface tone.
  - **Under the bar, the area's page tabs**, with short labels, scrolling
    sideways on a phone. RA Leave's are an RA's Home, Apply, Extra leave,
    My cover, History, and an approver's Awaiting my decision, Team leave,
    Decided; staff with Leave admin add its pages. A detail page adds a
    back link instead of a breadcrumb.
  - **The body is cards in up to three columns** where three fit (about
    960 px in the mockups), stacked in column order below that. Routes and
    permissions are the same at every width
    (`docs/cordware_mobile_to_desktop.md` §7.5, §9).
- **Desktop-oriented pages stay usable on a phone**: no layout breaks, wide
  tables scroll in their box; they are not designed for one.

**Support Logs** (`/supportlogs`). Access is by authorization, never by
appointment, and RAs never reach it:

| Page | Path | Reached by |
|---|---|---|
| Encounter log | `/encounters/` | Frontline authorization (RFs and RSLMs, by default) |
| Plans | `/plans/` | Frontline; senior identifiable (the Master and the admin, by default); Other Staff with identifiable view, read-only |
| Dashboard | `/dashboard/` | Frontline (personal); senior identifiable (oversight); Other Staff with view, aggregate or identifiable as granted |
| Sys admin | `/sys-admin/` | Support Logs sys admins: authorizations, configuration, categories, the cluster list and the administrative audit log, with no support content or support-activity audit; the super-admin, for the same and to grant Support Logs sys admin |

Each application also has:

- **a home** at its bare mount. Residential Operations' is the viewer's own
  dashboard (page map above); Support Logs' lists the pages the viewer
  reaches, or redirects when there is exactly one;
- **the not-registered page** (`residentialapps/docs/residentialapps_identity.md`),
  for a signed-in person Residential cannot link.

A linked viewer who reaches none of an application's pages gets a `403`
page saying so, never an empty home.

**Plans** (author, 2026-10-26) are check-in plans for a student under
support: assigned, often offline by counselling and recorded as a formal
assignment (spec §7, source *Counselling*), or set up by the staff member
themselves (§10.1). A plan may be for a student who already has
encounter-log entries.

## Health

- `GET /health` inside each mount returns `200` with `{"status": "ok"}`,
  as RRW's does. Its route name is `residentialops_health` or
  `supportlogs_health` (below).
- **Every route name carries its application's prefix**, `residentialops_`
  or `supportlogs_`. Inside a mount, `url_for` resolves a name through the
  host's router first, and the host's mounts carry no name, so the first
  mount with a matching route wins: an unprefixed `health` in either
  application would resolve to `/reviewrobin/health`. The mounted tests
  resolve each application's health name from inside its own mount and
  check it lands there.
- Health needs no identity and no database. A deployment excludes both paths
  from sign-in, as it does RRW's.
- Neither application serves `/docs`, `/redoc` or `/openapi.json`
  (`docs_url`, `redoc_url` and `openapi_url` are `None`). Neither is an
  API, and a schema page would list routes to anyone signed out.

## Running alone

Every combination starts and answers both health paths it mounts (ruling 5):

| `CORDWARE_APPS` | Mounts |
|---|---|
| `residentialops` | Residential Operations alone; `/` redirects to `/residentialops/` |
| `supportlogs` | Support Logs alone; `/` redirects to `/supportlogs/` |
| `residentialops,supportlogs` | Both; `/` lists both |
| unset | RRW and both; `/` lists all three |

A bare mount path (`/residentialops/`) answers `404` in 1A: the homes
and pages above arrive in 1B and later segments.

A host whose deployment does not carry `residentialapps/` must name its
applications in `CORDWARE_APPS`: unset, the host loads every factory and
fails to start on the missing package (`host.app_startup_failed`).

## Logging and lifespan

- Each application logs under named loggers below its prefix
  (`logging.getLogger("residentialapps.ops.…")`), never configures the
  root logger, and is stamped `residentialops` or `supportlogs` by the
  host's `ApplicationFilter`. The prefixes do not nest, so a record is
  never stamped with the wrong one (ruling 6).
- **Residential stamps its own shared code** (not built; 1B and later). Code both applications use
  (`residentialapps.core` and `residentialapps.web`, from 1B) logs under
  `residentialapps.core…` or `residentialapps.web…`, which no registry
  prefix covers, so the host alone would stamp it `cordware`. Instead it
  logs through Residential's own `get_logger`, which stamps `application`
  on each record with the application serving the request
  (`residentialops` or `supportlogs`, set per request by each
  application), or `residentialapps` outside a request. The host's filter
  keeps a stamp a record already carries (`cordware/spec/host.md`
  "Logging"), so this needs no change to the host.
- Neither application has a lifespan in 1A. When one does, every state key
  it yields starts `residentialops_` or `supportlogs_`, so the host's
  duplicate-key check can never trip between them (ruling 6).

## URLs

Each application emits its paths under its mount the way RRW does
(`spec/architecture.md` "URL emission"), through Residential's own helper,
`residentialapps/web/urls.py`, since Residential may not import RRW's:

- a template writes `url('/…')` for a path inside the application and
  `host_url('/')` for the host's landing page;
- comparisons read `is_here()`.

`residentialapps/tests/test_pages.py` holds both checks: the leak rule
fails on a template link written out without a helper, and the GET crawl
fails on a page that emits a path outside its mount (other than `/`, a
fragment or Easy Auth's `/.auth/`). The JSON health body emits no URL.
