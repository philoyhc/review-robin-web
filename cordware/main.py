"""The assembled entry point: `cordware.main:app`.

`create_app()` builds the host once. It registers the host's own
`/health` first, then mounts each application named by `CORDWARE_APPS`
from `REGISTRY`. Unset mounts every registered application; empty mounts
none, which runs the host alone (v0.8 §3, "The independence
requirement").

An application is imported only through its registry entry's factory
path, at mount time, so this module names no application package.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.types import ASGIApp, Receive, Scope, Send

from cordware.identity import is_local, missing_header_count, super_admin_configured
from cordware.logging import configure_logging
from cordware.settings import IdentitySettings, identity_settings
from cordware.web.landing import LandingLink, add_landing_page

log = logging.getLogger("cordware")


@dataclass(frozen=True)
class AppEntry:
    """One mountable application: where it mounts, how to build it, and
    the logger-name prefix it logs under.

    ``factory`` is a ``"module:attribute"`` path to a zero-argument
    callable returning a complete ASGI application. Records from
    ``logger`` and its children are stamped with the application's
    name. ``title`` is how the host's landing page names it; empty, the
    page uses the registry name."""

    path: str
    factory: str
    logger: str
    title: str = ""


# RRW mounts at `/reviewrobin` (segment 21D; v0.8 §3), the two Residential
# applications at `/residentialops` and `/supportlogs` (Residential segment
# 1A), Utilities at `/utilities` (Utilities segment U1). Constants, not settings, so no configuration can move one by accident.
REGISTRY: Mapping[str, AppEntry] = {
    "reviewrobin": AppEntry(
        path="/reviewrobin",
        factory="app.main:create_app",
        logger="app",
        title="Review Robin",
    ),
    "residentialops": AppEntry(
        path="/residentialops",
        factory="residentialapps.residentialops.main:create_app",
        logger="residentialapps.residentialops",
        title="Residential Operations",
    ),
    "supportlogs": AppEntry(
        path="/supportlogs",
        factory="residentialapps.supportlogs.main:create_app",
        logger="residentialapps.supportlogs",
        title="Support Logs",
    ),
    "utilities": AppEntry(
        path="/utilities",
        factory="utilityapps.main:create_app",
        logger="utilityapps",
        title="Utilities",
    ),
}


class CordwareSettings(BaseSettings):
    """The host's own settings, read from the repository-root `.env`; a
    shell value overrides the file (v0.8 §3)."""

    cordware_apps: str | None = None
    cordware_public_origin: str | None = None
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def parse_apps(raw: str | None, registry: Mapping[str, AppEntry]) -> tuple[str, ...]:
    """The application names a `CORDWARE_APPS` value selects.

    ``None`` (unset) selects every registered application; an empty or
    blank value selects none. Names are comma-separated, trimmed and
    matched exactly. An unknown or repeated name is refused, naming it."""
    if raw is None:
        return tuple(registry)
    names = [name.strip() for name in raw.split(",") if name.strip()]
    unknown = [name for name in names if name not in registry]
    if unknown:
        raise ValueError(
            f"CORDWARE_APPS names unknown application(s) {', '.join(unknown)}; "
            f"registered: {', '.join(registry)}"
        )
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"CORDWARE_APPS repeats {', '.join(repeated)}")
    return tuple(names)


@dataclass(frozen=True)
class PublicOrigin:
    """The address users reach the host at: `scheme://netloc`."""

    scheme: str
    host: str
    port: int
    netloc: str


_DEFAULT_PORTS = {"http": 80, "https": 443}


def parse_public_origin(raw: str | None, *, local: bool) -> PublicOrigin | None:
    """The origin a `CORDWARE_PUBLIC_ORIGIN` value names (segment 21E).

    Unset or blank is ``None``. Otherwise the value must be
    ``http(s)://host[:port]``, with nothing after the host but an
    optional ``/``; ``http`` only at `APP_ENV=local`. Anything else
    raises `ValueError` naming the setting."""
    if raw is None or not raw.strip():
        return None
    value = raw.strip()

    def refuse(reason: str) -> ValueError:
        return ValueError(f"CORDWARE_PUBLIC_ORIGIN={value!r}: {reason}")

    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise refuse("must start with https:// (or http:// at APP_ENV=local)")
    if scheme == "http" and not local:
        raise refuse("http is allowed only at APP_ENV=local")
    if parts.username is not None or parts.password is not None:
        raise refuse("must not carry user info")
    if parts.path not in ("", "/") or parts.query or parts.fragment or value.endswith(("?", "#")):
        raise refuse("must be an origin alone, with no path, query or fragment")
    try:
        port = parts.port
    except ValueError:
        raise refuse("has an invalid port") from None
    if not parts.hostname:
        raise refuse("has no host")
    return PublicOrigin(
        scheme=scheme,
        host=parts.hostname,
        port=port or _DEFAULT_PORTS[scheme],
        netloc=parts.netloc.lower(),
    )


class PublicOriginMiddleware:
    """Rewrites each HTTP request's scheme, server and `Host` header to
    the public origin, so every URL built from the request names it
    (segment 21E). No forwarded header is read; every other header, path
    and `root_path` pass through as sent."""

    def __init__(self, app: ASGIApp, origin: PublicOrigin) -> None:
        self.app = app
        self.origin = origin
        self.host_header = (b"host", origin.netloc.encode("latin-1"))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope = {
                **scope,
                "scheme": self.origin.scheme,
                "server": (self.origin.host, self.origin.port),
                "headers": [
                    *(item for item in scope["headers"] if item[0] != b"host"),
                    self.host_header,
                ],
            }
        await self.app(scope, receive, send)


def _load_factory(path: str) -> Callable[[], ASGIApp]:
    module_name, _, attribute = path.partition(":")
    return getattr(importlib.import_module(module_name), attribute)


def _log_startup_failure(name: str) -> None:
    log.exception(
        "mounted application failed to start",
        extra={"event": "host.app_startup_failed", "app": name},
    )


def _build(name: str, entry: AppEntry) -> ASGIApp:
    try:
        return _load_factory(entry.factory)()
    except Exception:
        _log_startup_failure(name)
        raise


class FakeAuthRefused(RuntimeError):
    """Fake auth is on outside `APP_ENV=local`: the host will not start."""


def check_fake_auth(settings: IdentitySettings) -> None:
    """The host's guard (v0.8 §3): fake auth only at `APP_ENV=local`.

    Refused, the host is not built, so the process fails before any
    application is mounted. Allowed, it warns on every start."""
    if not settings.allow_fake_auth:
        return
    if settings.app_env != "local":
        log.error(
            "fake auth refused outside APP_ENV=local",
            extra={"event": "identity.fake_auth_refused", "app_env": settings.app_env},
        )
        raise FakeAuthRefused(
            f"ALLOW_FAKE_AUTH is on with APP_ENV={settings.app_env!r}; "
            "fake auth is allowed only at APP_ENV=local"
        )
    log.warning(
        "fake auth is on: every request without Easy Auth headers is the fake user",
        extra={"event": "identity.fake_auth_enabled"},
    )


def warn_if_no_super_admin(settings: IdentitySettings) -> None:
    """In a deployed environment, an empty super-admin list is worth a
    loud line: each application then applies its own fallback (RRW's is
    "any admin manages admins")."""
    if is_local(settings) or super_admin_configured(settings):
        return
    log.warning(
        "no super-admin configured (SUPER_ADMIN_EMAILS empty); set it to "
        "enable the protected platform tier",
        extra={"event": "super_admin.unconfigured"},
    )


def create_app(
    apps: Sequence[str] | None = None,
    *,
    registry: Mapping[str, AppEntry] = REGISTRY,
) -> FastAPI:
    """Build the host and mount ``apps`` (default: from `CORDWARE_APPS`).

    The host configures the root logger first, so what a factory logs
    while it builds is already structured. A mounted application's
    factory raising, its startup validation included, is logged and
    propagates: the host does not start (v0.8 §3), as it does not when
    the fake-auth guard refuses (`check_fake_auth`)."""
    settings = CordwareSettings()
    configure_logging(
        settings.log_level, {entry.logger: name for name, entry in registry.items()}
    )
    check_fake_auth(identity_settings)
    warn_if_no_super_admin(identity_settings)
    origin = parse_public_origin(
        settings.cordware_public_origin, local=is_local(identity_settings)
    )
    names = parse_apps(settings.cordware_apps if apps is None else ",".join(apps), registry)
    mounted = [(registry[name], _build(name, registry[name])) for name in names]

    @asynccontextmanager
    async def lifespan(_host: FastAPI) -> AsyncIterator[dict[str, Any]]:
        # Starlette runs no lifespan for a mounted application, so the
        # host enters each one in mount order and exits them in reverse.
        # State a lifespan yields is merged and yielded on, which is how
        # it reaches `request.state` inside the mounted application.
        state: dict[str, Any] = {}
        async with AsyncExitStack() as stack:
            for name, (_, sub_app) in zip(names, mounted, strict=True):
                router = getattr(sub_app, "router", None)
                if router is None:
                    continue
                try:
                    yielded = await stack.enter_async_context(router.lifespan_context(sub_app))
                except Exception:
                    _log_startup_failure(name)
                    raise
                for key, value in (yielded or {}).items():
                    if key in state:
                        raise RuntimeError(
                            f"lifespan state key {key!r} from {name!r} is already set"
                        )
                    state[key] = value
            log.info(
                "host started", extra={"event": "host.started", "mounted": list(names)}
            )
            try:
                yield state
            finally:
                log.info(
                    "host stopping",
                    extra={
                        "event": "host.stopping",
                        "missing_identity_headers": missing_header_count(),
                    },
                )

    # No docs or schema routes of the host's own: registered ahead of the
    # mount, they would shadow those of an application mounted at `/`.
    host = FastAPI(
        title="Cordware",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Registered before any mount, so it answers ahead of an application
    # mounted at `/`. Easy Auth excludes this path from sign-in.
    # Named apart from RRW's own `health` route: inside a mounted app,
    # `url_for` resolves through the host's router first.
    @host.get("/health", include_in_schema=False, name="cordware_health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Also ahead of the mounts; it stands aside for an application at `/`.
    add_landing_page(
        host,
        [
            LandingLink(title=entry.title or name, path=entry.path)
            for name, (entry, _) in zip(names, mounted, strict=True)
        ],
    )

    for entry, sub_app in mounted:
        host.mount(entry.path, sub_app)
    # Outermost, and only when set: unset, the host is as it was.
    if origin is not None:
        host.add_middleware(PublicOriginMiddleware, origin=origin)
    return host


app = create_app()
