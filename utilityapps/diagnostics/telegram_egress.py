"""One outbound HTTPS request to Telegram's Bot API, classified
(`utilityapps/docs/cordware_telegram_egress_probe_handover_v0.1.md` §3).

The request is fixed: ``GET`` of `getMe` with a token-shaped path that is
invalid on purpose, so nothing secret is sent and Telegram answers with
its own error envelope (`{"ok": false, "error_code": 401, ...}`). That
envelope, whatever its code, is the pass: it proves the reply came from
the Bot API, not from something in between. Nothing here takes a host,
path or token from a caller.

The client is urllib, as `cordware.graph` uses: it honours a proxy set in
the environment, as a later Telegram client on the same host would, and it
verifies certificates and host names by default. Redirects are refused, not
followed. Every socket operation (connect, TLS, send, each read) is held to
``TIMEOUT`` seconds, and at most ``BODY_LIMIT`` bytes are read.
"""

from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import IO, Any, cast

HOST = "api.telegram.org"
# Bot id 0 does not exist, so no real bot is ever addressed.
URL = f"https://{HOST}/bot000000000:INVALID/getMe"
TIMEOUT = 3.0
BODY_LIMIT = 4096
_DESCRIPTION_LIMIT = 80


class Outcome(StrEnum):
    TELEGRAM_REACHABLE = "TELEGRAM_REACHABLE"
    DNS_FAILURE = "DNS_FAILURE"
    CONNECT_TIMEOUT = "CONNECT_TIMEOUT"
    READ_TIMEOUT = "READ_TIMEOUT"
    TLS_FAILURE = "TLS_FAILURE"
    NETWORK_ERROR = "NETWORK_ERROR"
    HTTP_INTERMEDIARY_OR_UNEXPECTED = "HTTP_INTERMEDIARY_OR_UNEXPECTED"
    OTHER_ERROR = "OTHER_ERROR"


GUIDANCE: dict[Outcome, str] = {
    Outcome.TELEGRAM_REACHABLE: (
        "Telegram's Bot API answered from this App Service: no egress request "
        "is needed for api.telegram.org at this time."
    ),
    Outcome.DNS_FAILURE: (
        "api.telegram.org did not resolve: check the App Service's DNS "
        "before calling this a firewall block."
    ),
    Outcome.CONNECT_TIMEOUT: (
        "No connection within the time allowed: possibly a route, NSG or "
        "central firewall; give IT the time and correlation ID."
    ),
    Outcome.READ_TIMEOUT: (
        "Connected, but no complete answer in time: run it once more later, "
        "then give IT the time and correlation ID."
    ),
    Outcome.TLS_FAILURE: (
        "The TLS handshake or certificate check failed: possibly TLS "
        "inspection; ask IT about the trust chain, never turn verification off."
    ),
    Outcome.NETWORK_ERROR: (
        "The connection was refused or reset: give IT the time and correlation ID."
    ),
    Outcome.HTTP_INTERMEDIARY_OR_UNEXPECTED: (
        "Something answered, but not as Telegram's Bot API does: possibly a "
        "proxy or block page; not a pass."
    ),
    Outcome.OTHER_ERROR: (
        "The probe failed in an unexpected way: see the server log by correlation ID."
    ),
}


@dataclass(frozen=True)
class Reply:
    status: int
    content_type: str
    body: bytes  # at most BODY_LIMIT bytes


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    http_status: int | None
    telegram_api_envelope: bool
    description: str | None  # Telegram's own, sanitised; only with the envelope
    elapsed_ms: int

    @property
    def guidance(self) -> str:
        return GUIDANCE[self.outcome]


Fetch = Callable[[], Reply]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx comes back as an answer, never followed (handover §3, step 3)."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


def tls_context() -> ssl.SSLContext:
    """The default: certificates verified, host names checked."""
    return ssl.create_default_context()


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        _NoRedirect, urllib.request.HTTPSHandler(context=tls_context())
    )


def _reply(status: int, headers: Any, stream: IO[bytes]) -> Reply:
    content_type = str(headers.get("Content-Type", "")) if headers is not None else ""
    return Reply(status, content_type, stream.read(BODY_LIMIT))


def urllib_fetch() -> Reply:
    request = urllib.request.Request(
        URL, headers={"Accept": "application/json", "User-Agent": "cordware-egress-probe"}
    )
    try:
        with _opener().open(request, timeout=TIMEOUT) as answer:  # noqa: S310 - fixed https URL
            return _reply(answer.status, answer.headers, answer)
    except urllib.error.HTTPError as exc:
        return _reply(exc.code, exc.headers, exc)


def _envelope(reply: Reply) -> str | None:
    """Telegram's error description if ``reply`` is its error envelope:
    a JSON object with ``ok`` false and ``error_code`` the HTTP status."""
    if "json" not in reply.content_type.lower():
        return None
    try:
        data: object = json.loads(reply.body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    fields = cast(dict[str, object], data)
    code, description = fields.get("error_code"), fields.get("description")
    if fields.get("ok") is not False or type(code) is not int or code != reply.status:
        return None
    if not isinstance(description, str):
        return None
    shown = "".join(c for c in description if c.isprintable())
    return shown[:_DESCRIPTION_LIMIT]


def _failure(exc: BaseException) -> Outcome:
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, BaseException):
            return _cause(reason, connecting=True)
        return Outcome.NETWORK_ERROR
    return _cause(exc, connecting=False)


def _cause(exc: BaseException, *, connecting: bool) -> Outcome:
    # Order matters: an SSL error is an OSError, and so is a timeout.
    if isinstance(exc, socket.gaierror):
        return Outcome.DNS_FAILURE
    if isinstance(exc, ssl.SSLError | ssl.CertificateError):
        return Outcome.TLS_FAILURE
    if isinstance(exc, TimeoutError):
        return Outcome.CONNECT_TIMEOUT if connecting else Outcome.READ_TIMEOUT
    if isinstance(exc, OSError):
        return Outcome.NETWORK_ERROR
    return Outcome.OTHER_ERROR


def run(fetch: Fetch = urllib_fetch, clock: Callable[[], float] = time.monotonic) -> Result:
    """One attempt, no retry."""
    started = clock()
    try:
        reply = fetch()
    except Exception as exc:  # classified, never shown
        elapsed = round((clock() - started) * 1000)
        return Result(_failure(exc), None, False, None, elapsed)
    elapsed = round((clock() - started) * 1000)
    description = _envelope(reply)
    if description is None:
        return Result(Outcome.HTTP_INTERMEDIARY_OR_UNEXPECTED, reply.status, False, None, elapsed)
    return Result(Outcome.TELEGRAM_REACHABLE, reply.status, True, description, elapsed)
