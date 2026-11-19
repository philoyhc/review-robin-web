"""Scratch exercises (segment AD1N, ruling 59): until AD2, *New exercise*
makes a blank draft the operator sets up page by page, held in this
process's memory for one browser and never written anywhere.

A browser is known by an opaque cookie, ``applydesk-scratch``, set when it
first creates one. ``Middleware`` puts the request's token in a context
variable, so ``sample_data``'s lookups find the browser's scratch
exercises beside the fixed sample without any route passing them. A
restart or a deploy clears every scratch exercise, as does eight idle
hours; a browser holds at most five.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from http.cookies import SimpleCookie
from typing import Any

from applydesk import sample_data
from applydesk.ids import generate_public_id

COOKIE = "applydesk-scratch"
#: Scratch exercises one browser may hold (ruling 59).
LIMIT = 5
#: Idle seconds before a browser's scratch exercises are dropped.
IDLE_SECONDS = 8 * 3600
#: The largest page post a scratch exercise takes, in bytes.
MAX_BODY = 256 * 1024


class Refused(Exception):
    """A request the store will not carry out, said to the operator."""


@dataclass
class Scratch:
    """One scratch exercise: its details, and each Setup page's state as
    that page last saved it (later rungs), by page."""

    exercise: sample_data.Exercise
    pages: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


@dataclass
class _Browser:
    touched: float
    exercises: dict[str, Scratch] = field(default_factory=lambda: dict[str, Scratch]())


_BOX: dict[str, _Browser] = {}
_LOCK = threading.Lock()
_token: ContextVar[str | None] = ContextVar("applydesk_scratch_token", default=None)


def _prune(now: float) -> None:
    for token in [t for t, b in _BOX.items() if now - b.touched > IDLE_SECONDS]:
        del _BOX[token]


def _browser(token: str | None, now: float) -> _Browser | None:
    _prune(now)
    found = _BOX.get(token) if token else None
    if found is not None:
        found.touched = now
    return found


def token() -> str | None:
    """The current request's browser token, if it has one."""
    return _token.get()


def mine() -> tuple[Scratch, ...]:
    """The current browser's scratch exercises, newest first."""
    with _LOCK:
        found = _browser(_token.get(), time.monotonic())
        return tuple(reversed(found.exercises.values())) if found else ()


def get(public_id: str) -> Scratch | None:
    """The current browser's scratch exercise with this ID, else None: one
    browser never sees another's."""
    with _LOCK:
        found = _browser(_token.get(), time.monotonic())
        return found.exercises.get(public_id) if found else None


def is_scratch(public_id: str) -> bool:
    return get(public_id) is not None


def new_token() -> str:
    return secrets.token_urlsafe(24)


def blank(name: str, public_id: str) -> sample_data.Exercise:
    """A blank draft, as *Graduate Travel Grant 2027*: a name and nothing
    else (the rest set on Details and the Setup pages)."""
    return sample_data.Exercise(
        public_id=public_id,
        code="",
        name=name,
        state="Draft",
        form_open=True,
        eligibility="Not set",
        blind=False,
        opens="Not set",
        application_stage_ends="Not set",
        expected_outcome="Not set",
        summary="",
    )


def create(browser_token: str, name: str) -> Scratch:
    """A new scratch exercise named ``name`` for this browser."""
    name = name.strip()
    if not name:
        raise Refused("A name is needed.")
    if len(name) > 200:
        raise Refused("A name is at most 200 characters.")
    with _LOCK:
        now = time.monotonic()
        found = _browser(browser_token, now) or _BOX.setdefault(browser_token, _Browser(now))
        if len(found.exercises) >= LIMIT:
            raise Refused(f"At most {LIMIT} scratch exercises at once: discard one first.")
        taken = {e.public_id for e in sample_data.EXERCISES} | {
            k for b in _BOX.values() for k in b.exercises
        }
        public_id = generate_public_id()
        while public_id in taken:
            public_id = generate_public_id()
        made = Scratch(blank(name, public_id))
        found.exercises[public_id] = made
        return made


def discard(browser_token: str | None, public_id: str) -> bool:
    """Drop one of this browser's scratch exercises; False if none."""
    with _LOCK:
        found = _browser(browser_token, time.monotonic())
        return bool(found and found.exercises.pop(public_id, None))


def update(public_id: str, **changes: Any) -> sample_data.Exercise:
    """Change a scratch exercise's details (Details' *Lock*)."""
    with _LOCK:
        found = _browser(_token.get(), time.monotonic())
        held = found.exercises.get(public_id) if found else None
        if held is None:
            raise Refused("No such scratch exercise.")
        held.exercise = replace(held.exercise, **changes)
        return held.exercise


def clear() -> None:
    """Forget every scratch exercise (tests)."""
    with _LOCK:
        _BOX.clear()


Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]


class Middleware:
    """Puts the request's scratch token, from its cookie, in context, so
    every lookup the request makes sees that browser's scratch exercises."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        found: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"cookie":
                jar: SimpleCookie = SimpleCookie()
                try:
                    jar.load(value.decode("latin-1"))
                except Exception:  # a malformed header is no token
                    continue
                if COOKIE in jar:
                    found = jar[COOKIE].value
        reset = _token.set(found)
        try:
            await self.app(scope, receive, send)
        finally:
            _token.reset(reset)
