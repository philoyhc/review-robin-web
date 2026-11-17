"""A long table's pages (segment AD1H): 200 rows at a time, as Review
Robin's rosters (`app/web/views/_pager.py`), reached by an offset in the
query string so a link keeps its place."""

from __future__ import annotations

from dataclasses import dataclass

PAGE_SIZE = 200


@dataclass(frozen=True)
class Page:
    """Where a table stands: the first row shown (0-based), how many in
    all, and the page size."""

    offset: int
    total: int
    size: int = PAGE_SIZE

    @property
    def end(self) -> int:
        return min(self.offset + self.size, self.total)

    @property
    def last(self) -> int:
        """The last page's offset (0 for an empty table)."""
        return ((self.total - 1) // self.size) * self.size if self.total else 0

    @property
    def ranges(self) -> tuple[tuple[int, str, bool], ...]:
        """Every page: its offset, its rows ("201–400"), and whether it
        is the one showing."""
        return tuple(
            (start, f"{start + 1:,}–{min(start + self.size, self.total):,}", start == self.offset)
            for start in range(0, self.total, self.size)
        )

    @property
    def previous(self) -> int | None:
        return self.offset - self.size if self.offset else None

    @property
    def following(self) -> int | None:
        return self.offset + self.size if self.offset + self.size < self.total else None


def page(total: int, offset: int, size: int = PAGE_SIZE) -> Page:
    """The page holding ``offset``: snapped to a page's start, one past
    the last clamped to the last, a negative one to the first."""
    start = max(0, offset) // size * size
    last = ((total - 1) // size) * size if total else 0
    return Page(min(start, last), total, size)
