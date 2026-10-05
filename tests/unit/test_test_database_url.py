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
