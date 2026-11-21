"""Public IDs: the 10-character handles in ApplyDesk's URLs (ruling 7,
`applydesk/guide/todo_master.md`).

RRW's alphabet and length (`app/db/models/review_session.py`), copied
rather than imported: the convention is shared, the code is not
(`applydesk/spec/architecture.md`, "Import boundaries"). Lowercase letters
and digits without the look-alikes (0/o, 1/l/i), drawn at random, so an ID
carries no count and is not guessable by walking."""

from __future__ import annotations

import re
import secrets
from typing import Annotated

from fastapi import Path

PUBLIC_ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
PUBLIC_ID_LENGTH = 10
_SHAPE = re.compile(f"[{PUBLIC_ID_ALPHABET}]{{{PUBLIC_ID_LENGTH}}}")


def generate_public_id() -> str:
    """A fresh random public ID."""
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))


def is_public_id(value: str) -> bool:
    """Whether ``value`` has a public ID's shape. A route refuses any
    other shape with a 404 before looking anything up."""
    return bool(_SHAPE.fullmatch(value))


#: A database row ID in a form or a path: positive and within a 32-bit
#: integer, so a value no column holds is refused before any lookup
#: (bug sweep at the AD2A close: ``"²".isdigit()`` is true, and SQLite
#: overflows on a 30-digit one).
ROW_ID_MAX = 2**31 - 1
_ROW_ID = re.compile(r"[1-9][0-9]{0,9}")


def row_id(raw: str) -> int | None:
    """``raw`` as a row ID, or None."""
    if not _ROW_ID.fullmatch(raw):
        return None
    value = int(raw)
    return value if value <= ROW_ID_MAX else None


#: A person's row ID in a route's path: out of range is a 422, not a 500.
RowId = Annotated[int, Path(ge=1, le=ROW_ID_MAX)]
