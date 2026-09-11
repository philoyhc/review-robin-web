"""Row pager for the seven roster-bearing tables — Segment 19J.5.

Before this, five of the seven tables stopped at a cap and said so
(``Showing first 200 of 1,240 reviewers; 1,040 more not shown.``) and
the rows past it were unreachable except by searching for them. This
module turns that cap into a page size and hands the template the
ranges to link.

**Ranges, not page numbers** (author, 2026-09-11). ``201–400`` says
where the operator is in the roster; ``page 2`` makes them multiply.

**Elision.** A 40,000-row assignments table is 200 ranges. The pager
shows a window around the current page and hangs First / Last off the
ends, with an ellipsis marking each gap — so the row count a session
can reach is not also the width of its navigation.

**One page is no pager.** ``build_pager`` returns ``None`` when
everything fits, for the same reason ``preview_count_line`` returns
``None`` when a table shows everything: a control that cannot go
anywhere is noise.

The pager is also suppressed whenever a search or status filter is
active — but that is the *route's* call, not this module's, because
the same flag suppresses the pager and summons the count line and the
two must never disagree. This module is only asked once the route has
decided a pager belongs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PAGE_SIZE", "PagerLink", "Pager", "build_pager"]


# The cap the five capped tables already used, now read as a page size.
# Not operator-configurable: one number, already specified and already
# tested, and a selector would be a setting, an inventory row and a
# persistence question for a need nobody has stated.
PAGE_SIZE = 200

# Ranges shown either side of the current one before the ellipsis
# takes over. Five keeps the strip inside one line at the narrowest
# operator width the app supports.
_WINDOW = 5


@dataclass(frozen=True)
class PagerLink:
    """One range in the strip. ``offset`` is the row index it starts
    at, which is what the route reads back off the query string."""

    label: str
    offset: int
    is_current: bool


@dataclass(frozen=True)
class Pager:
    """What the template renders. ``first`` and ``last`` are ``None``
    when that end is already inside ``links`` — an elision marker and
    a First anchor pointing at a range the strip already shows would
    be two ways to reach the same place."""

    links: tuple[PagerLink, ...]
    first: PagerLink | None
    last: PagerLink | None
    elided_before: bool
    elided_after: bool
    page_size: int
    total: int


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
    """The strip for a table of ``total`` rows positioned at ``offset``,
    or ``None`` when the table holds one page or less."""
    if page_size <= 0 or total <= page_size:
        return None

    offset = clamp_offset(offset, total=total, page_size=page_size)
    page_count = (total + page_size - 1) // page_size
    current_index = offset // page_size

    def link(index: int) -> PagerLink:
        start = index * page_size
        end = min(start + page_size, total)
        return PagerLink(
            label=_label(start + 1, end),
            offset=start,
            is_current=index == current_index,
        )

    half = _WINDOW // 2
    window_start = max(0, current_index - half)
    window_end = min(page_count - 1, window_start + _WINDOW - 1)
    # Re-anchor when the window runs off the end, so the strip keeps a
    # constant width instead of shrinking near the last page.
    window_start = max(0, window_end - _WINDOW + 1)

    links = tuple(link(i) for i in range(window_start, window_end + 1))
    return Pager(
        links=links,
        first=link(0) if window_start > 0 else None,
        last=link(page_count - 1) if window_end < page_count - 1 else None,
        elided_before=window_start > 1,
        elided_after=window_end < page_count - 2,
        page_size=page_size,
        total=total,
    )
