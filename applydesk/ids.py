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
