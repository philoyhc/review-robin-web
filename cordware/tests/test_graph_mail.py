"""The host's send primitive (`cordware/graph.py`, RRW segment 14F):
the request it makes, what each answer becomes, the fake mailer, and
which mailer a request gets. No test touches the network: `GraphMailer`
takes its transport as a parameter."""

from __future__ import annotations

import json
import logging

import pytest
from starlette.requests import Request

from cordware import graph
from cordware.graph import FakeMailer, GraphError, GraphMailer, MailMessage, Response
from cordware.settings import IdentitySettings


class Script:
    """A POST transport answering from a list, recording each request."""

    def __init__(self, *replies: Response | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str], bytes]] = []

    def __call__(self, url: str, headers, body: bytes, timeout: float) -> Response:
        self.calls.append((url, dict(headers), body))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


ACCEPTED = Response(202, {}, b"")
MESSAGE = MailMessage(to="rev@example.edu", subject="Your review", body="Hello\nthere")


def mailer(script: Script, sleeps: list[float] | None = None) -> GraphMailer:
    return GraphMailer("tok", transport=script, sleep=(sleeps if sleeps is not None else []).append)


def test_one_post_to_me_send_mail_with_the_token_and_a_text_body() -> None:
    script = Script(ACCEPTED)
    mailer(script).send_mail(MESSAGE)
    url, headers, body = script.calls[0]
    assert url == f"{graph.GRAPH_ROOT}/me/sendMail"
    assert headers["Authorization"] == "Bearer tok"
    payload = json.loads(body)
    assert payload == {
        "message": {
            "subject": "Your review",
            "body": {"contentType": "Text", "content": "Hello\nthere"},
            "toRecipients": [{"emailAddress": {"address": "rev@example.edu"}}],
        },
        "saveToSentItems": False,
    }


def test_bcc_reply_to_and_sent_items_reach_the_payload() -> None:
    payload = graph.send_mail_payload(
        MailMessage(
            to="rev@example.edu",
            subject="s",
            body="b",
            cc=("dean@example.edu",),
            bcc=("me@example.edu",),
            reply_to="help@example.edu",
            save_to_sent_items=True,
        )
    )
    assert payload["message"]["ccRecipients"] == [{"emailAddress": {"address": "dean@example.edu"}}]
    assert payload["message"]["bccRecipients"] == [{"emailAddress": {"address": "me@example.edu"}}]
    assert payload["message"]["replyTo"] == [{"emailAddress": {"address": "help@example.edu"}}]
    assert payload["saveToSentItems"] is True


@pytest.mark.parametrize(
    ("reply", "kind"),
    [
        (Response(401, {}, b""), "unauthorized"),
        (Response(403, {}, b'{"error": {"code": "ErrorAccessDenied"}}'), "forbidden"),
        (Response(500, {}, b""), "server"),
        (Response(400, {}, b'{"error": {"code": "ErrorInvalidRecipients"}}'), "bad_response"),
        (OSError("reset"), "network"),
    ],
)
def test_each_failure_raises_its_kind_and_is_not_retried(
    reply: Response | Exception, kind: str
) -> None:
    script = Script(reply, ACCEPTED)
    with pytest.raises(GraphError) as caught:
        mailer(script).send_mail(MESSAGE)
    assert caught.value.kind == kind
    assert len(script.calls) == 1  # a 5xx or a reset may follow an accepted send


def test_a_throttle_waits_its_retry_after_once_then_sends() -> None:
    sleeps: list[float] = []
    script = Script(Response(429, {"Retry-After": "3"}, b""), ACCEPTED)
    mailer(script, sleeps).send_mail(MESSAGE)
    assert sleeps == [3.0]
    assert len(script.calls) == 2


def test_a_second_throttle_or_a_long_wait_raises() -> None:
    throttled = Response(429, {"Retry-After": "3"}, b"")
    with pytest.raises(GraphError, match="throttled"):
        mailer(Script(throttled, throttled)).send_mail(MESSAGE)
    with pytest.raises(GraphError, match="throttled"):
        mailer(Script(Response(429, {"Retry-After": "120"}, b""))).send_mail(MESSAGE)


def test_the_fake_mailer_keeps_the_message_and_sends_nothing() -> None:
    fake = FakeMailer()
    fake.send_mail(MESSAGE)
    assert fake.sent == [MESSAGE]


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw})


def test_fake_auth_on_a_local_run_gets_the_fake_mailer() -> None:
    settings = IdentitySettings(app_env="local", allow_fake_auth=True, _env_file=None)  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option
    assert isinstance(graph.mailer_for(_request(), settings), FakeMailer)


def test_otherwise_the_mailer_uses_the_request_token() -> None:
    settings = IdentitySettings(app_env="production", allow_fake_auth=False, _env_file=None)  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option
    found = graph.mailer_for(_request({graph.TOKEN_HEADER: "abc"}), settings)
    assert isinstance(found, GraphMailer)
    assert found._headers["Authorization"] == "Bearer abc"


def test_no_token_is_an_error() -> None:
    settings = IdentitySettings(app_env="production", allow_fake_auth=False, _env_file=None)  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option
    with pytest.raises(GraphError, match="no_token"):
        graph.mailer_for(_request(), settings)


def test_a_mail_failure_logs_its_kind_never_the_address_or_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Findings N1, as the directory's own test does."""
    caplog.set_level(logging.INFO, logger="cordware.graph")
    # Graph's error body echoes the address, so the log line must not
    # copy the reply into itself.
    echo = b'{"error": {"code": "ErrorAccessDenied", "message": "secret.person@example.edu"}}'
    secret = GraphMailer("secret-token-xyz", transport=Script(Response(403, {}, echo)))
    with pytest.raises(GraphError):
        secret.send_mail(MailMessage(to="secret.person@example.edu", subject="Hi", body="x"))
    (record,) = caplog.records
    assert record.__dict__["kind"] == "forbidden"
    text = record.getMessage() + repr(record.__dict__)
    assert "secret.person" not in text and "secret-token-xyz" not in text


def test_the_fake_mailer_logs_no_address_or_subject(caplog: pytest.LogCaptureFixture) -> None:
    """Findings N2."""
    caplog.set_level(logging.INFO, logger="cordware.graph")
    FakeMailer().send_mail(
        MailMessage(to="secret.person@example.edu", subject="Private subject", body="x")
    )
    (record,) = caplog.records
    text = record.getMessage() + repr(record.__dict__)
    assert "secret.person" not in text and "Private subject" not in text
    assert record.__dict__["recipients"] == 1


@pytest.mark.parametrize("code", [302, 303, 307])
def test_the_mailer_post_does_not_follow_a_redirect_with_the_token(code: int) -> None:
    """Findings N1, and the cold read: Python's stock handler already
    refuses a 307 for a POST, but follows a 302 or 303 as a GET with the
    headers, the bearer token included. The shared opener follows none."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from cordware.graph import urllib_post

    seen: list[str | None] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            if self.path == "/start":
                self.send_response(code)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            else:
                seen.append(self.headers.get("Authorization"))
                self.send_response(202)
                self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        reply = urllib_post(
            f"http://127.0.0.1:{server.server_port}/start",
            {"Authorization": "Bearer secret"},
            b"{}",
            5.0,
        )
    finally:
        server.shutdown()
    assert reply.status == code
    assert seen == []  # the redirect target was never asked


def test_a_request_mailer_refuses_a_long_throttle_at_once() -> None:
    """Findings N4 (author, 2026-11-06): a send on a request waits a short
    Retry-After, but past `REQUEST_MAX_WAIT` refuses as throttled without
    sleeping, so one click cannot hold the page for a minute."""
    sleeps: list[float] = []
    short = GraphMailer(
        "tok",
        transport=Script(Response(429, {"Retry-After": "3"}, b""), ACCEPTED),
        sleep=sleeps.append,
        max_wait=graph.REQUEST_MAX_WAIT,
    )
    short.send_mail(MESSAGE)
    assert sleeps == [3.0]
    sleeps.clear()
    long = GraphMailer(
        "tok",
        transport=Script(Response(429, {"Retry-After": "20"}, b"")),
        sleep=sleeps.append,
        max_wait=graph.REQUEST_MAX_WAIT,
    )
    with pytest.raises(GraphError, match="throttled"):
        long.send_mail(MESSAGE)
    assert sleeps == []


def test_the_request_mailer_uses_the_short_wait() -> None:
    mailer_built = graph.mailer_for(
        _request({graph.TOKEN_HEADER: "tok"}),
        IdentitySettings(app_env="production", allow_fake_auth=False, _env_file=None),  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option
    )
    assert isinstance(mailer_built, GraphMailer)
    assert mailer_built._max_wait == graph.REQUEST_MAX_WAIT  # pyright: ignore[reportPrivateUsage]  -- the setting under test
