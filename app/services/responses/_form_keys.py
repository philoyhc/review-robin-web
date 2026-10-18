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

The form also carries a digest of the page's assignment-ID set (keyed,
so it reveals no count). A post whose digest doesn't match the page as
it stands now was made against a page that changed since it rendered,
and an ordinal would land on the wrong row, so it is refused.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable, Sequence

from app.services.participant_tokens import workspace_salt

PAGE_DIGEST_FIELD = "page_digest"


def page_assignment_ids(
    assignments: Iterable[object], instrument_ids: set[int]
) -> list[int]:
    """The IDs of ``assignments`` on the page's instruments, ascending.
    ``assignments`` are the reviewer's included ones, as the surface
    loads them."""
    return sorted(
        a.id for a in assignments if a.instrument_id in instrument_ids  # type: ignore[attr-defined]
    )


def answer_ordinals(assignment_ids: Sequence[int]) -> dict[int, int]:
    """Assignment ID → its ordinal in a form name."""
    return {aid: n for n, aid in enumerate(assignment_ids, start=1)}


def page_digest(session_public_id: str, assignment_ids: Sequence[int]) -> str:
    """A keyed digest of one page's assignment-ID set."""
    message = f"{session_public_id}|{','.join(map(str, assignment_ids))}"
    return hmac.new(
        workspace_salt().encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def digest_matches(
    posted: str | None, session_public_id: str, assignment_ids: Sequence[int]
) -> bool:
    return hmac.compare_digest(
        posted or "", page_digest(session_public_id, assignment_ids)
    )
