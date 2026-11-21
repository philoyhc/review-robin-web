"""Apply Desk's own database (segment AD2A, rung 2): its Alembic history
runs up, down and up again, matches the models and keeps its own version
table; the factory still opens no database; and the localhost seed gives
each sample exercise its row and Owner, once, and only locally."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select

from applydesk import db, sample_data
from applydesk.models import Exercise, ExerciseOperator, Person
from applydesk.seed import SeedRefused, main, seed
from cordware.settings import identity_settings

ROOT = Path(__file__).resolve().parents[2]
TABLES = {"person", "exercise", "exercise_operator", "audit_event"}


def _config(url: str) -> Config:
    config = Config(str(ROOT / "applydesk" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_the_history_round_trips_and_matches_the_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'a.db'}"
    config = _config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)  # raises if the models and the history differ
    tables = set(inspect(create_engine(url)).get_table_names())
    assert tables == TABLES | {"applydesk_alembic_version"}


def test_another_application_s_tables_are_left_alone(tmp_path: Path) -> None:
    """CI's Postgres holds RRW's and Utilities' tables beside Apply Desk's:
    the history's check compares Apply Desk's own tables only, and never
    drops another's."""
    url = f"sqlite:///{tmp_path / 'shared.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
    config = _config(url)
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    assert "sessions" in inspect(create_engine(url)).get_table_names()


def test_a_percent_encoded_url_reaches_alembic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ConfigParser reads `%` as interpolation, so the URL from the setting
    is doubled on its way into Alembic's config (as Utilities')."""
    path = tmp_path / "p%40d.db"
    monkeypatch.setenv("APPLYDESK_DATABASE_URL", f"sqlite:///{path}")
    command.upgrade(Config(str(ROOT / "applydesk" / "alembic.ini")), "head")
    assert (tmp_path / "p@d.db").exists()


def test_the_url_comes_from_its_own_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLYDESK_DATABASE_URL", "sqlite:///./elsewhere.db")
    assert db.ApplyDeskSettings().database_url == "sqlite:///./elsewhere.db"
    monkeypatch.delenv("APPLYDESK_DATABASE_URL")
    monkeypatch.chdir(ROOT / "applydesk")  # no .env here
    assert db.ApplyDeskSettings().database_url == "sqlite:///./applydesk.db"


def test_the_factory_opens_no_database() -> None:
    from fastapi.testclient import TestClient

    from applydesk.tests._host import host_with

    db.engine.cache_clear()
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get("/applydesk/health").status_code == 200
    assert db.engine.cache_info().currsize == 0


@pytest.mark.usefixtures("applydesk_db")
def test_the_seed_gives_each_sample_exercise_its_owner_once() -> None:
    session = db.new_session()
    first = seed(session)
    second = seed(session)
    samples = sample_data.exercises()
    assert (first.exercises_added, first.grants_added) == (len(samples), len(samples))
    assert (second.exercises_added, second.grants_added) == (0, 0)
    owner = session.get(Person, first.owner_id)
    assert owner is not None and owner.may_operate
    # Bound as Cordware's fake identity is.
    assert (owner.tenant_id, owner.object_id) == (
        identity_settings.fake_auth_tenant_id,
        identity_settings.fake_auth_principal_id,
    )
    ids = set(session.scalars(select(Exercise.public_id)))
    assert ids == {s.public_id for s in samples}
    owners = session.scalar(
        select(func.count()).where(
            ExerciseOperator.person_id == owner.id, ExerciseOperator.is_owner.is_(True)
        )
    )
    assert owners == len(samples)
    session.close()


@pytest.mark.usefixtures("applydesk_db")
def test_the_seed_may_name_a_pending_owner(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--owner", "Someone@Example.EDU"]) == 0
    assert "seeded: " in capsys.readouterr().out
    session = db.new_session()
    owner = session.scalars(select(Person)).one()
    assert owner.object_id is None and owner.email_key == "someone@example.edu"
    assert owner.may_operate
    session.close()


@pytest.mark.usefixtures("applydesk_db")
def test_the_seed_is_refused_outside_local(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(identity_settings, "app_env", "production")
    session = db.new_session()
    with pytest.raises(SeedRefused):
        seed(session)
    session.close()
    assert main([]) == 2
    assert "refused" in capsys.readouterr().err
    session = db.new_session()
    assert session.scalar(select(func.count()).select_from(Exercise)) == 0
    session.close()


def test_the_seed_is_audited_and_binds_as_a_sign_in_would() -> None:
    """Cold read: the seed goes through `people` and `operators`, so its
    rows are audited and a pending Owner named by `--owner` is bound by the
    fake identity's later run, not duplicated."""
    from applydesk.models import AuditEvent

    session = db.new_session()
    seed(session, owner_email="Admin@Example.edu ")
    seed(session)  # the fake identity (admin@example.edu) signs in: bound, not a second person
    people = list(session.scalars(select(Person)))
    assert len(people) == 1 and people[0].bound and people[0].may_operate
    kinds = [e.event_type for e in session.scalars(select(AuditEvent).order_by(AuditEvent.id))]
    session.close()
    assert kinds[:2] == ["person.created", "person.admitted"]
    assert kinds.count("exercise.created") == len(sample_data.exercises())
    assert "person.bound" in kinds
