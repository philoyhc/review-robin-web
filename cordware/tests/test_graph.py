"""The host's Graph helper (`cordware/graph.py`; Utilities segment U1,
rung 4): the query it sends, what it does with each answer, the fake
directory, and which directory a request gets. No test touches the
network: `GraphDirectory` takes its transport as a parameter."""

from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.requests import Request

from cordware import graph
from cordware.graph import DirectoryUser, FakeDirectory, GraphDirectory, GraphError, Response
from cordware.settings import IdentitySettings

JANE = {"id": "u1", "displayName": "Jane Tan", "mail": "jane.tan@example.edu", "userPrincipalName": "e0123456@example.edu"}


class Script:
    """A transport answering from a list, recording each request."""

    def __init__(self, *replies: Response | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def __call__(self, url: str, headers, timeout: float) -> Response:
        self.calls.append((url, dict(headers), timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def ok(*users: dict) -> Response:
    return Response(200, {}, json.dumps({"value": list(users)}).encode())


def directory(script: Script, sleeps: list[float] | None = None) -> GraphDirectory:
    return GraphDirectory("tok", transport=script, sleep=(sleeps if sleeps is not None else []).append)


def test_one_query_matches_mail_or_upn_with_the_token() -> None:
    script = Script(ok(JANE))
    users = directory(script).find_users("o'brien@example.edu")
    assert users == [DirectoryUser("u1", "Jane Tan", "jane.tan@example.edu", "e0123456@example.edu")]
    url, headers, timeout = script.calls[0]
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://graph.microsoft.com/v1.0/users"
    query = parse_qs(parts.query)
    assert query["$filter"] == ["mail eq 'o''brien@example.edu' or userPrincipalName eq 'o''brien@example.edu'"]
    assert query["$select"] == ["id,displayName,mail,userPrincipalName"]
    assert query["$top"] == ["5"]
    assert headers["Authorization"] == "Bearer tok"
    assert timeout == 10.0


def test_no_match_is_an_empty_list_and_a_null_mail_is_none() -> None:
    assert directory(Script(ok())).find_users("x@example.edu") == []
    lab = {"id": "u3", "displayName": "Lab", "mail": None, "userPrincipalName": "lab01@example.edu"}
    assert directory(Script(ok(lab))).find_users("lab01@example.edu")[0].mail is None


@pytest.mark.parametrize(("status", "kind"), [(401, "unauthorized"), (403, "forbidden"), (400, "bad_response")])
def test_a_refusal_is_raised_at_once(status: int, kind: str) -> None:
    script = Script(Response(status, {}, b"{}"))
    with pytest.raises(GraphError) as caught:
        directory(script).find_users("a@example.edu")
    assert caught.value.kind == kind and caught.value.status == status
    assert len(script.calls) == 1


def test_throttling_waits_its_retry_after_then_succeeds() -> None:
    sleeps: list[float] = []
    script = Script(Response(429, {"Retry-After": "3"}, b""), ok(JANE))
    assert directory(script, sleeps).find_users("a@example.edu")[0].id == "u1"
    assert sleeps == [3.0]


def test_throttling_past_the_longest_wait_is_raised_without_waiting() -> None:
    sleeps: list[float] = []
    script = Script(Response(429, {"retry-after": "120"}, b""))
    with pytest.raises(GraphError, match="throttled"):
        directory(script, sleeps).find_users("a@example.edu")
    assert sleeps == []


@pytest.mark.parametrize(
    ("failure", "kind"), [(Response(503, {}, b""), "server"), (OSError("reset"), "network")]
)
def test_server_and_network_failures_back_off_then_give_up(failure, kind: str) -> None:
    sleeps: list[float] = []
    script = Script(failure, failure, failure)
    with pytest.raises(GraphError) as caught:
        directory(script, sleeps).find_users("a@example.edu")
    assert caught.value.kind == kind
    assert sleeps == [1.0, 2.0] and len(script.calls) == 3


def test_a_transient_failure_then_success_returns_the_users() -> None:
    script = Script(OSError("reset"), ok(JANE))
    assert len(directory(script).find_users("a@example.edu")) == 1


@pytest.mark.parametrize("body", [b"not json", b"{}", b'{"value": [{"displayName": "no id"}]}'])
def test_an_unreadable_answer_is_bad_response(body: bytes) -> None:
    with pytest.raises(GraphError, match="bad_response"):
        directory(Script(Response(200, {}, body))).find_users("a@example.edu")


def test_a_failure_logs_its_kind_never_the_address_or_token(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="cordware.graph")
    with pytest.raises(GraphError):
        directory(Script(Response(403, {}, b""))).find_users("secret.person@example.edu")
    (record,) = caplog.records
    assert record.event == "graph.request_failed" and record.kind == "forbidden" and record.status == 403
    text = record.getMessage() + repr(record.__dict__)
    assert "secret.person" not in text and "tok" not in text.replace("token", "")


def test_the_fake_directory_matches_mail_or_upn_in_any_case() -> None:
    fake = FakeDirectory()
    assert [u.display_name for u in fake.find_users("JANE.TAN@example.edu")] == ["Jane Tan"]
    assert [u.display_name for u in fake.find_users("e0123456@example.edu")] == ["Jane Tan"]
    assert fake.find_users("lab01@example.edu")[0].mail is None
    # One address that is one user's mail and another's UPN: two users.
    assert {u.display_name for u in fake.find_users("office@example.edu")} == {"Wei Ling Lim", "Office Desk"}
    assert fake.find_users("nobody@example.edu") == []


@pytest.mark.parametrize(("address", "kind"), sorted(graph.FAKE_FAILURES.items()))
def test_the_fake_directory_fails_on_its_failure_addresses(address: str, kind: str) -> None:
    with pytest.raises(GraphError) as caught:
        FakeDirectory().find_users(address)
    assert caught.value.kind == kind


def test_the_fake_directory_is_invented_accounts_only() -> None:
    for user in graph.FAKE_USERS:
        for address in (user.mail, user.user_principal_name):
            assert address is None or address.endswith("@example.edu")


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw})


def test_fake_auth_on_a_local_run_gets_the_fake_directory() -> None:
    settings = IdentitySettings(app_env="local", allow_fake_auth=True, _env_file=None)
    assert isinstance(graph.directory_for(_request(), settings), FakeDirectory)


def test_otherwise_the_request_token_is_used() -> None:
    settings = IdentitySettings(app_env="production", allow_fake_auth=False, _env_file=None)
    found = graph.directory_for(_request({graph.TOKEN_HEADER: "abc"}), settings)
    assert isinstance(found, GraphDirectory)
    assert found._headers["Authorization"] == "Bearer abc"


@pytest.mark.parametrize("token", [None, "", "   "])
def test_no_token_is_an_error_not_an_empty_directory(token: str | None) -> None:
    settings = IdentitySettings(app_env="local", allow_fake_auth=False, _env_file=None)
    headers = {} if token is None else {graph.TOKEN_HEADER: token}
    with pytest.raises(GraphError, match="no_token"):
        graph.directory_for(_request(headers), settings)
