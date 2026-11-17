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


#: The columns a gate's table sorts by (segment AD1H, author 2026-11-17),
#: as Review Robin's rosters: a cascade of up to three, each up or down.
SORT_KEYS: tuple[str, ...] = ("candidate", "evaluator", "source", "state")
SORT_MAX = 3

Sort = tuple[tuple[str, bool], ...]  # (key, descending), in cascade order


def parse_sort(raw: str) -> Sort:
    """``?sort=candidate,-state`` as a cascade: known keys only, each
    once, three at most; anything else is dropped."""
    out: list[tuple[str, bool]] = []
    for part in raw.split(","):
        part = part.strip()
        desc = part.startswith("-")
        key = part.removeprefix("-")
        if key in SORT_KEYS and key not in (k for k, _ in out) and len(out) < SORT_MAX:
            out.append((key, desc))
    return tuple(out)


def sort_text(spec: Sort) -> str:
    return ",".join(("-" if desc else "") + key for key, desc in spec)


def plain_click(spec: Sort, key: str) -> Sort:
    """As Review Robin's header click: the sole sorted column cycles up,
    down, unsorted; any other click sorts by that column alone, up."""
    if len(spec) == 1 and spec[0][0] == key:
        return () if spec[0][1] else ((key, True),)
    return ((key, False),)


def shift_click(spec: Sort, key: str) -> Sort:
    """As Review Robin's shift-click: an unsorted column joins the cascade
    up (three at most); a sorted one goes down, then drops out."""
    keys = [k for k, _ in spec]
    if key not in keys:
        return (*spec, (key, False)) if len(spec) < SORT_MAX else spec
    i = keys.index(key)
    if not spec[i][1]:
        return (*spec[:i], (key, True), *spec[i + 1 :])
    return (*spec[:i], *spec[i + 1 :])


def sort_badge(spec: Sort, key: str) -> str:
    """The header's mark, as Review Robin's: ↕ unsorted, else its place in
    the cascade and its direction, ``1↑`` or ``2↓``."""
    for n, (k, desc) in enumerate(spec, start=1):
        if k == key:
            return f"{n}{'↓' if desc else '↑'}"
    return "↕"
