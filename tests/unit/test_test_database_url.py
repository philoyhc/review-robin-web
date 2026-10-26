"""The suite never reads ``DATABASE_URL`` (findings H12, 2026-10-05).

On Postgres the ``engine`` fixture runs ``DROP SCHEMA public CASCADE``.
It used to fall back to ``DATABASE_URL`` when ``TEST_DATABASE_URL`` was
unset, so a bare ``pytest`` in a shell that had exported the app's own
database would wipe it. Only ``TEST_DATABASE_URL`` reaches the drop now;
``ci-postgres.yml`` sets it from its ``DATABASE_URL``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT_CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"


def _resolver():
    for module in list(sys.modules.values()):
        if getattr(module, "__file__", None) == str(ROOT_CONFTEST):
            return module._test_database_url, module.DEFAULT_TEST_DATABASE_URL
    raise AssertionError("tests/conftest.py is not loaded")


def test_an_exported_database_url_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve, default = _resolver()
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://app:pw@prod.example:5432/rrw"
    )
    assert resolve() == default


def test_test_database_url_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    resolve, _ = _resolver()
    url = "postgresql+psycopg://postgres:pw@localhost:5432/scratch"
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    assert resolve() == url


def test_ci_postgres_names_the_test_url() -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/ci-postgres.yml"
    ).read_text()
    assert "TEST_DATABASE_URL: ${{ env.DATABASE_URL }}" in workflow


def _conftest():
    for module in list(sys.modules.values()):
        if getattr(module, "__file__", None) == str(ROOT_CONFTEST):
            return module
    raise AssertionError("tests/conftest.py is not loaded")


PG = "postgresql+psycopg://rrw_app:rrw_app@localhost:5432/rrw"


def test_each_xdist_worker_gets_its_own_database() -> None:
    derive = _conftest()._worker_database_url
    assert derive(PG, "gw0") == "postgresql+psycopg://rrw_app:rrw_app@localhost:5432/rrw_gw0"
    assert derive(PG, "gw11").endswith("/rrw_gw11")


@pytest.mark.parametrize(
    ("url", "worker"),
    [(PG, None), (PG, ""), ("sqlite+pysqlite:///:memory:", "gw0")],
)
def test_a_serial_run_or_sqlite_keeps_the_named_database(url, worker) -> None:
    assert _conftest()._worker_database_url(url, worker) == url


@pytest.mark.parametrize("worker", ["master", "gw0; DROP", "../gw0"])
def test_an_unexpected_worker_id_is_refused(worker) -> None:
    with pytest.raises(RuntimeError, match="worker id"):
        _conftest()._worker_database_url(PG, worker)


def test_a_database_name_that_cannot_be_quoted_safely_is_refused() -> None:
    with pytest.raises(RuntimeError, match="cannot derive"):
        _conftest()._worker_database_url(
            'postgresql+psycopg://u:p@localhost/rrw"x', "gw0"
        )


def test_a_worker_database_past_postgres_identifier_limit_is_refused() -> None:
    derive = _conftest()._worker_database_url
    assert derive(f"postgresql+psycopg://u:p@localhost/{'d' * 59}", "gw0").endswith("_gw0")
    with pytest.raises(RuntimeError, match="identifier limit"):
        derive(f"postgresql+psycopg://u:p@localhost/{'d' * 60}", "gw0")


class _Connection:
    def __init__(self, exists: bool, error: Exception | None = None) -> None:
        self.exists, self.error, self.statements = exists, error, []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if sql.startswith("CREATE DATABASE") and self.error is not None:
            raise self.error

        class _Result:
            def scalar(_self):
                return 1 if self.exists else None

        return _Result()


def test_a_missing_worker_database_is_created_once() -> None:
    ensure = _conftest()._ensure_database
    missing = _Connection(exists=False)
    ensure(missing, "rrw_gw0")
    assert missing.statements[-1] == 'CREATE DATABASE "rrw_gw0"'
    present = _Connection(exists=True)
    ensure(present, "rrw_gw0")
    assert not any(s.startswith("CREATE") for s in present.statements)


def test_without_createdb_the_run_fails_naming_it() -> None:
    from sqlalchemy.exc import ProgrammingError

    denied = _Connection(exists=False, error=ProgrammingError("CREATE DATABASE", {}, Exception()))
    with pytest.raises(RuntimeError, match="CREATEDB"):
        _conftest()._ensure_database(denied, "rrw_gw0")
