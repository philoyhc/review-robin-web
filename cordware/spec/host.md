# Cordware host

The contract of the Cordware host: the process that serves Review Robin Web
(RRW) and, later, other applications. Design and rationale are in
`docs/cordware_repository_strategy_v0.8.md` §3; this file states what the
host does.

**Stage 1.** RRW is mounted at `/`, so every RRW URL is unchanged. Segment
21D moves the registry's `path` to `/reviewrobin`. The host serves only
through `cordware.main:app`; RRW has no standalone entry point.

## Entry point

- The start command names `cordware.main:app`.
- `create_app(apps=None, *, registry=REGISTRY)` builds the host. `apps` is a
  sequence of registry names; `None` reads `CORDWARE_APPS`. An explicit `apps`
  (including `()`) overrides the setting. `registry` exists for tests.
- `app = create_app()` runs once, at import of `cordware.main`: the entry point
  is the one construction. Importing `app.main` builds nothing
  (`tests/unit/test_app_main_builds_nothing.py`).
- `create_app` reads `CordwareSettings`, configures logging, builds every
  selected application, registers `/health`, then mounts them.

## Registry

`REGISTRY` maps an application name to `AppEntry(path, factory, logger)`:

| Field | Meaning |
|---|---|
| `path` | Mount path. |
| `factory` | `"module:attribute"` string naming a zero-argument callable that returns a complete ASGI application. |
| `logger` | Logger-name prefix the application logs under (see Logging). |

- One entry: `reviewrobin` -> `path="/"`, `factory="app.main:create_app"`,
  `logger="app"`.
- The mount path is a constant here, not a setting, so no configuration can
  move an application off its path.
- The host imports an application only by loading its `factory` string at
  construction. `cordware/main.py` names no application package.

## The host's part in `root_path`

The host emits no URL of its own and rewrites none. Its only part is the
mount: Starlette's `Mount` sets `root_path` in the ASGI scope to the mount
path before the application runs, and an application serves what is under
it. Inside the mount:

- `root_path` is the mount path (empty at `/`), and `request.url.path`
  includes it;
- `request.app.url_path_for(...)` omits it;
- `request.url_for(...)` is absolute, host and prefix included.

Adding the prefix to the URLs an application emits is the application's
job (RRW's, in `spec/architecture.md` "URL emission"). Easy Auth's
`/.auth/*` stays at the host level, outside every mount.

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

## `/health`

- The host's own route: `GET /health` returns `{"status": "ok"}`, route name
  `cordware_health`. It is registered before any mount, so it answers ahead of
  an application mounted at `/`. Easy Auth excludes this path from sign-in.
- The name differs from RRW's own `health` route on purpose: inside a mounted
  application `url_for` resolves through the host's router first, and
  `url_for("health")` must not resolve to the host's route.
- The host registers no `/docs`, `/redoc` or `/openapi.json` of its own
  (`docs_url`, `redoc_url` and `openapi_url` are `None`). Registered ahead of
  a mount at `/`, they would shadow the mounted application's.

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
| `host.stopping` | The server is shutting down, before mounted lifespans exit. | none |
| `host.app_startup_failed` | A factory or a mounted lifespan raised. | `app` (name) |

These are part of v0.8 §3 "Host logging" event 1. The rest of that list
(fake auth, identity problems, unhandled requests, errors outside any
application, failing `/health` checks) arrives with 21C and 21D; the startup
warning for an empty `SUPER_ADMIN_EMAILS` still comes from RRW until 21C.

## Import boundary

`cordware/tests/test_import_boundary.py` reads source with `ast`, at any
depth and including literal `importlib.import_module(...)` and
`__import__(...)` calls. The `FORBIDDEN` map names, per package, the
top-level packages it may not import:

| Package | May not import |
|---|---|
| `app` | `residentialapps`, `cordware` |
| `residentialapps` | `app` |
| `cordware` | `app`, `residentialapps` |

- `cordware/tests/` is exempt: the host's tests drive real applications.
- `app` may not import `cordware` until 21C moves identity there; 21C drops
  that name from its set.
- `residentialapps` joins the test when the directory exists.

## Tests

The host's tests live in `cordware/tests/`, a package (it has its own
`__init__.py`, so a basename shared with root `tests/` does not break
collection). `pyproject.toml` lists it in `testpaths`, so both CI jobs collect
it. They need no database; RRW's `tests/conftest.py` fixtures do not reach
them. RRW's own suite builds the application through `tests/_rrw_app.py`.

### The `/reviewrobin` harness

RRW is still served at `/`, so the mounted behavior is proved under a test
mount. `tests/_mounted.py` (a top-level module, like `_rrw_app`) holds it:

- `host_with(factory, path="/reviewrobin")` builds the host through
  `create_app` with a one-entry registry override. It puts the root
  logger back as it found it, since `create_app` configures logging.
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
Browser tests stay on RRW at `/` until 21D moves the registry's `path`.
