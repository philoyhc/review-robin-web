"""Review-form posts as the page renders them (19V Item 2).

The review page names each answer ``response[{ordinal}][{field_key}]``,
the row's rank among the page's assignments in ID order, and carries a
digest of that set. Tests think in assignment IDs, so they build the
form keyed by ID and pass it through ``answer_form``, which rewrites the
keys to ordinals and adds the digest, exactly as a browser posting the
rendered page would.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.db.models import Assignment, Reviewer, ReviewSession
from app.services import responses as responses_service
from app.web.routes_reviewer._surface._context import page_assignments_for

_BY_ID = re.compile(r"^response\[(?P<aid>[0-9]+)\]\[(?P<key>[^\]]+)\]$")


def answer_form(
    db: Session, data: Mapping[str, str], *, page_n: int = 1
) -> dict[str, str]:
    """``data`` with its ``response[<assignment id>][<key>]`` keys renamed
    to page ``page_n``'s ordinals, plus the page digest. Other keys pass
    through. Every assignment named must belong to one reviewer and sit
    on that page; a test that wants a stale or forged post builds it by
    hand."""
    matches = {key: _BY_ID.match(key) for key in data}
    assignment_ids = {int(m["aid"]) for m in matches.values() if m}
    if not assignment_ids:
        return dict(data)
    first = db.get(Assignment, min(assignment_ids))
    review_session = db.get(ReviewSession, first.session_id)
    reviewer = db.get(Reviewer, first.reviewer_id)
    page_rows = page_assignments_for(db, review_session, reviewer, page_n)
    ordinals = responses_service.answer_ordinals([a.id for a in page_rows])
    missing = assignment_ids - set(ordinals)
    assert not missing, f"assignments {sorted(missing)} are not on page {page_n}"
    out: dict[str, str] = {}
    for key, value in data.items():
        m = matches[key]
        out[f"response[{ordinals[int(m['aid'])]}][{m['key']}]" if m else key] = value
    out[responses_service.PAGE_DIGEST_FIELD] = responses_service.page_digest(
        review_session,
        page_rows,
        group_keys=responses_service.group_keys(
            db, assignments=page_rows, session_id=review_session.id
        ),
    )
    return out
