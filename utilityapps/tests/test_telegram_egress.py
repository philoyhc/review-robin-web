"""The Telegram egress probe (`utilityapps/spec/utilities.md` "Telegram
egress probe"; handover §3 and §6). No test reaches Telegram: the fetch is
replaced, and urllib's opener with it where the request itself is checked."""

from __future__ import annotations

import json
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from email.message import Message
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cordware.settings import identity_settings
from utilityapps.diagnostics import routes, telegram_egress
from utilityapps.diagnostics.telegram_egress import Outcome, Reply
from utilityapps.tests._host import host_with

PAGE = "/utilities/diagnostics/telegram-egress"
RUN = PAGE + "/run"
JSON = "application/json"


def _envelope(code: int, description: str = "Unauthorized") -> bytes:
    return json.dumps({"ok": False, "error_code": code, "description": description}).encode()


def _replying(reply: Reply):
    return lambda deadline: reply


def _raising(exc: BaseException):
    def fetch(deadline: float) -> Reply:
        raise exc

    return fetch


# --- classification ---------------------------------------------------------


@pytest.mark.parametrize("code", [401, 404])
def test_telegrams_own_error_envelope_is_the_pass(code: int) -> None:
    result = telegram_egress.run(_replying(Reply(code, JSON, _envelope(code))))
    assert result.outcome is Outcome.TELEGRAM_REACHABLE
    assert (result.http_status, result.telegram_api_envelope) == (code, True)
    assert result.description == "Unauthorized"


@pytest.mark.parametrize(
    "reply",
    [
        Reply(200, "text/html", b"<html>Blocked by policy</html>"),  # a block page
        Reply(302, "text/html", b""),  # a redirect, not followed
        Reply(401, "text/html", _envelope(401)),  # right shape, wrong type
        Reply(401, JSON, _envelope(403)),  # code and status disagree
        Reply(401, JSON, json.dumps({"ok": True, "result": {}}).encode()),
        Reply(401, JSON, b"not json"),
        Reply(401, JSON, b"[1, 2]"),
        Reply(401, JSON, json.dumps({"ok": False, "error_code": 401}).encode()),
        Reply(401, JSON, json.dumps({"ok": False, "error_code": True}).encode()),
        Reply(401, JSON, b"\xff\xfe"),
    ],
)
def test_anything_else_that_answers_is_not_a_pass(reply: Reply) -> None:
    result = telegram_egress.run(_replying(reply))
    assert result.outcome is Outcome.HTTP_INTERMEDIARY_OR_UNEXPECTED
    assert result.http_status == reply.status
    assert (result.telegram_api_envelope, result.description) == (False, None)


@pytest.mark.parametrize(
    ("exc", "outcome"),
    [
        (urllib.error.URLError(socket.gaierror(-2, "Name or service not known")), "DNS_FAILURE"),
        (urllib.error.URLError(TimeoutError("timed out")), "CONNECT_TIMEOUT"),
        (TimeoutError("timed out"), "READ_TIMEOUT"),
        (urllib.error.URLError(ssl.SSLCertVerificationError(1, "bad cert")), "TLS_FAILURE"),
        (urllib.error.URLError(ssl.SSLError(1, "handshake")), "TLS_FAILURE"),
        (ssl.SSLError(1, "mid-read"), "TLS_FAILURE"),
        (urllib.error.URLError(ConnectionRefusedError(111, "refused")), "NETWORK_ERROR"),
        (ConnectionResetError(104, "reset"), "NETWORK_ERROR"),
        (urllib.error.URLError("unknown url type"), "NETWORK_ERROR"),
        (
            urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden")),
            "HTTP_INTERMEDIARY_OR_UNEXPECTED",
        ),
        (ValueError("something else"), "OTHER_ERROR"),
    ],
)
def test_failures_are_classified_without_their_detail(exc: BaseException, outcome: str) -> None:
    result = telegram_egress.run(_raising(exc))
    assert result.outcome.value == outcome
    assert result.error_type == type(exc).__name__  # for the log, never the page
    assert (result.http_status, result.telegram_api_envelope, result.description) == (
        None,
        False,
        None,
    )
    assert result.guidance  # every outcome has its sentence


def test_elapsed_time_is_measured_in_milliseconds() -> None:
    ticks = iter([10.0, 10.25])
    reply = Reply(401, JSON, _envelope(401))
    assert telegram_egress.run(_replying(reply), clock=lambda: next(ticks)).elapsed_ms == 250


def test_telegrams_description_is_cut_and_stripped_of_control_characters() -> None:
    reply = Reply(401, JSON, _envelope(401, "Unauth\x1b[31morized " + "x" * 200))
    description = telegram_egress.run(_replying(reply)).description
    assert description is not None and "\x1b" not in description
    assert len(description) == 80


# --- the request itself -----------------------------------------------------


class _Answer:
    def __init__(self, status: int, body: bytes) -> None:
        self.status, self._body = status, BytesIO(body)
        self.headers = Message()
        self.headers["Content-Type"] = JSON

    def read(self, limit: int = -1) -> bytes:
        return self._body.read(limit)

    def __enter__(self) -> _Answer:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Opener:
    def __init__(self, outcome: Any) -> None:
        self.outcome, self.calls = outcome, []

    def open(self, request: urllib.request.Request, timeout: float) -> Any:
        self.calls.append((request.full_url, request.get_method(), timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def test_the_request_is_fixed_bounded_and_reads_at_most_4_kib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _Opener(_Answer(200, b"x" * 10_000))
    monkeypatch.setattr(telegram_egress, "_opener", lambda: opener)
    reply = telegram_egress.urllib_fetch(time.monotonic() + 5)
    assert opener.calls == [
        ("https://api.telegram.org/bot000000000:INVALID/getMe", "GET", telegram_egress.TIMEOUT)
    ]
    assert telegram_egress.TIMEOUT <= 3.0 and telegram_egress.DEADLINE <= 7.0
    assert len(reply.body) == telegram_egress.BODY_LIMIT == 4096


def test_an_http_error_status_is_an_answer_not_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    headers["Content-Type"] = JSON
    error = urllib.error.HTTPError(
        telegram_egress.URL, 401, "Unauthorized", headers, BytesIO(_envelope(401))
    )
    closed: list[bool] = []
    monkeypatch.setattr(error, "close", lambda: closed.append(True))
    monkeypatch.setattr(telegram_egress, "_opener", lambda: _Opener(error))
    reply = telegram_egress.urllib_fetch(time.monotonic() + 5)
    assert (reply.status, reply.content_type) == (401, JSON)
    assert closed == [True]  # its socket is not left to the collector
    assert telegram_egress.run(lambda deadline: reply).outcome is Outcome.TELEGRAM_REACHABLE


def test_the_whole_attempt_is_held_to_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lookup or connect no socket timeout reaches still ends the run."""
    monkeypatch.setattr(telegram_egress, "DEADLINE", 0.05)
    release = threading.Event()

    def hangs(deadline: float) -> Reply:
        release.wait(5)
        return Reply(401, JSON, _envelope(401))

    started = time.monotonic()
    result = telegram_egress.run(hangs)
    release.set()
    assert time.monotonic() - started < 2
    assert result.outcome is Outcome.CONNECT_TIMEOUT
    assert result.error_type == "_Unfinished"


def test_a_trickling_body_stops_at_the_deadline() -> None:
    class Trickle:
        def read1(self, size: int) -> bytes:
            time.sleep(0.01)  # a byte at a time, each inside the socket timeout
            return b"x"

    with pytest.raises(TimeoutError):
        telegram_egress._read(Trickle(), time.monotonic() + 0.05)  # pyright: ignore[reportPrivateUsage]  -- the reader under test
    reply = telegram_egress.run(_raising(TimeoutError("probe deadline")))
    assert reply.outcome is Outcome.READ_TIMEOUT


def test_certificates_and_host_names_are_verified() -> None:
    context = telegram_egress.tls_context()
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    handlers = telegram_egress._opener().handlers  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]  -- urllib leaves the attribute untyped
    https = next(h for h in handlers if isinstance(h, urllib.request.HTTPSHandler))
    assert https._context.verify_mode is ssl.CERT_REQUIRED  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]  -- urllib keeps it private


def test_the_opener_has_no_redirect_handler_but_its_own() -> None:
    handlers = telegram_egress._opener().handlers  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]  -- urllib leaves the attribute untyped
    redirects = [h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert [type(h) for h in redirects] == [telegram_egress._NoRedirect]  # pyright: ignore[reportPrivateUsage]  -- the handler under test


def test_redirects_are_not_followed() -> None:
    handler = telegram_egress._NoRedirect()  # pyright: ignore[reportPrivateUsage]  -- the handler under test
    request = urllib.request.Request(telegram_egress.URL)
    follow = handler.redirect_request(request, BytesIO(), 302, "Found", Message(), "https://x/")
    assert follow is None


# --- the page ---------------------------------------------------------------


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    made: list[int] = []

    def fake() -> telegram_egress.Result:
        made.append(1)
        return telegram_egress.run(_replying(Reply(401, JSON, _envelope(401))))

    monkeypatch.setattr(routes, "probe", fake)
    monkeypatch.setattr(routes, "gate", routes._Gate())  # pyright: ignore[reportPrivateUsage]  -- a fresh gate per test
    yield made


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def test_the_page_explains_and_sends_nothing(client: TestClient, calls: list[int]) -> None:
    page = client.get(PAGE)
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "<h1>Telegram egress probe</h1>" in page.text
    assert f'action="{RUN}"' in page.text and 'method="post"' in page.text
    assert ">Run probe</button>" in page.text
    assert calls == []


def test_running_it_makes_one_request_and_shows_the_result(
    client: TestClient, calls: list[int], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="utilityapps.diagnostics.routes")
    page = client.post(RUN, data={"url": "https://evil.example/", "token": "123:abc"})
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert calls == [1]
    assert "TELEGRAM_REACHABLE" in page.text and "(Unauthorized)" in page.text
    assert " UTC · " in page.text and " SGT" in page.text
    assert "evil.example" not in page.text and "123:abc" not in page.text
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "outcome=TELEGRAM_REACHABLE" in logged and "correlation=" in logged
    assert "error=-" in logged
    assert "INVALID" not in logged and "bot0" not in logged


def test_a_second_run_within_30_s_is_refused(client: TestClient, calls: list[int]) -> None:
    assert client.post(RUN).status_code == 200
    again = client.post(RUN)
    assert again.status_code == 429
    assert (
        "Try again in" in again.text
        and f"less than {round(routes.MIN_INTERVAL)} s ago" in again.text
    )
    assert calls == [1]


def test_the_gate_opens_again_after_the_interval() -> None:
    gate = routes._Gate()  # pyright: ignore[reportPrivateUsage]  -- the gate under test
    assert gate.wait_left(100.0) == 0
    gate.release()
    assert gate.wait_left(110.0) == 20
    assert gate.wait_left(100.0 + routes.MIN_INTERVAL) == 0


def test_one_run_at_a_time_however_long_it_takes() -> None:
    gate = routes._Gate()  # pyright: ignore[reportPrivateUsage]  -- the gate under test
    assert gate.wait_left(100.0) == 0
    assert gate.wait_left(100.0 + 10 * routes.MIN_INTERVAL) > 0  # still running
    gate.release()
    assert gate.wait_left(100.0 + 10 * routes.MIN_INTERVAL) == 0


def test_a_probe_that_raises_still_releases_the_gate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = routes._Gate()  # pyright: ignore[reportPrivateUsage]  -- a fresh gate
    monkeypatch.setattr(routes, "gate", gate)

    def broken() -> telegram_egress.Result:
        raise RuntimeError("bug")

    monkeypatch.setattr(routes, "probe", broken)
    with pytest.raises(RuntimeError):
        client.post(RUN)
    assert gate.wait_left(1e12) == 0  # not left busy


def test_running_needs_a_post(client: TestClient, calls: list[int]) -> None:
    assert client.get(RUN).status_code == 405
    assert calls == []


@pytest.mark.parametrize(("method", "path"), [("get", PAGE), ("post", RUN)])
def test_someone_not_super_admin_gets_a_plain_403(
    client: TestClient,
    calls: list[int],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    page = getattr(client, method)(path)
    assert page.status_code == 403
    assert "<h1>Not available</h1>" in page.text
    assert calls == []


@pytest.mark.parametrize(("method", "path"), [("get", PAGE), ("post", RUN)])
def test_nobody_signed_in_gets_a_401(
    client: TestClient,
    calls: list[int],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    assert getattr(client, method)(path).status_code == 401
    assert calls == []


def test_the_index_does_not_list_it(client: TestClient) -> None:
    index = client.get("/utilities/").text
    assert "diagnostics" not in index and "Telegram" not in index


def test_a_failed_probe_leaves_health_alone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "gate", routes._Gate())  # pyright: ignore[reportPrivateUsage]  -- a fresh gate
    monkeypatch.setattr(
        routes, "probe", lambda: telegram_egress.run(_raising(ConnectionResetError()))
    )
    page = client.post(RUN)
    assert page.status_code == 200 and "NETWORK_ERROR" in page.text
    assert 'class="card alert"' in page.text
    assert client.get("/utilities/health").json() == {"status": "ok"}
