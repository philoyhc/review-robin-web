"""Small text helpers shared across services and view adapters."""

from __future__ import annotations


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """Return the count-agreed noun: ``singular`` when ``count == 1``,
    else ``plural`` (defaulting to ``singular + "s"``).

    One home for the ``f"{n} response{'' if n == 1 else 's'}"`` /
    ``"draft" if n == 1 else "drafts"`` idioms that were reinvented
    inline across the codebase (audit V6). Returns just the noun, so
    callers write ``f"{n} {pluralize(n, 'response')}"``.
    """
    if count == 1:
        return singular
    return plural if plural is not None else singular + "s"


#: The largest id a 64-bit integer column holds. SQLite refuses to bind
#: anything above it (``OverflowError``) where Postgres merely compares, so
#: a longer id is treated as one no row can have (findings O6, R8).
MAX_SQL_INT = 2**63 - 1


def parse_id(raw: object) -> int | None:
    """A row id typed as text, or None when ``raw`` is not one.

    ASCII digits only: ``str.isdigit`` accepts ``"²"``, which ``int``
    refuses (findings P4), and ``int`` accepts full-width digits a
    browser never sends. An id past :data:`MAX_SQL_INT` is None too.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if 0 <= raw <= MAX_SQL_INT else None
    text = str(raw or "").strip()
    if not (text.isascii() and text.isdigit()):
        return None
    value = int(text)
    return value if value <= MAX_SQL_INT else None
