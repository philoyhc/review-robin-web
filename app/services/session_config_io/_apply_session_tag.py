"""``session_tags[N].tag`` parse + apply — Segment 18P PR D2.

Session tags round-trip through the settings CSV (they already
round-tripped through ``session_clone``). Wipe-and-replace on apply,
mirroring the other list sections.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionTag
from app.services.session_tags import normalize_tag

from ._apply_shared import _RX_SESSION_TAG, _ParsedConfig, _ParseError


def _apply_session_tag_kv(
    plan: _ParsedConfig, field_path: str, value: str
) -> None:
    match = _RX_SESSION_TAG.match(field_path)
    if match is None:
        raise _ParseError(f"unrecognised session_tags[] key {field_path!r}")
    attr = match.group(2)
    if attr != "tag":
        raise _ParseError(f"unknown session_tags[] attribute {attr!r}")
    # 19S Item 9: tags are lower case everywhere, so an imported tag is
    # normalized exactly as a typed one is — lowercased, trimmed, length-
    # checked. Before this, ``Pilot`` was stored raw while every typed
    # surface lowercased, and the lobby could not remove it. A blank value
    # is skipped as before; an over-long one rejects the bundle with a
    # message, rather than reaching a 64-character column raw.
    if not value.strip():
        return
    try:
        tag = normalize_tag(value)
    except ValueError as exc:
        raise _ParseError(f"session_tags[] value {value!r}: {exc}") from exc
    if tag not in plan.session_tags:
        plan.session_tags.append(tag)


def _apply_session_tags(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Wipe-and-replace the session's tags from the parsed set.

    ``(session_id, tag)`` is unique, so the parse phase already
    de-duplicated; here we drop every existing tag not in the CSV and
    insert the ones that are new.
    """
    existing = {
        tag.tag: tag
        for tag in db.execute(
            select(SessionTag).where(
                SessionTag.session_id == review_session.id
            )
        ).scalars()
    }

    written = 0
    for tag_value in plan.session_tags:
        if existing.pop(tag_value, None) is None:
            db.add(SessionTag(session_id=review_session.id, tag=tag_value))
        written += 1

    for orphan in existing.values():
        db.delete(orphan)

    return written
