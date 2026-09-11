"""The collation guard on the Assignments sort — Segment 19J.5 rung 4.

``tests/integration/test_pair_sort_sql.py`` proves the ordering itself,
but only against whatever collation the database under test happens to
carry. Measured 2026-09-11: an Ubuntu-packaged Postgres 16 initialises
as ``C.UTF-8``, where the ordering is right **with or without** the
explicit collation — so on such a server those tests pass even if the
guard is deleted. I could not determine the ``ci-postgres`` container's
locale from the sandbox, and would rather not depend on it.

So this file asserts the guard is *emitted*, by compiling against the
Postgres dialect rather than by running anything. It holds whatever
locale the server has, which is the property the integration tests
cannot offer.

The pairing is deliberate: the integration tests say the order is
right, and this one says the reason it is right has not been removed.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import String, column
from sqlalchemy.dialects import postgresql, sqlite

from app.services.assignments._coverage import _code_point


@dataclass
class _FakeDialect:
    name: str


@dataclass
class _FakeBind:
    dialect: _FakeDialect


class _FakeSession:
    """Just enough Session for ``_code_point``: it asks the bind for its
    dialect name and nothing else."""

    def __init__(self, dialect_name: str) -> None:
        self._bind = _FakeBind(_FakeDialect(dialect_name))

    def get_bind(self):
        return self._bind


def _compiled(expression, dialect) -> str:
    return str(expression.compile(dialect=dialect))


def test_postgres_gets_an_explicit_c_collation() -> None:
    """Without this the ordering follows the database's own collation,
    which on a locale-aware one is *not* the order this app has always
    rendered — measured, and recorded in the module the guard lives
    in."""
    expression = _code_point(_FakeSession("postgresql"), column("name", String))
    assert 'COLLATE "C"' in _compiled(expression, postgresql.dialect())


def test_sqlite_is_left_alone() -> None:
    """Its default collation is BINARY, which already is code-point
    order — and ``COLLATE "C"`` is not a collation SQLite has."""
    expression = _code_point(_FakeSession("sqlite"), column("name", String))
    assert "COLLATE" not in _compiled(expression, sqlite.dialect()).upper()


def test_the_guard_is_keyed_on_the_dialect_not_the_server() -> None:
    """A server-locale check would be the obvious alternative and the
    wrong one: the same code must emit the same SQL wherever it runs,
    or the ordering becomes a property of the deployment."""
    pg = _code_point(_FakeSession("postgresql"), column("name", String))
    lite = _code_point(_FakeSession("sqlite"), column("name", String))
    assert _compiled(pg, postgresql.dialect()) != _compiled(
        lite, sqlite.dialect()
    )
