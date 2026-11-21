"""Apply Desk's own database, `applydesk` (segment AD2A, rung 2).

Its URL is `APPLYDESK_DATABASE_URL`: on the App Service a Key Vault
reference (Cordware's `app-settings-database-urls.yml`), locally a SQLite
file that `alembic -c applydesk/alembic.ini upgrade head` builds and
`python -m applydesk.seed` fills, so the database can be checked on
localhost (ruling 74). The engine is made on first use, so the factory
still opens no database and `/health` needs none. Models are declared on
`Base`, which is Apply Desk's alone (`applydesk/spec/architecture.md`,
"Import boundaries": no other application's model is imported)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class ApplyDeskSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="sqlite:///./applydesk.db",
        validation_alias="APPLYDESK_DATABASE_URL",
    )


class Base(DeclarativeBase):
    """Every Apply Desk table."""


@cache
def engine() -> Engine:
    url = ApplyDeskSettings().database_url
    options: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options = {"connect_args": {"check_same_thread": False}}
    made = create_engine(url, **options)
    if url.startswith("sqlite"):
        _real_sqlite_transactions(made)
    return made


def _real_sqlite_transactions(made: Engine) -> None:
    """SQLAlchemy's recipe for SQLite ("Serializable isolation /
    Savepoints / Transactional DDL"): Python's driver begins a transaction
    only before a write, so a savepoint opened after reads had no
    transaction round it, and releasing it committed (Codex on #4110).
    The driver's own handling is turned off and the engine says `BEGIN`
    when its transaction starts, as Postgres does."""

    @event.listens_for(made, "connect")
    def _no_driver_transactions(  # pyright: ignore[reportUnusedFunction]  -- an event hook
        dbapi_connection: Any, _record: object
    ) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(made, "begin")
    def _begin(conn: Connection) -> None:  # pyright: ignore[reportUnusedFunction]  -- an event hook
        conn.exec_driver_sql("BEGIN")


@cache
def _sessions() -> sessionmaker[Session]:
    return sessionmaker(bind=engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """A request's session, closed afterwards: a FastAPI dependency."""
    session = _sessions()()
    try:
        yield session
    finally:
        session.close()


def new_session() -> Session:
    """A session outside a request (the seed, scripts), closed by its caller."""
    return _sessions()()
