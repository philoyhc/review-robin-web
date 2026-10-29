# Residential applications

> **Built so far:** segment 1A built "Two applications, one package",
> "Health", "Running alone" and the per-application half of "Logging and
> lifespan". Segment 1B item 1 is building the screens as placeholders
> with sample data: the chrome, Rosters and setup (`/rosters/`, both
> rosters and person detail), Sys admin (`/sys-admin/`) and a preview of
> the not-registered page (`/not-registered`), and "URLs". The rest of "Pages" and the shared-code log
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
| Factory | `residentialapps.residentialops.main:create_app` | `residentialapps.supportlogs.main:create_app` |
| Logger prefix | `residentialapps.residentialops` | `residentialapps.supportlogs` |
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

Ruled by the author, 2026-10-26. Rosters and setup, Sys admin and the
not-registered page stand as placeholders on sample data (1B item 1),
answering only on a local run (`APP_ENV=local`) until items 3–5 wire
them; the rest is the contract for 1B and later. Each page shows what the
viewer's role allows; the table says only who reaches it. *Sys admin* is the system
role and *admin* the appointment (`residentialapps/docs/residentialapps_roles.md`,
"Terms"). Paths are under each mount, hyphenated as RRW's are.

**Residential Operations** (`/residentialops`; named RA Operations until
2026-10-26). Its four areas and who reaches them:

| Area | Path | Reached by |
|---|---|---|
| RA Leave Management | `/ra-leave/` | RAs, RFs, RSLMs, the Master and the admin, by appointment; every linked Staff-roster member, read-only (who is away, who covers whom); sys admins |
| RA Events Proposals | `/ra-events/` | As RA Leave |
| Rosters and setup | `/rosters/` | Sys admins only: Staff and RA rosters with their appointments, and the assignments: the terms, levels and slots, and who is assigned to each slot for a term |
| Sys admin | `/sys-admin/` | Sys admins, for the audit log; the super-admin, for the audit log and to grant and revoke sys admin |

**Residential Operations page map** (author, 2026-10-26). Each page, what
staff and RAs do on it, and its device class (`docs/cordware_mobile_to_desktop.md` §3:
*mobile-critical*, *responsive*, *desktop-oriented*); `—` is a page that side
never reaches. Section numbers are the RA Leave spec's
(`residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`). RA
Events has no spec yet, so its rows are provisional.

| Page | Path | Staff | RA |
|---|---|---|---|
| Landing | `/` | Choose an application the viewer reaches: RA Leave now, on the viewer's own side (RA or staff), RA Events later; RA Leave admin, Rosters and Sys admin for sys admins (author, 2026-10-28) · mobile-critical | The same · mobile-critical |
| Not registered | any path | First sign-in not yet linked · mobile-critical | The same · mobile-critical |
| **RA Leave, RAs** | `/ra-leave/` | — | — |
| RA home | `/ra-leave/` | — | Balance, cover requests to answer, current applications, Apply (§8) · mobile-critical |
| Apply for leave | `/ra-leave/apply` | — | Leave type, dates, covering RA (§9); dates counting no day under the policy are not submitted (author, 2026-10-29) · mobile-critical |
| Request extra leave | `/ra-leave/appeal` | — | Reason, dates, cover (§7, §15); open to every RA, or by invitation only to an invited RA (not shown to the rest), never while off · mobile-critical |
| Application detail | `/ra-leave/applications/{id}` | — | Status timeline with each decision's date and remarks; name new cover while open, which a declined cover requires where the policy asks cover to confirm, and the page urges otherwise (§12, scenario L); withdraw · mobile-critical |
| My cover | `/ra-leave/cover` | — | Acknowledge or decline being named as cover; notification links land here (§12, §23) · mobile-critical |
| My history | `/ra-leave/history` | — | Own applications and leave, with decision dates and remarks (§19) · responsive |
| **RA Leave, staff** | `/ra-leave/staff/` | — | — |
| Staff home | `/ra-leave/staff/` | What awaits my decision; this week in my Precinct(s) (§24) · mobile-critical | — |
| Awaiting my decision | `/ra-leave/staff/decide` | First approval, final approval (whoever the policy names), appeals (the Master: while appeals are on, and any already made), oldest first (§16, §24) · **mobile-critical** | — |
| Decide | `/ra-leave/staff/decide/{id}` | Entitlement, cover status, Precinct context; Approve or Reject with remarks in a few taps; the timeline shows earlier decisions' dates and remarks, the first approver's to the final approver and staff remarks on an appeal to the Master; read-only once decided (§13–§15) · **mobile-critical** | — |
| Decided | `/ra-leave/staff/decided` | The approver's own past decisions (§24) · responsive | — |
| Precinct leave | `/ra-leave/staff/precinct` | Who is away, cover, clashes, pending, scoped by Assignments for the current term: an RF their Precinct(s), an RSLM their Wing, the Master and the admin the whole Unit, staff in no slot the whole Unit, read-only (§22) · desktop-oriented, with a this-week summary that is mobile-critical | — |
| Appeals (staff) | `/ra-leave/staff/appeals` | Only staff the policy lets open appeals (slot appointments for their slots' RAs, Unit appointments, or named staff): the admin Appeals page's invitations, appeals with the Master and the card to open one, for the RAs they may (author, 2026-10-29) · responsive | — |
| **RA Leave, sys admins** | `/ra-leave/admin/` | — | — |
| Leave dashboard | `/ra-leave/admin/` | The Unit: pending by stage, appeals awaiting the Master (while appeals are on), overdue, clashes, routing gaps, who is away this week and later this term, extra leave granted by term, entitlement anomalies, recent administrative corrections (§25) · desktop-oriented | — |
| Leave policy | `/ra-leave/admin/policy` | Leave types needing an application (at least two, typically personal and official), each earned per term or per month served and capped per year or term, a term's days available only within it; blackout periods by week of a term, refused or appeal only; appeals beyond entitlement, open, by invitation or off, who may open one by invitation (as approvers are chosen), and their terms; how leave days count (every day, weekdays, or working days less public holidays); cover required or not, named or confirmed, and from whom; first approval by one or more of the appointments on the RAs' slots (several: whichever approves first) or none needed; final approval by one or more Unit-level appointments or by named staff (§6, §7, §9.1, §12, §21.1; author, 2026-10-28 and 2026-10-29) · desktop-oriented | — |
| Entitlements | `/ra-leave/admin/entitlements` | Each RA's entitlement for a term, worked out from the policy's rules, used and pending; adjustments with a reason, one at a time or by CSV (§21.1, §21.3) · desktop-oriented | — |
| Approval chain | `/ra-leave/admin/routing` | Approvers per Precinct, derived from Assignments and the policy (first approver from the RA's slot, final the policy's final approver, appeals the Master while they are on), delegates by person, each standing in for one of the slots' approvers on all their slots with optional From–To dates, first approval only; gaps flagged (§21.2; author, 2026-10-28) · desktop-oriented | — |
| Applications | `/ra-leave/admin/applications`, `…/{id}` | Search, correct, cancel (approved leave cancelled keeps its record, as Cancelled, and releases its days and its cover, as withdrawn leave does, §20, §30), reassign, record external leave (§21.4); export what the filter shows as CSV (§4.6) · desktop-oriented | — |
| Appeals | `/ra-leave/admin/appeals` | By invitation: whoever the policy lets open appeals (by default the Master or the Master's admin delegate), having agreed in principle, opens an appeal for one RA; the invitations and their status; appeals with the Master (§7; author, 2026-10-29) · desktop-oriented | — |
| Propose an event | `/ra-events/propose` | — | Provisional · mobile-critical |
| My proposals | `/ra-events/mine` | — | Provisional · responsive |
| Review proposals | `/ra-events/review` | Provisional · responsive | — |
| Events calendar | `/ra-events/` | Provisional · responsive | Provisional · responsive |
| Events admin | `/ra-events/admin/` | Provisional: event policy · desktop-oriented | — |
| Home, Assignments, Terms, Staff roster, RA roster | `/rosters/`, `/rosters/assignments`, `/rosters/assignments/terms`, `/rosters/staff`, `/rosters/ras` | Sys admins · desktop-oriented | — |
| Sys admin | `/sys-admin/` | Audit log; sys admin grants (super-admin) · desktop-oriented | — |

- **RA Leave by audience** (author, 2026-10-28): RAs' pages under
  `/ra-leave/`, staff's under `/ra-leave/staff/`, sys admins' under
  `/ra-leave/admin/`, each with its own home and tabs; RA Events follows the
  same shape when built. The RA roster is the Rosters area's, not Leave
  admin's.
- **Configurable, not fixed** (author, 2026-10-28), on Leave policy: each
  leave type's entitlement rule and cap, blackouts, cover, and who approves
  first and finally.
- **Approver pages are mobile-critical** (author, 2026-10-26): Awaiting my
  decision and Decide must work one-handed on a phone. This raises the RA
  Leave spec's §2.5, which classed approver actions as responsive.
- **How the pages look** — device widths, the chrome, color, buttons,
  row builders, roster tables, placeholders — is `residentialapps/spec/residentialops_ui.md`.
- **Policy lives with its application** (author, 2026-10-27): leave policy
  on Leave admin, event policy on Events admin. Rosters and setup stays the
  organization's slots and the two rosters, the data every application shares.

**Support Logs** (`/supportlogs`). Access is by authorization, never by
appointment, and RAs never reach it:

| Page | Path | Reached by |
|---|---|---|
| Encounter log | `/encounters/` | Frontline authorization (RFs and RSLMs, by default) |
| Plans | `/plans/` | Frontline; senior identifiable (the Master and the admin, by default); Other Staff with identifiable view, read-only |
| Dashboard | `/dashboard/` | Frontline (personal); senior identifiable (oversight); Other Staff with view, aggregate or identifiable as granted |
| Sys admin | `/sys-admin/` | Support Logs sys admins: authorizations, configuration, categories, the cluster list and the administrative audit log, with no support content or support-activity audit; the super-admin, for the same and to grant Support Logs sys admin |

Each application also has:

- **a home** at its bare mount. Residential Operations' is the landing
  (page map above), choosing an application the viewer reaches; Support
  Logs' lists the pages the viewer reaches, or redirects when there is
  exactly one;
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

A bare mount path answered `404` in 1A. Residential Operations' landing
(`/residentialops/`) now answers on a local run while a placeholder, and
`404` deployed; Support Logs' bare mount still answers `404`.

A host whose deployment does not carry `residentialapps/` must name its
applications in `CORDWARE_APPS`: unset, the host loads every factory and
fails to start on the missing package (`host.app_startup_failed`).

## Logging and lifespan

- Each application logs under named loggers below its prefix
  (`logging.getLogger("residentialapps.residentialops.…")`), never configures the
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
