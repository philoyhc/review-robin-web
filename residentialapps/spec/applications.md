# Residential applications

> **Draft for inspection, 2026-10-26.** Nothing here is built. It states
> what segment 1A (`residentialapps/guide/segment_1A_package_and_mounts.md`)
> will build, so the author can correct it before any code exists. When 1A
> lands, the draft banner goes and each section says what shipped.

The contract of the two Residential applications as the Cordware host
sees them: how each is built, where it mounts, what it answers before it
has any pages. The host's side is `cordware/spec/host.md`; this file
states only what Residential adds.

## Two applications, one package

| | RA Operations | Support Logs |
|---|---|---|
| Registry name | `residentialops` | `supportlogs` |
| Mount path | `/residentialops` | `/supportlogs` |
| Factory | `residentialapps.ops.main:create_app` | `residentialapps.supportlogs.main:create_app` |
| Logger prefix | `residentialapps.ops` | `residentialapps.supportlogs` |
| Landing-page title | `RA Operations` | `Support Logs` |
| Health | `GET /residentialops/health` | `GET /supportlogs/health` |

- Nothing mounts at `/residentialapps`; it names the package only
  (ruling 1).
- Each factory is a zero-argument callable returning a new `FastAPI`
  application, as the registry requires. It reads no setting and opens no
  database in 1A.
- The registry lists them after `reviewrobin`, in the order above, so an
  unset `CORDWARE_APPS` mounts all three in that order and the landing
  page lists them so.

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
| `residentialops` | RA Operations alone; `/` redirects to `/residentialops/` |
| `supportlogs` | Support Logs alone; `/` redirects to `/supportlogs/` |
| `residentialops,supportlogs` | Both; `/` lists both |
| unset | RRW and both; `/` lists all three |

A bare mount path (`/residentialops/`) answers `404` in 1A: neither
application has a page yet.

A host whose deployment does not carry `residentialapps/` must name its
applications in `CORDWARE_APPS`: unset, the host loads every factory and
fails to start on the missing package (`host.app_startup_failed`).

## Logging and lifespan

- Each application logs under named loggers below its prefix
  (`logging.getLogger("residentialapps.ops.…")`), never configures the
  root logger, and is stamped `residentialops` or `supportlogs` by the
  host's `ApplicationFilter`. The prefixes do not nest, so a record is
  never stamped with the wrong one (ruling 6).
- **Residential stamps its own shared code.** Code both applications use
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

The JSON health body emits no URL. From the first page (1B), each
application emits its paths under its mount the way RRW does
(`spec/architecture.md` "URL emission"), through its own helper, with a
leak test and a GET crawl (`residentialapps/guide/todo_master.md`, "What
Residential takes from the deployment strategy").
