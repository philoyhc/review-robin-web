"""Utilities' own database, `utilityapps` (segment U4, rung 2).

Its URL is `UTILITYAPPS_DATABASE_URL`: on the App Service a Key Vault
reference (Cordware's `app-settings-database-urls.yml`), locally a SQLite
file. The engine is made on first use, so the factory still opens no
database and `/health` needs none. Models are declared on `Base`, which
is Utilities' alone (`utilityapps/spec/architecture` boundaries: no RRW
or Residential model is imported)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class UtilityAppsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="sqlite:///./utilityapps.db",
        validation_alias="UTILITYAPPS_DATABASE_URL",
    )


class Base(DeclarativeBase):
    """Every Utilities table."""


@cache
def engine() -> Engine:
    url = UtilityAppsSettings().database_url
    options: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options = {"connect_args": {"check_same_thread": False}}
    return create_engine(url, **options)


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
