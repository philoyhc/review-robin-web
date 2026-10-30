"""Microsoft Graph as the signed-in user, through Easy Auth's token store
(`cordware/spec/identity.md` "Graph"; Utilities segment U1, rung 4).

The host owns the token, so the host owns the client: one helper for
every application, not a copy per application. Deployed, Easy Auth puts
the user's delegated Graph token in `X-MS-TOKEN-AAD-ACCESS-TOKEN`; with
fake auth on there is no token, and `directory_for` answers from a fixed
fake directory of invented accounts instead.

Only directory lookups are built, for the Email Address Checker. A
failure is a `GraphError` with a `kind`, never an empty answer: a caller
must not read "could not ask" as "nobody there".

The standard library makes the requests: nothing here needs a dependency
the applications do not already have. `GraphDirectory` takes the
transport as a parameter, so tests never touch the network.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from starlette.requests import HTTPConnection

from cordware.identity import fake_auth, is_local
from cordware.settings import IdentitySettings

log = logging.getLogger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
TOKEN_HEADER = "X-MS-TOKEN-AAD-ACCESS-TOKEN"
_SELECT = "id,displayName,mail,userPrincipalName"
# More than one match is all a caller needs to know (`AMBIGUOUS`); a page
# of five spares reading a directory's worth for a shared address.
_TOP = 5
# The longest `Retry-After` honored before giving up on that lookup.
_MAX_WAIT = 30.0


@dataclass(frozen=True)
class DirectoryUser:
    id: str
    display_name: str
    mail: str | None
    user_principal_name: str


class GraphError(Exception):
    """A lookup that did not finish. ``kind`` is one of `KINDS`; the
    message carries no address, name or token."""

    KINDS = ("no_token", "unauthorized", "forbidden", "throttled", "server", "network", "bad_response")

    def __init__(self, kind: str, status: int | None = None) -> None:
        assert kind in self.KINDS, kind
        super().__init__(kind if status is None else f"{kind} ({status})")
        self.kind = kind
        self.status = status


class Directory(Protocol):
    def find_users(self, address: str) -> list[DirectoryUser]:
        """Every user whose `mail` or `userPrincipalName` is ``address``
        (exactly, as Graph compares), up to a small page."""
        ...


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, Mapping[str, str], float], Response]


def urllib_transport(url: str, headers: Mapping[str, str], timeout: float) -> Response:
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:  # noqa: S310 - fixed https root
            return Response(reply.status, dict(reply.headers), reply.read())
    except urllib.error.HTTPError as exc:
        return Response(exc.code, dict(exc.headers or {}), exc.read() or b"")


def odata_string(value: str) -> str:
    """``value`` as an OData string literal: quoted, a quote doubled."""
    return "'" + value.replace("'", "''") + "'"


def _retry_after(headers: Mapping[str, str]) -> float:
    for name, value in headers.items():
        if name.lower() == "retry-after":
            try:
                return max(0.0, float(value))
            except ValueError:
                return 1.0
    return 1.0


class GraphDirectory:
    """Directory lookups with one user's delegated token.

    A `429` waits its `Retry-After` (up to `_MAX_WAIT`); a `5xx` or a
    network failure waits 1 s, then 2 s. Either is retried at most
    ``retries`` times, then raised. `401` and `403` are raised at once."""

    def __init__(
        self,
        token: str,
        *,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 2,
        timeout: float = 10.0,
    ) -> None:
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        self._transport = transport
        self._sleep = sleep
        self._retries = retries
        self._timeout = timeout

    def find_users(self, address: str) -> list[DirectoryUser]:
        literal = odata_string(address)
        query = urlencode(
            {
                "$filter": f"mail eq {literal} or userPrincipalName eq {literal}",
                "$select": _SELECT,
                "$top": str(_TOP),
            }
        )
        return _users(self._get(f"{GRAPH_ROOT}/users?{query}"))

    def _get(self, url: str) -> bytes:
        for attempt in range(self._retries + 1):
            last = attempt == self._retries
            try:
                reply = self._transport(url, self._headers, self._timeout)
            except OSError:
                error, wait = GraphError("network"), 2.0**attempt
            else:
                if 200 <= reply.status < 300:
                    return reply.body
                if reply.status == 401:
                    raise _logged(GraphError("unauthorized", 401))
                if reply.status == 403:
                    raise _logged(GraphError("forbidden", 403))
                if reply.status == 429:
                    wait = _retry_after(reply.headers)
                    error = GraphError("throttled", 429)
                    if wait > _MAX_WAIT:
                        raise _logged(error)
                elif reply.status >= 500:
                    error, wait = GraphError("server", reply.status), 2.0**attempt
                else:
                    raise _logged(GraphError("bad_response", reply.status))
            if last:
                raise _logged(error)
            self._sleep(wait)
        raise AssertionError("unreachable")


def _logged(error: GraphError) -> GraphError:
    # The kind and status only: never the address, the query or the token.
    log.warning(
        "graph request failed",
        extra={"event": "graph.request_failed", "kind": error.kind, "status": error.status},
    )
    return error


def _users(body: bytes) -> list[DirectoryUser]:
    try:
        values = json.loads(body)["value"]
        return [
            DirectoryUser(
                id=str(v["id"]),
                display_name=str(v.get("displayName") or ""),
                mail=(str(v["mail"]) if v.get("mail") else None),
                user_principal_name=str(v.get("userPrincipalName") or ""),
            )
            for v in values
        ]
    except (ValueError, KeyError, TypeError):
        raise _logged(GraphError("bad_response")) from None


# The fake directory: invented `example.edu` accounts, one per case a
# caller must handle. Never real data (functional spec §9).
FAKE_USERS = (
    DirectoryUser("11111111-1111-4111-8111-111111111111", "Jane Tan", "jane.tan@example.edu", "e0123456@example.edu"),
    DirectoryUser("22222222-2222-4222-8222-222222222222", "Arun Kumar", "arun.kumar@example.edu", "arun.kumar@example.edu"),
    DirectoryUser("33333333-3333-4333-8333-333333333333", "Lab Account", None, "lab01@example.edu"),
    DirectoryUser("44444444-4444-4444-8444-444444444444", "Wei Ling Lim", "office@example.edu", "e0222222@example.edu"),
    DirectoryUser("55555555-5555-4555-8555-555555555555", "Office Desk", "office.desk@example.edu", "office@example.edu"),
)
#: Addresses the fake directory fails on, by kind, to show each failure.
FAKE_FAILURES = {
    "throttled@example.edu": "throttled",
    "outage@example.edu": "server",
    "denied@example.edu": "forbidden",
}


class FakeDirectory:
    """`FAKE_USERS`, matched as Graph would: `mail` or UPN, any case."""

    def __init__(self, users: tuple[DirectoryUser, ...] = FAKE_USERS) -> None:
        self._users = users

    def find_users(self, address: str) -> list[DirectoryUser]:
        key = address.strip().lower()
        if key in FAKE_FAILURES:
            kind = FAKE_FAILURES[key]
            raise GraphError(kind, {"throttled": 429, "server": 503, "forbidden": 403}[kind])
        return [
            user
            for user in self._users
            if key in {(user.mail or "").lower(), user.user_principal_name.lower()}
        ][:_TOP]


def directory_for(request: HTTPConnection, settings: IdentitySettings | None = None) -> Directory:
    """The directory as the request's signed-in user sees it.

    With fake auth on (a local run only) it is `FakeDirectory`. Otherwise
    it is Graph with the user's delegated token, and with no token
    `GraphError("no_token")`: Easy Auth's token store is off, or the
    sign-in did not ask for Graph."""
    if is_local(settings) and fake_auth(settings).enabled:
        return FakeDirectory()
    token = request.headers.get(TOKEN_HEADER, "").strip()
    if not token:
        raise _logged(GraphError("no_token"))
    return GraphDirectory(token)
