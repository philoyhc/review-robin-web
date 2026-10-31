# Cordware host

The contract of the Cordware host: the process that serves Review Robin Web
(RRW) and, later, other applications. Design and rationale are in
`docs/archive/cordware_repository_strategy_v0.8.md` §3; this file states what the
host does.

RRW is mounted at `/reviewrobin`, and the host's landing page owns `/`. The
host serves only through `cordware.main:app`; RRW has no standalone entry
point.

## Entry point

- The start command names `cordware.main:app`.
- `create_app(apps=None, *, registry=REGISTRY)` builds the host. `apps` is a
  sequence of registry names; `None` reads `CORDWARE_APPS`. An explicit `apps`
  (including `()`) overrides the setting. `registry` exists for tests.
- `app = create_app()` runs once, at import of `cordware.main`: the entry point
  is the one construction. Importing `app.main` builds nothing
  (`tests/unit/test_app_main_builds_nothing.py`).
- `create_app` reads `CordwareSettings`, configures logging, runs the
  fake-auth guard and the super-admin warning (below), builds every selected
  application, registers `/health` and the landing page, then mounts them.

## Registry

`REGISTRY` maps an application name to `AppEntry(path, factory, logger, title)`:

| Field | Meaning |
|---|---|
| `path` | Mount path. |
| `factory` | `"module:attribute"` string naming a zero-argument callable that returns a complete ASGI application. |
| `logger` | Logger-name prefix the application logs under (see Logging). |
| `title` | How the landing page names the application. Defaults to empty, and the page then shows the registry name. |

- Four entries, in this order:

  | Name | `path` | `factory` | `logger` | `title` |
  |---|---|---|---|---|
  | `reviewrobin` | `/reviewrobin` | `app.main:create_app` | `app` | `Review Robin` |
  | `residentialops` | `/residentialops` | `residentialapps.residentialops.main:create_app` | `residentialapps.residentialops` | `Residential Operations` |
  | `supportlogs` | `/supportlogs` | `residentialapps.supportlogs.main:create_app` | `residentialapps.supportlogs` | `Support Logs` |
  | `utilities` | `/utilities` | `utilityapps.main:create_app` | `utilityapps` | `Utilities` |

  The two Residential applications' own contract is
  `residentialapps/spec/applications.md`; Utilities' is
  `utilityapps/spec/utilities.md`.
- An unset `CORDWARE_APPS` mounts all four, so a deployment that does not
  carry `residentialapps/` or `utilityapps/` names its applications: the host fails to start
  on a factory it cannot import. Cordware's production carries no
  `residentialapps/` for now (2026-10-30), so it always sets the variable.
- The mount path is a constant here, not a setting, so no configuration can
  move an application off its path.
- The host imports an application only by loading its `factory` string at
  construction. `cordware/main.py` names no application package.

## The host's part in `root_path`

The host rewrites no application's URLs. It emits URLs only on its own
landing page (§ Landing page), where its links carry the
request's `root_path` before the application's path. For an application,
the host's part is the mount: Starlette's `Mount` sets `root_path` in the
ASGI scope to the mount path before the application runs, and an
application serves what is under it. Inside the mount:

- `root_path` is the mount path (empty at `/`), and `request.url.path`
  includes it;
- `request.app.url_path_for(...)` omits it;
- `request.url_for(...)` is absolute, host and prefix included.

Adding the prefix to the URLs an application emits is the application's
job (RRW's, in `spec/architecture.md` "URL emission"). Easy Auth's
`/.auth/*` stays at the host level, outside every mount.

## Landing page

`cordware/web/landing.py` and its template, `cordware/web/templates/landing.html`,
serve `GET /`. The host registers it before any mount, so it answers ahead of
an application; if an application is mounted at `/`, the host registers
nothing there and the application owns `/`.

`/` answers with a page listing each mounted application, in mount order,
as a link to its path with its trailing slash and the request's
`root_path` (`/reviewrobin/` for RRW), titled by its registry title
(registry name if empty), and a host-level `Sign out` link to
`/.auth/logout`. With none mounted it says no applications are running.
**One application is listed like any other** (author, 2026-10-31): the
302 redirect a lone application took (ruled 2026-10-21) is withdrawn, as
it hid the sign-in details on a deployment mounting only one.

The page requires no sign-in and has no roles: it lists what is mounted,
not what a viewer may use, and each application gates its own routes.

For diagnosis (author, 2026-10-26; rows extended 2026-10-31) the page
also shows **Sign-in details**, from `current_identity`
(`cordware/spec/identity.md`), to everyone signed in: name; **Matched
as** (`email`, the address the applications match on); **UPN** and
**Mail** (`upn`, `mail`, as Entra gives them, `FAKE_AUTH_UPN` /
`FAKE_AUTH_MAIL` under fake auth); object ID (`principal_id`: the Entra
object ID under Easy Auth, `FAKE_AUTH_PRINCIPAL_ID` under fake auth);
provider; whether the identity came from Easy Auth headers or fake auth;
and whether it is the super-admin. An absent field reads "—", never an
error. **Only a super-admin** also sees the principal header's claims,
as `extract_claims` reads them, collapsed under "Sign-in claims": the
full list is a diagnostic and carries session internals (author,
2026-10-31). The fake identity has none. Signed out, it says so, without
counting a refusal. The details are the viewer's own, so the response is
`Cache-Control: no-store`.

The landing template carries its own inline style and extends nothing of
RRW's. Its favicon, inline SVG as Residential's are, is a white two-ply cord
twisted into a ring on a black rounded square (author, 2026-10-29).

## `CORDWARE_APPS`

Selects which registered applications mount. Read once, when the host is
built, by `CordwareSettings` from the `.env` in the working directory (the
repository root); a shell value overrides the file.

| Value | Mounts |
|---|---|
| unset | Every registered application, in registry order. |
| `""` (or blank) | None: the host alone. |
| `a,b` | Those applications, in the order written. |

Names are comma-separated, trimmed and matched exactly (case kept); empty
items are ignored. An unknown name, or a name written twice, raises
`ValueError` naming the value, and the host does not start.

## `CORDWARE_PUBLIC_ORIGIN`

The address users reach the host at, when it differs from what reaches the
app server: behind a gateway that sends the backend's own host name, or
TLS ended in front of it. Read once with `CORDWARE_APPS`.

- **Unset or blank:** nothing changes. Every URL built from a request names
  the request's own scheme and host.
- **Set:** the value is `https://host[:port]`. The host is an ASCII DNS
  name (an internationalized one in its `xn--` form) or an IP address, the
  port 1–65535; a default port is dropped. A trailing `/` is allowed; a
  path, query, fragment or user info is not. `http://` is allowed only at
  `APP_ENV=local`. Anything else raises `ValueError` naming the setting,
  and the host does not start (`parse_public_origin`).
- **What it rewrites.** `PublicOriginMiddleware` wraps the whole host,
  outermost, and runs only when the setting is set. On every HTTP request it
  sets the scope's `scheme`, its `server` (host and port, the port defaulted
  from the scheme) and the `Host` header to the origin. The landing page,
  `/health` and every mount see the origin, so `request.url`, `url_for` and
  the framework's trailing-slash redirects name it.
- **What it leaves alone.** The path, `root_path` and every other header
  pass through as sent. No forwarded header (`X-Original-Host`,
  `X-Forwarded-Host`, `X-Forwarded-Proto`) is read, so no request can move
  the origin. Lifespan events pass through.

A link built with no request has no origin to read; segment 14B's worker
owns that when it lands.

## `/health`

- The host's own route: `GET /health` returns `{"status": "ok"}`, route name
  `cordware_health`. It is registered before any mount, so it answers ahead of
  an application mounted at `/`. Easy Auth excludes this path from sign-in.
  RRW's own probe is `/reviewrobin/health`, inside the mount; Residential's
  are `/residentialops/health` and `/supportlogs/health`; Utilities' is
  `/utilities/health`.
- The name differs from RRW's own `health` route on purpose: inside a mounted
  application `url_for` resolves through the host's router first, and
  `url_for("health")` must not resolve to the host's route.
- The host registers no `/docs`, `/redoc` or `/openapi.json` of its own
  (`docs_url`, `redoc_url` and `openapi_url` are `None`). Registered ahead of
  a mount at `/`, they would shadow the mounted application's.

## Fake-auth guard and super-admin warning

Both read Cordware's identity settings (`cordware/spec/identity.md`) and run
in `create_app` after logging is configured and before any factory runs.

- **`check_fake_auth(settings)`.** With `ALLOW_FAKE_AUTH` off it does nothing.
  With it on and `APP_ENV` not `local` it logs `identity.fake_auth_refused`
  and raises `FakeAuthRefused`: the host is not built, so the process fails
  before any application is mounted. With it on at `local` it logs
  `identity.fake_auth_enabled` as a warning, on every start.
- **`warn_if_no_super_admin(settings)`.** In a deployed environment (`APP_ENV`
  not `local`) with an empty effective super-admin list, it logs
  `super_admin.unconfigured` as a warning. It never refuses; each application
  applies its own fallback. At `local` it is silent.

## Startup failure

A factory that raises (RRW's `validate_critical_settings` included) is logged
as `host.app_startup_failed` and the exception propagates out of
`create_app`. There is no degraded mode (v0.8 §3, "A critical application
failure fails startup").

## Lifespan

Starlette runs no lifespan for a mounted application, so the host does:

- It enters each mounted application's `router.lifespan_context` in mount
  order and exits them in reverse. An application with no `router` is skipped.
- State an application's lifespan yields is merged and yielded on, so it
  reaches `request.state` inside that application.
- A state key yielded twice raises `RuntimeError` naming the key and the
  application, and the host does not start.
- A failure entering an application's lifespan is logged as
  `host.app_startup_failed` and propagates.

Startup work may also stay in an application's factory. RRW has no lifespan.

## Logging

`cordware/logging.py` owns process-wide logging; an application never
configures the root logger.

- `configure_logging(level, loggers)` installs one `StreamHandler` on stdout
  with `JsonFormatter` on the root logger and sets the root level. It is
  idempotent: a handler it added earlier is replaced. An unrecognized level
  falls back to `INFO`. `loggers` maps a logger-name prefix to an application
  name, built from the registry.
- `JsonFormatter` renders one JSON object per record: `timestamp`, `level`,
  `logger`, `message`, every non-reserved `extra=` key at the top level, and
  `exc_info` when present.
- `ApplicationFilter` stamps `record.application` from the logger name: the
  registered application for a record from its prefix or a child of it
  (`reviewrobin` for `app` and `app.*`), `cordware` for everything else. A
  record that already carries `application` keeps it.
- `LOG_LEVEL` (default `INFO`) is the host's setting, in `CordwareSettings`.
- RRW logs under named `app.*` loggers through `app.logging_config.get_logger`.
- uvicorn's and gunicorn's own loggers keep their own handlers and do not
  reach the root handler, so their lines stay plain text.

Host events (`extra["event"]`, logger `cordware`):

| Event | When | Extra keys |
|---|---|---|
| `host.started` | The host's lifespan has entered every mounted application. | `mounted` (names, mount order) |
| `host.stopping` | The server is shutting down, before mounted lifespans exit. | `missing_identity_headers` (count of requests refused for want of Easy Auth headers, since process start) |
| `host.app_startup_failed` | A factory or a mounted lifespan raised. | `app` (name) |
| `identity.fake_auth_refused` | The guard refused (level error). | `app_env` |
| `identity.fake_auth_enabled` | The guard allowed fake auth at `local` (warning, every start). | none |
| `super_admin.unconfigured` | A deployed environment has no super-admin (warning). | none |

The identity events from `cordware.identity` (`identity.header_malformed`,
`identity.headers_missing`) are in `cordware/spec/identity.md` "Logging". The
rest of v0.8 §3 "Host logging" (unhandled requests, errors outside any
application, failing `/health` checks) is not yet built.

## Import boundary

`cordware/tests/test_import_boundary.py` reads source with `ast`, at any
depth and including literal `importlib.import_module(...)` and
`__import__(...)` calls. The `FORBIDDEN` map names, per package, the
top-level packages it may not import; a second check adds one module:

| Package | May not import |
|---|---|
| `app` | `residentialapps`; and the module `cordware.main` |
| `residentialapps` | `app`; and the module `cordware.main` |
| `cordware` | `app`, `residentialapps` |

- `cordware/tests/` is exempt: the host's tests drive real applications.
- `app` may import `cordware` (identity, `cordware.identity`) but never
  `cordware.main`, which builds the host when imported. A separate check in
  the same file reads every module an application imports, `from cordware
  import main` and dynamic imports included.
- `residentialapps/tests/` is exempt from the `cordware.main` check only
  (never from `app`): Residential's mounted tests build the host there.
- Inside `residentialapps`, neither application package imports the other
  (`residentialapps.residentialops`, `residentialapps.supportlogs`), relative imports
  resolved; `residentialapps/spec/architecture.md` has the full table.

## Tests

The host's tests live in `cordware/tests/`, a package (it has its own
`__init__.py`, so a basename shared with root `tests/` does not break
collection). `pyproject.toml` lists it in `testpaths`, so both CI jobs collect
it, as they do `residentialapps/tests`. They need no database; RRW's
`tests/conftest.py` fixtures do not reach them. RRW's own suite builds the application through `tests/_rrw_app.py`.

### The `/reviewrobin` harness

RRW's own suite builds the application alone (`tests/_rrw_app.py`), at `/`,
so its requests carry no prefix. Mounted behavior is proved two ways: under a
test mount, and live. `tests/_mounted.py` (a top-level module, like
`_rrw_app`) holds the test mount:

- `MOUNT` is `"/reviewrobin"`; a test ties it to `REGISTRY`'s path, so the
  harness cannot pass at a path nothing serves.
- `host_with(factory, path=MOUNT)` builds the host through `create_app` with a
  one-entry registry override. It puts the root logger back as it found it,
  since `create_app` configures logging.
- `mounted_rrw()` is that host with RRW's cached `tests/_rrw_app.py`
  instance at `/reviewrobin`, so the `dependency_overrides` a fixture sets
  carry into the mount. `tests/integration/conftest.py`'s `mounted_client`
  and `make_mounted_client` wrap it; request paths carry the prefix.
- `leaks(response, prefix="/reviewrobin", *, within=None)` returns every URL
  a response emits as an app path without the prefix: link, form and
  source attributes (and `data-*` URL attributes), strings in inline
  scripts, string values in a JSON body, `Location` and cookie `Path`s.
  `/.auth/…`, fragments, queries, other schemes and hosts, and relative
  paths are not app paths. `within` limits the attributes read to one
  element, by class.

`tests/integration/test_url_crawl.py` drives it over every RRW GET route.
`tests/integration/test_mount_requirements.py` pins v0.8 §3's behavior
requirements under the mount: both health probes, the bare mount's redirect,
RRW's own 404, 403 and 422 pages, `/.auth/…` links left unprefixed, and an
invitation link carrying the request's host and `/reviewrobin`.

The browser suite (`tests/browser/`) runs the real host, `uvicorn
cordware.main:app`, so RRW answers under its mount as deployed. A browser
test writes every page URL through `app_url(path)` (`tests/browser/conftest.py`),
which prefixes `MOUNT`; `tests/unit/test_browser_app_urls.py` fails a
navigation, in-page `window.location` use or URL assertion that skips it.
