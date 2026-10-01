"""Browser tests: the app served live, driven by a real Chromium.

Plan: ``guide/browser_test.md``. A session-scoped server runs
``uvicorn app.main:app`` against a freshly migrated SQLite file with fake
auth, so a Save reaches the server and a reload proves it persisted. Tests
seed through the app's own routes over HTTP and make their own session, so
they share the server but not data.

Without a Chromium build the tests skip, saying why (``playwright`` itself
is a dev dependency, so its absence is an import error, not a skip).
``RRW_REQUIRE_BROWSER=1`` (set in ``.github/workflows/ci.yml``) turns that
skip into a failure, so CI cannot pass by not running them.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from playwright.sync_api import Browser, Error, Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRE_BROWSER = os.environ.get("RRW_REQUIRE_BROWSER") == "1"
SERVER_START_TIMEOUT_S = 30.0


def _unavailable(reason: str) -> None:
    if REQUIRE_BROWSER:
        pytest.fail(f"{reason}, and RRW_REQUIRE_BROWSER=1", pytrace=False)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch()
        except Error as exc:
            _unavailable(f"Chromium could not launch: {exc.message.splitlines()[0]}")
        yield launched
        launched.close()


@dataclass(frozen=True)
class LiveServer:
    base_url: str
    # The server's own SQLite file, for fixture-time setup the UI has no
    # short route to (pinning a rule set, as tests/integration does).
    database_url: str


def _bound_socket() -> socket.socket:
    """A listening socket the server inherits, so no other xdist worker's
    server can take the port between choosing it and binding it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    sock.set_inheritable(True)
    return sock


@pytest.fixture(scope="session")
def live_server(
    browser: Browser, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[LiveServer]:
    # Depends on ``browser`` so a missing browser skips before a server starts.
    workdir = tmp_path_factory.mktemp("live_server")
    database_url = f"sqlite:///{workdir / 'browser.db'}"
    # The server inherits the test environment on purpose: the root
    # conftest's AUDIT_STRICT_MODE (and REHYDRATE_ENABLED) reach it, as they
    # reach the in-process suite. The fake-auth keys are pinned here because
    # app settings also read a developer's .env, which must not decide who
    # the tests sign in as.
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "ALLOW_FAKE_AUTH": "true",
        "FAKE_AUTH_OPERATOR": "true",
    }
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if migrated.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed:\n{migrated.stderr}")
    sock = _bound_socket()
    base_url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    log_path = workdir / "server.log"
    with sock, log_path.open("wb") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--fd", str(sock.fileno())],
            cwd=REPO_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            pass_fds=(sock.fileno(),),
        )
        try:
            _wait_for_health(base_url, server, log_path)
            yield LiveServer(base_url=base_url, database_url=database_url)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def _wait_for_health(base_url: str, server: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + SERVER_START_TIMEOUT_S
    while time.monotonic() < deadline:
        if server.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1):
                return
        except OSError:
            # Refused, reset, or (the socket listens before uvicorn starts
            # accepting) a read that timed out in the queue: try again.
            time.sleep(0.1)
    raise RuntimeError(
        f"live server did not answer /health; its log:\n{log_path.read_text()}"
    )


@pytest.fixture
def api(live_server: LiveServer) -> Iterator[httpx.Client]:
    """An HTTP client on the live server, signed in as the fake operator."""
    with httpx.Client(base_url=live_server.base_url) as client:
        yield client


@pytest.fixture
def new_session(api: httpx.Client) -> Callable[[], int]:
    """Create a session through ``POST /operator/sessions``; return its id."""

    def make() -> int:
        code = f"b{uuid.uuid4().hex[:8]}"
        response = api.post(
            "/operator/sessions",
            data={"name": f"Browser {code}", "code": code},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        # Location: /operator/sessions/<id>?editing=1#session-config
        return int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])

    return make


@pytest.fixture
def page_as(browser: Browser, live_server: LiveServer) -> Iterator[Callable[..., Page]]:
    """Open fresh pages, as the fake operator or as a named person.

    A person signs in through the Easy Auth headers, which
    ``app/auth/identity.py`` reads before falling back to fake auth. An
    uncaught page error on any page fails the test.
    """
    contexts = []
    errors: list[str] = []

    def open_page(email: str | None = None) -> Page:
        headers = {}
        if email is not None:
            headers = {
                "X-MS-CLIENT-PRINCIPAL-NAME": email,
                "X-MS-CLIENT-PRINCIPAL-ID": f"browser-{email}",
                "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
            }
        context = browser.new_context(
            base_url=live_server.base_url,
            viewport={"width": 1500, "height": 1000},
            extra_http_headers=headers,
        )
        contexts.append(context)
        opened = context.new_page()
        opened.on("pageerror", lambda exc: errors.append(str(exc)))
        return opened

    yield open_page
    for context in contexts:
        context.close()
    assert not errors, f"uncaught page errors: {errors}"


@pytest.fixture
def page(page_as: Callable[..., Page]) -> Page:
    """A fresh page signed in as the fake operator."""
    return page_as()
