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
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.types import ASGIApp


@dataclass(frozen=True)
class AppEntry:
    """One mountable application: where it mounts and how to build it.

    ``factory`` is a ``"module:attribute"`` path to a zero-argument
    callable returning a complete ASGI application."""

    path: str
    factory: str


# RRW mounts at `/` until segment 21D moves it to `/reviewrobin`. A
# constant, not a setting, so no configuration can move it by accident.
REGISTRY: Mapping[str, AppEntry] = {
    "reviewrobin": AppEntry(path="/", factory="app.main:create_app"),
}


class CordwareSettings(BaseSettings):
    """The host's own settings, read from the repository-root `.env`; a
    shell value overrides the file (v0.8 §3)."""

    cordware_apps: str | None = None

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


def _load_factory(path: str) -> Callable[[], ASGIApp]:
    module_name, _, attribute = path.partition(":")
    return getattr(importlib.import_module(module_name), attribute)


def create_app(
    apps: Sequence[str] | None = None,
    *,
    registry: Mapping[str, AppEntry] = REGISTRY,
) -> FastAPI:
    """Build the host and mount ``apps`` (default: from `CORDWARE_APPS`).

    A mounted application's factory raising, its startup validation
    included, propagates: the host does not start (v0.8 §3)."""
    names = parse_apps(
        CordwareSettings().cordware_apps if apps is None else ",".join(apps),
        registry,
    )
    mounted = [(registry[name], _load_factory(registry[name].factory)()) for name in names]

    @asynccontextmanager
    async def lifespan(_host: FastAPI) -> AsyncIterator[None]:
        # Starlette runs no lifespan for a mounted application, so the
        # host enters each one in mount order and exits them in reverse.
        async with AsyncExitStack() as stack:
            for _, sub_app in mounted:
                router = getattr(sub_app, "router", None)
                if router is not None:
                    await stack.enter_async_context(router.lifespan_context(sub_app))
            yield

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
    @host.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for entry, sub_app in mounted:
        host.mount(entry.path, sub_app)
    return host


app = create_app()
