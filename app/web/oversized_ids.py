"""An id too large for a 64-bit column answers 404, not 500 (findings O6).

SQLite refuses to bind an integer past ``MAX_SQL_INT`` and raises
``OverflowError``, a 500; Postgres compares it and finds no row, a 404.
This app-wide dependency gives both databases the Postgres answer before a
route reaches the database: a path or query parameter, or a form-body
field, that names an id and is past the bound is a page that cannot exist.
``request.path_params`` holds the raw text (FastAPI converts it for the
route, not here), so all are read as digits. A value that isn't digits is
left to the route, which already refuses it as malformed.

The form body is read only on a route that declares ``Form`` / ``File``
parameters (findings 2026-10-22 P2). FastAPI parses that body before it
solves any dependency, and Starlette caches the ``FormData`` on the
request, so ``request.form()`` here hands back the parsed body rather
than reading it again. A route that declares no form body is never made
to read one; the handlers that read ``request.form()`` themselves parse
their ids with ``parse_id``, which already refuses one past the bound.
"""

from __future__ import annotations

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
    return text.isascii() and text.isdigit() and int(text) > MAX_SQL_INT


def _declares_form_body(request: Request) -> bool:
    """Whether the matched route takes a form body — FastAPI's own test
    for parsing one with ``request.form()`` before the dependencies."""
    body_field = getattr(request.scope.get("route"), "body_field", None)
    return body_field is not None and isinstance(body_field.field_info, params.Form)


async def refuse_oversized_ids(request: Request) -> None:
    """404 when a path, id query or id form-body value is past ``MAX_SQL_INT``."""
    fields = [*request.path_params.items(), *request.query_params.multi_items()]
    if _declares_form_body(request):
        form = await request.form()  # the cached FormData, not a second read
        fields += [(k, v) for k, v in form.multi_items() if isinstance(v, str)]
    if any(_is_id_key(key) and _too_large(value) for key, value in fields):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
