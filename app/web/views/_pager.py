"""Row pager for the seven roster-bearing tables — Segment 19J.5.

Before this, five of the seven tables stopped at a cap and said so
(``Showing first 200 of 1,240 reviewers; 1,040 more not shown.``) and
the rows past it were unreachable except by searching for them. This
module turns that cap into a page size and hands the template the
ranges to link.

**Ranges, not page numbers** (author, 2026-09-11). ``201–400`` says
where the operator is in the roster; ``page 2`` makes them multiply.

**One page is no pager.** ``build_pager`` returns ``None`` when
everything fits, for the same reason ``preview_count_line`` returns
``None`` when a table shows everything: a control that cannot go
anywhere is noise.

The pager is also suppressed whenever a search or status filter is
active — but that is the *route's* call, not this module's, because
the same flag suppresses the pager and summons the count line and the
two must never disagree. This module is only asked once the route has
decided a pager belongs.

**What used to be here** (19J.5, retired 2026-09-11 at 19J.9): a
five-wide window of links centred on the current page, with First and
Last hung off the ends and an ellipsis marking each gap, so a
40,000-row table was not 200 links wide. It went with the strip that
rendered it. The window bounded the strip's *width* and left its
*depth* alone — reach was two pages per click whatever the roster
size, so crossing a long roster cost a number of clicks linear in its
length. ``Pager`` now carries where you are and how big the table is,
and the cluster renders every range in a menu.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PAGE_SIZE", "PagerLink", "Pager", "build_pager", "clamp_offset"]


# The cap the five capped tables already used, now read as a page size.
# Not operator-configurable: one number, already specified and already
# tested, and a selector would be a setting, an inventory row and a
# persistence question for a need nobody has stated.
PAGE_SIZE = 200


@dataclass(frozen=True)
class PagerLink:
    """One range in the menu. ``offset`` is the row index it starts
    at, which is what the route reads back off the query string."""

    label: str
    offset: int
    is_current: bool


@dataclass(frozen=True)
class Pager:
    """Where the operator is, and how much table there is.

    Three scalars and a derived list: the ranges are computed on
    demand rather than stored, because they are markup's business and
    a 40,000-row table has 200 of them.
    """

    offset: int
    page_size: int
    total: int

    @property
    def ranges(self) -> tuple[PagerLink, ...]:
        """Every range in the table, in order, one of them current."""
        page_count = (self.total + self.page_size - 1) // self.page_size
        return tuple(
            PagerLink(
                label=_label(
                    index * self.page_size + 1,
                    min((index + 1) * self.page_size, self.total),
                ),
                offset=index * self.page_size,
                is_current=index * self.page_size == self.offset,
            )
            for index in range(page_count)
        )


def _label(start: int, end: int) -> str:
    return f"{start:,}–{end:,}"


def clamp_offset(offset: int, *, total: int, page_size: int = PAGE_SIZE) -> int:
    """Snap an arbitrary ``?offset=`` onto a real page boundary.

    Out of range clamps rather than 404s: a link that was valid before
    someone deleted forty rows should land on the last page, not on an
    error. Negative clamps to the first page for the same reason — a
    hand-edited URL is not worth an error page.
    """
    if total <= 0 or page_size <= 0:
        return 0
    if offset <= 0:
        return 0
    last_start = ((total - 1) // page_size) * page_size
    if offset >= last_start:
        return last_start
    # Snap to the boundary at or below the requested row.
    return (offset // page_size) * page_size


def build_pager(
    *, total: int, offset: int = 0, page_size: int = PAGE_SIZE
) -> Pager | None:
    """The pager for a table of ``total`` rows positioned at ``offset``,
    or ``None`` when the table holds one page or less."""
    if page_size <= 0 or total <= page_size:
        return None
    return Pager(
        offset=clamp_offset(offset, total=total, page_size=page_size),
        page_size=page_size,
        total=total,
    )
