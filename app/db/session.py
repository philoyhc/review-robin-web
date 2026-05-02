from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _enable_sqlite_fk_enforcement(engine: Engine) -> None:
    """SQLite ships with foreign-key enforcement off by default, so
    ``ON DELETE CASCADE`` declarations silently no-op. Production runs
    on Postgres (where FKs are always enforced); turn the pragma on
    for SQLite so dev + test environments behave the same way."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        settings.database_url, connect_args=connect_args, future=True
    )
    if settings.database_url.startswith("sqlite"):
        _enable_sqlite_fk_enforcement(engine)
    return engine


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
