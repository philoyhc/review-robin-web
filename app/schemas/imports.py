from __future__ import annotations

from pydantic import BaseModel


class ReviewerImportRow(BaseModel):
    name: str
    email: str
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
