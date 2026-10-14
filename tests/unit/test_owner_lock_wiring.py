"""Every route that makes a session takes the owner-add lock first.

``sessions.create_session``, ``session_clone.clone_session`` and
``session_rehydrate.rehydrate_session`` (which calls ``create_session``)
each make the caller the new session's owner, and the lock that keeps a
concurrent revoke from leaving a non-operator owner lives in their
routes, not in them (``spec/permissions.md`` §4.2). Rehydrate was missed
once through exactly that indirection, so the hand-kept lists below are
held to what a scan of the services finds, one call deep, and each route
must check the lock on the same user as a top-level ``if not …: raise``
before the session is made, with no commit or rollback between.

What it can't see: a commit inside a service the route calls between
the gate and the make, and an owner row written through a relationship
collection rather than ``SessionOperator(...)`` or ``insert(...)``.
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


def _writes_owner_row(call: ast.Call) -> bool:
    if _name(call) == "SessionOperator":
        return True
    return _name(call) == "insert" and any(
        isinstance(a, ast.Name) and a.id == "SessionOperator" for a in call.args
    )


def test_only_the_known_services_write_owner_rows() -> None:
    writers = {
        where
        for where, function in _functions(SERVICES)
        if any(_writes_owner_row(c) for c in _calls(function))
    }
    assert writers == OWNER_WRITERS


def test_every_service_reaching_an_owner_write_is_accounted_for() -> None:
    """A service wrapping a writer would hide it from the route check
    below, as ``rehydrate_session`` once did. ``add_owner`` locks itself;
    ``rehydrate_session`` is in ``MAKES_AN_OWNER``; nothing wraps either."""
    reached = {"create_session", "clone_session", "_insert_owner", "rehydrate_session"}
    wrappers = {
        where
        for where, function in _functions(SERVICES)
        if function.name not in reached - {"rehydrate_session"}
        and any(_name(c) in reached for c in _calls(function))
    }
    assert wrappers == {
        "session_rehydrate.py::rehydrate_session",
        "session_owners.py::add_owner",
    }


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


def _owner_arg(call: ast.Call) -> str | None:
    """The name passed as the new session's owner (``user=``)."""
    for keyword in call.keywords:
        if keyword.arg == "user" and isinstance(keyword.value, ast.Name):
            return keyword.value.id
    return None


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
    locked = body[gates[-1]].test.operand.args[1]
    make = next(c for c in _calls(body[makes]) if _name(c) in MAKES_AN_OWNER)
    assert isinstance(locked, ast.Name) and locked.id == _owner_arg(make), (
        f"{where}: the lock is not on the session's owner"
    )
    between = body[gates[-1] + 1 : makes]
    assert not any(
        _name(c) in {"commit", "rollback"} for s in between for c in _calls(s)
    ), f"{where}: the lock is released before the session is made"
