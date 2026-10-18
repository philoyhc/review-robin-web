"""How the review form names its answers (19V Item 2).

An answer box is named ``response[{ordinal}][{field_key}]``. The
ordinal is the row's rank, 1-based, among the page's assignments in
assignment-ID order, never the assignment ID itself, which is
workspace-wide and would let a reviewer read off how many assignments
the workspace has made.

ID order, not display order: a reviewer's column sort reorders the
rows in the browser and the server rebuilds them in the cookie's order,
so a display position would name a different row after a sort. The
same page always yields the same ordinals.

The form also carries a digest of the page's assignment-ID set, in ID
order. A post whose digest doesn't match the page as it stands now was
made against a page that changed since it rendered, and an ordinal would
land on the wrong row, so it is refused. The digest is keyed by the
session's own ``form_key``, a random secret never rendered or exported,
so it reveals neither the IDs nor their count, and can't be brute-forced
for anything the page hides.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Assignment, ReviewSession

PAGE_DIGEST_FIELD = "page_digest"

# ``response[{ordinal}][{field_key}]``. ``n`` is ASCII digits, bounded so a
# hand-made key can't reach a database bind.
ANSWER_KEY_PATTERN = re.compile(r"^response\[(?P<n>[0-9]{1,6})\]\[(?P<key>[^\]]+)\]$")
_DIGEST_SHAPE = re.compile(r"[0-9a-f]{32}")


def page_assignments(
    assignments: Iterable[Assignment], instrument_ids: set[int]
) -> list[Assignment]:
    """``assignments`` on the page's instruments, in ID order.
    ``assignments`` are the reviewer's included ones, as the surface loads
    them, with ``reviewee`` and ``instrument`` loaded."""
    return sorted(
        (a for a in assignments if a.instrument_id in instrument_ids),
        key=lambda a: a.id,
    )


def page_assignment_ids(
    assignments: Iterable[Assignment], instrument_ids: set[int]
) -> list[int]:
    """The IDs of ``page_assignments``, ascending."""
    return [a.id for a in page_assignments(assignments, instrument_ids)]


def answer_ordinals(assignment_ids: Sequence[int]) -> dict[int, int]:
    """Assignment ID → its ordinal in a form name."""
    return {aid: n for n, aid in enumerate(assignment_ids, start=1)}


def page_digest(review_session: ReviewSession, rows: Sequence[Assignment]) -> str:
    """A digest of one page's assignment IDs in ID order, keyed by the
    session's secret ``form_key``. A row joining or leaving the page
    changes it."""
    message = "rrw-page-digest|" + ",".join(str(a.id) for a in rows)
    return hmac.new(
        review_session.form_key.encode("ascii"),
        message.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()[:32]


def digest_matches(
    posted: str | None, review_session: ReviewSession, rows: Sequence[Assignment]
) -> bool:
    """Whether a posted digest is the page's. Anything not shaped like a
    digest is a mismatch, before any comparison: ``hmac.compare_digest``
    refuses a non-ASCII string with ``TypeError``."""
    if not posted or not _DIGEST_SHAPE.fullmatch(posted):
        return False
    return hmac.compare_digest(
        posted.encode("ascii"), page_digest(review_session, rows).encode("ascii")
    )
