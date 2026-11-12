"""Utilities' own database (segment U4, rung 2): its Alembic history runs
up, down and up again, matches the models, keeps its own version table,
and the factory still opens no database."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from utilityapps import db

ROOT = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    config = Config(str(ROOT / "utilityapps" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_the_history_round_trips_and_matches_the_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'u.db'}"
    config = _config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)  # raises if the models and the history differ
    tables = set(inspect(create_engine(url)).get_table_names())
    assert tables == {"photo_poc_photos", "utilityapps_alembic_version"}


def test_another_application_s_tables_are_left_alone(tmp_path: Path) -> None:
    """CI's Postgres holds RRW's tables beside Utilities': the history's
    check compares Utilities' own tables only, and never drops another's."""
    url = f"sqlite:///{tmp_path / 'shared.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
    config = _config(url)
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    assert "sessions" in inspect(create_engine(url)).get_table_names()


def test_the_url_comes_from_its_own_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITYAPPS_DATABASE_URL", "sqlite:///./elsewhere.db")
    assert db.UtilityAppsSettings().database_url == "sqlite:///./elsewhere.db"
    monkeypatch.delenv("UTILITYAPPS_DATABASE_URL")
    monkeypatch.chdir(ROOT / "utilityapps")  # no .env here
    assert db.UtilityAppsSettings().database_url == "sqlite:///./utilityapps.db"


def test_the_factory_opens_no_database() -> None:
    from fastapi.testclient import TestClient

    from utilityapps.tests._host import host_with

    db.engine.cache_clear()
    client = TestClient(host_with(("utilities",))[0])
    assert client.get("/utilities/health").status_code == 200
    assert db.engine.cache_info().currsize == 0
