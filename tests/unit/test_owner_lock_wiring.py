"""Every route that makes a session takes the owner-add lock first.

``sessions.create_session``, ``session_clone.clone_session`` and
``session_rehydrate.rehydrate_session`` (which calls ``create_session``)
each make the caller the new session's owner, and the lock that keeps a
concurrent revoke from leaving a non-operator owner lives in their
routes, not in them (``spec/permissions.md`` §4.2). Rehydrate was missed
once for exactly that indirection, so the list is derived from the
services here rather than trusted, and each route must check the lock as
a top-level ``if not …: raise`` that runs before the session is made,
with no commit between to release it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
SERVICES = APP / "services"
WEB = APP / "web"

# The services that write an owner row, and how. ``_insert_owner`` sits
# behind ``add_owner``, which takes the lock itself.
OWNER_WRITERS = {
    "sessions.py::create_session",
    "session_clone.py::clone_session",
    "session_owners.py::_insert_owner",
}
# What a route can call that ends in an owner row it doesn't lock itself.
MAKES_AN_OWNER = {"create_session", "clone_session", "rehydrate_session"}


def _calls(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def _name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _functions(root: Path):
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield f"{path.relative_to(root)}::{node.name}", node


def test_only_the_known_services_write_owner_rows() -> None:
    writers = {
        where
        for where, function in _functions(SERVICES)
        if any(_name(c) == "SessionOperator" for c in _calls(function))
    }
    assert writers == OWNER_WRITERS


def test_only_rehydrate_reaches_an_owner_write_through_another_service() -> None:
    """A service wrapping one of the writers would hide it from the route
    check below, as ``rehydrate_session`` once did; it must be listed."""
    writers = {"create_session", "clone_session"}
    wrappers = {
        where
        for where, function in _functions(SERVICES)
        if function.name not in writers
        and any(_name(c) in writers for c in _calls(function))
    }
    assert wrappers == {"session_rehydrate.py::rehydrate_session"}


def _route_callers():
    return [
        (where, function)
        for where, function in _functions(WEB)
        if any(_name(c) in MAKES_AN_OWNER for c in _calls(function))
    ]


def test_the_three_routes_are_found() -> None:
    """Guards the guard: a rename that hid a caller would pass below."""
    assert len(_route_callers()) == 3


def _is_lock_gate(statement: ast.stmt) -> bool:
    """``if not session_owners.lock_owner_eligible(db, user): raise …``."""
    return (
        isinstance(statement, ast.If)
        and isinstance(statement.test, ast.UnaryOp)
        and isinstance(statement.test.op, ast.Not)
        and isinstance(statement.test.operand, ast.Call)
        and _name(statement.test.operand) == "lock_owner_eligible"
        and any(isinstance(s, ast.Raise) for s in statement.body)
    )


@pytest.mark.parametrize(
    "where, function", _route_callers(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_the_lock_gates_the_route_before_the_session_is_made(
    where: str, function
) -> None:
    body = function.body
    makes = next(
        i for i, s in enumerate(body) if any(_name(c) in MAKES_AN_OWNER for c in _calls(s))
    )
    gates = [i for i, s in enumerate(body[:makes]) if _is_lock_gate(s)]
    assert gates, f"{where}: no top-level lock gate before the session is made"
    between = body[gates[-1] + 1 : makes]
    assert not any(
        _name(c) == "commit" for s in between for c in _calls(s)
    ), f"{where}: a commit releases the lock before the session is made"
