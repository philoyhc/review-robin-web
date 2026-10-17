"""An id too large for a 64-bit column answers 404, not 500 (findings O6).

SQLite refuses to bind an integer past ``MAX_SQL_INT`` and raises
``OverflowError``, a 500; Postgres compares it and finds no row, a 404.
This app-wide dependency gives both databases the Postgres answer before a
route reaches the database: a path or query parameter that names an id and
is past the bound is a page that cannot exist. ``request.path_params``
holds the raw text (FastAPI converts it for the route, not here), so both
are read as digits. A value that isn't digits is left to the route, which
already refuses it as malformed.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.text import MAX_SQL_INT

# Parameters that carry a row id besides ``id`` and ``*_id``. Anything else
# (a session code, a search term) may legitimately be a long run of digits.
_ID_KEYS = frozenset({"sid", "editing", "saved", "selected", "focus"})


def _is_id_key(key: str) -> bool:
    return key == "id" or key.endswith("_id") or key in _ID_KEYS


def _too_large(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) > MAX_SQL_INT
    text = str(value).strip().lstrip("+-")
    return text.isascii() and text.isdigit() and int(text) > MAX_SQL_INT


def refuse_oversized_ids(request: Request) -> None:
    """404 when a path or id query parameter is past ``MAX_SQL_INT``."""
    params = [*request.path_params.items(), *request.query_params.multi_items()]
    if any(_is_id_key(key) and _too_large(value) for key, value in params):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
