"""Fast SQLite schema build for the test suite.

The migration chain is replayed only on the ``ci-postgres`` job; the
SQLite test path builds its schema directly from the ORM metadata
(``Base.metadata.create_all``). Wave 5 PR 5.2 retired the seeded
RuleSet install — no data-only seed step runs anymore.
"""

from __future__ import annotations

from sqlalchemy import Engine


def build_sqlite_schema(eng: Engine) -> None:
    """Build the full schema on a SQLite engine directly from ORM metadata.

    Importing ``app.db.models`` registers every mapped class on
    ``Base.metadata``; ``create_all`` then builds the schema in one pass,
    skipping the migration replay.
    """
    from app.db.base import Base
    import app.db.models  # noqa: F401  -- registers all tables on Base.metadata

    Base.metadata.create_all(eng)
