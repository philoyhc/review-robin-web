"""RRW mounted under `/reviewrobin` through the Cordware host, for tests.

Segment 21B (`guide/segment_21B_url_sweep.md`): RRW is served at `/`
until 21D, so the mount's behavior is proved here first. The host is
`cordware.main.create_app` with a registry override, and the mounted
application is the suite's own cached `tests/_rrw_app.py` instance, so
the `dependency_overrides` a fixture sets on it carry into the mount.

Imported as a top-level module, like `_rrw_app`.
"""

from __future__ import annotations

import logging
from functools import cache
from html.parser import HTMLParser
from http.cookies import SimpleCookie

import httpx
from fastapi import FastAPI

from cordware.main import AppEntry, create_app

MOUNT = "/reviewrobin"


def host_with(factory: str, path: str = MOUNT) -> FastAPI:
    """A Cordware host mounting ``factory`` (``"module:attribute"``) at
    ``path``. The host configures the root logger as it is built; that is
    put back, so the rest of the worker's tests see the logging they had."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        return create_app(
            apps=("reviewrobin",),
            registry={"reviewrobin": AppEntry(path=path, factory=factory, logger="app")},
        )
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)


@cache
def mounted_rrw() -> FastAPI:
    """The host with RRW (the cached suite instance) at `/reviewrobin`."""
    return host_with("_rrw_app:rrw_app")


_URL_ATTRS = {"href", "action", "formaction", "src"}
_NOT_APP_PATHS = ("#", "?", "mailto:", "tel:", "javascript:", "data:", "http:", "https:", "//")


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.urls += [value for name, value in attrs if name in _URL_ATTRS and value]


def leaks(response: httpx.Response, prefix: str = MOUNT) -> list[str]:
    """Every URL ``response`` emits that is an app path without ``prefix``:
    link, form action and source attributes, ``Location`` and cookie
    ``Path``s. A fragment, a query, another scheme, another host, a
    relative path or Easy Auth's host-level ``/.auth/`` is not an app
    path."""
    emitted: list[str] = []
    if "html" in response.headers.get("content-type", ""):
        parser = _Links()
        parser.feed(response.text)
        emitted += parser.urls
    if "location" in response.headers:
        emitted.append(response.headers["location"])
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        emitted += [m["path"] for m in cookie.values() if m["path"]]
    return [
        url
        for url in emitted
        if url.startswith("/")
        and not url.startswith(_NOT_APP_PATHS)
        and not url.startswith("/.auth/")
        and url != prefix
        and not url.startswith((prefix + "/", prefix + "?", prefix + "#"))
    ]
