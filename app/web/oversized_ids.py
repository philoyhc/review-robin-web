"""An id too large for an id column answers 404, not 500 (findings O6).

Neither database binds an id past ``MAX_SQL_INT``, the 32-bit ``Integer``
an id column holds: Postgres raises "integer out of range" and SQLite,
past 64 bits, ``OverflowError``, each a 500. This app-wide dependency
answers 404 before a route reaches the database: a path or query
parameter that names an id and is past the bound is a page that cannot
exist. A form-body id list and the audit log's ``cursor`` are refused the
same way: no page emits such a value, so only a hand-made request
carries one (findings 2026-10-22 P2).
``request.path_params`` holds the raw text (FastAPI converts it for the
route, not here), so all are read as digits. A value that isn't digits is
left to the route, which already refuses it as malformed.

The form body is read only on a route that declares ``Form`` / ``File``
parameters (findings 2026-10-22 P2). FastAPI parses that body before it
solves any dependency, and Starlette caches the ``FormData`` on the
request, so ``request.form()`` here hands back the parsed body rather
than reading it again. A route that declares no form body is never made
to read one. Of the handlers that read ``request.form()`` themselves, the
Observers ones parse their ids with ``parse_id``, which refuses one past
the bound; the Instruments display-field saves read theirs with ``int``
and only compare them in Python, never binding them in SQL.
"""

from __future__ import annotations

import typing

from fastapi import HTTPException, Request, params, status

from app.services.text import MAX_SQL_INT

# Parameters that carry a row id besides ``id``, ``*_id`` and ``*_ids``.
# Anything else (a session code, a search term) may legitimately be a long
# run of digits. ``cursor`` is the audit log's keyset position, a row id.
_ID_KEYS = frozenset({"sid", "editing", "saved", "selected", "focus", "cursor"})


def _is_id_key(key: str) -> bool:
    return (
        key == "id" or key.endswith("_id") or key.endswith("_ids") or key in _ID_KEYS
    )


def _too_large(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) > MAX_SQL_INT
    text = str(value).strip().lstrip("+-")
    if not (text.isascii() and text.isdigit()):
        return False
    # Compared by length first: ``int`` refuses a string past Python's
    # 4,300-digit limit with a ``ValueError``, which answered 500 (Codex
    # on #3236).
    digits = text.lstrip("0")
    if len(digits) != len(str(MAX_SQL_INT)):
        return len(digits) > len(str(MAX_SQL_INT))
    return int(digits) > MAX_SQL_INT


def _declares_form_body(request: Request) -> bool:
    """Whether the matched route takes a form body — FastAPI's own test
    for parsing one with ``request.form()`` before the dependencies."""
    body_field = getattr(request.scope.get("route"), "body_field", None)
    return body_field is not None and isinstance(body_field.field_info, params.Form)


def _is_text(annotation: object) -> bool:
    """Whether a declared parameter type is ``str`` (or ``str | None``)."""
    if annotation is str:
        return True
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    return bool(args) and all(a is str for a in args)


def _text_params(request: Request) -> set[str]:
    """The path and query parameters the matched route, or a dependency
    of it, declares as text. A session's ``session_id`` is its public id,
    ten characters that may all be digits (``2222222222``), so a text
    parameter is never read as a row id (Codex on #3236)."""
    stack = [getattr(request.scope.get("route"), "dependant", None)]
    names: set[str] = set()
    while stack:
        dependant = stack.pop()
        if dependant is None:
            continue
        for field in (*dependant.path_params, *dependant.query_params):
            if _is_text(field.field_info.annotation):
                names.add(field.name)
        stack.extend(dependant.dependencies)
    return names


async def refuse_oversized_ids(request: Request) -> None:
    """404 when a path, id query or id form-body value is past ``MAX_SQL_INT``."""
    text = _text_params(request)
    fields = [
        (key, value)
        for key, value in (
            *request.path_params.items(),
            *request.query_params.multi_items(),
        )
        if key not in text
    ]
    if _declares_form_body(request):
        form = await request.form()  # the cached FormData, not a second read
        fields += [(k, v) for k, v in form.multi_items() if isinstance(v, str)]
    if any(_is_id_key(key) and _too_large(value) for key, value in fields):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
