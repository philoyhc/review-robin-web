from __future__ import annotations

from pydantic import BaseModel


class ReviewerImportRow(BaseModel):
    name: str
    email: str
    profile_link: str | None = None
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None


class RevieweeImportRow(BaseModel):
    name: str
    email_or_identifier: str
    profile_link: str | None = None
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None


class RelationshipImportRow(BaseModel):
    """Per-pair attribute row resolved against the session's existing
    rosters at import time. ``reviewer_id`` / ``reviewee_id`` carry
    the FK targets the parser resolved from the row's
    ``ReviewerEmail`` / ``RevieweeEmail`` cells.
    """

    reviewer_id: int
    reviewee_id: int
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None
    status: str = "active"
