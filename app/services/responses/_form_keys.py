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

The form also carries a digest of the page's rows. A post whose digest
doesn't match the page as it stands now was made against a page that
changed since it rendered, and an ordinal would land on the wrong row, so
it is refused. The digest covers only what the reviewer can already see,
never an ID: each row's instrument position and reviewee, in ID order.
It is keyed, but the key (``PARTICIPANT_TOKEN_SALT``) has a public default,
so it must not be the thing keeping IDs out of the page: someone who
brute-forces the digest learns nothing the page doesn't already show.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from app.services.participant_tokens import workspace_salt

if TYPE_CHECKING:
    from app.db.models import Assignment

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


def page_digest(session_public_id: str, rows: Sequence[Assignment]) -> str:
    """A digest of one page's rows, in ID order: per row its instrument's
    position and its reviewee's name and identifier, which the page shows.
    A row joining or leaving the page, or two rows trading places in ID
    order, changes it; no ID goes in."""
    parts = [
        "\x1f".join(
            (
                str(a.instrument.order),
                a.reviewee.name or "",
                a.reviewee.email_or_identifier or "",
            )
        )
        for a in rows
    ]
    message = "\x1e".join(["rrw-page-digest", session_public_id, *parts])
    return hmac.new(
        workspace_salt().encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def digest_matches(
    posted: str | None, session_public_id: str, rows: Sequence[Assignment]
) -> bool:
    """Whether a posted digest is the page's. Anything not shaped like a
    digest is a mismatch, before any comparison: ``hmac.compare_digest``
    refuses a non-ASCII string with ``TypeError``."""
    if not posted or not _DIGEST_SHAPE.fullmatch(posted):
        return False
    return hmac.compare_digest(
        posted.encode("ascii"), page_digest(session_public_id, rows).encode("ascii")
    )
