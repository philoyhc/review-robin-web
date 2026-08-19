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
