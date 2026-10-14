"""Every route that makes a session takes the owner-add lock first.

``sessions.create_session``, ``session_clone.clone_session`` and
``session_rehydrate.rehydrate_session`` each make the caller the new
session's owner, and the lock that keeps a concurrent revoke from leaving
a non-operator owner lives in their routes, not in them
(``spec/permissions.md`` §4.2). A new caller that forgot it would reopen
the race silently, so this reads every route module for them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "app" / "web"
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


def _callers() -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    found = []
    for path in sorted(WEB.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                _name(c) in MAKES_AN_OWNER for c in _calls(node)
            ):
                found.append((f"{path.relative_to(WEB)}::{node.name}", node))
    return found


def test_the_three_routes_are_found() -> None:
    """Guards the guard: a rename that hid every caller would pass below."""
    assert len(_callers()) == 3


@pytest.mark.parametrize("where, function", _callers(), ids=lambda v: v if isinstance(v, str) else "")
def test_the_lock_comes_before_the_session_is_made(where: str, function) -> None:
    calls = _calls(function)
    makes = min(c.lineno for c in calls if _name(c) in MAKES_AN_OWNER)
    locks = [c.lineno for c in calls if _name(c) == "lock_owner_eligible"]
    assert locks and min(locks) < makes, where
