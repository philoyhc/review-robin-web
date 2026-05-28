"""Segment 18N PR 1 — ``validate_page_n`` helper.

The reviewer-surface GET, the save POST, and the operator-side
preview route all need to validate a 1-based ``page_n`` against
the session's pages list and 404 on out-of-range. Before this
helper landed, the GET + preview clamped ``page_count = len(pages)
or 1`` (rendering empty content on ``/1`` for empty sessions)
while the save POST hard-failed with ``len(pages)`` (404 on
empty). The asymmetry was unreachable in practice but
inconsistent. ``validate_page_n`` is the single source of truth
all three routes now call.

Strict semantics: empty pages list, ``page_n < 1``, and
``page_n > len(pages)`` all raise 404.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.web.routes_reviewer._shared import validate_page_n


# Pages payloads are sequences of sequences of Instrument; for the
# helper's perspective only the length matters. Use plain lists of
# sentinel objects so the unit test stays decoupled from the ORM.
_inst = object()


@pytest.mark.parametrize(
    "page_n,pages,expected",
    [
        # Single-page session — only ``/1`` valid.
        (1, [[_inst]], 1),
        # Three-page session — every in-range index round-trips.
        (1, [[_inst], [_inst], [_inst]], 1),
        (2, [[_inst], [_inst], [_inst]], 2),
        (3, [[_inst], [_inst], [_inst]], 3),
        # Multi-instrument page (one page with two instruments)
        # — still valid at ``/1``.
        (1, [[_inst, _inst]], 1),
    ],
)
def test_validate_page_n_returns_page_n_when_in_range(
    page_n: int, pages: list[list[object]], expected: int
) -> None:
    assert validate_page_n(page_n, pages) == expected


@pytest.mark.parametrize(
    "page_n,pages",
    [
        # Empty pages — every method now 404s (was the GET + preview
        # quirk of returning 200 with empty content on ``/1``).
        (1, []),
        (2, []),
        # Above the last page.
        (2, [[_inst]]),
        (4, [[_inst], [_inst], [_inst]]),
        # Zero and negative ``page_n``.
        (0, [[_inst]]),
        (-1, [[_inst]]),
        # Zero on empty (the unreachable-in-practice cross-product).
        (0, []),
    ],
)
def test_validate_page_n_raises_404_on_out_of_range(
    page_n: int, pages: list[list[object]]
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_page_n(page_n, pages)
    assert exc_info.value.status_code == 404
