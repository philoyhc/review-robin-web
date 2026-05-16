from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    deadline: datetime | None = None
    # Operational help contact ("I have questions about the review
    # process" — distinct from the technical-support contact tracked
    # at unfinished_business.md #35). Surfaces on the reviewer
    # surface and as the ``$help_contact`` merge field in the email
    # template editor (Segment 11E).
    help_contact: str | None = Field(default=None, max_length=320)
    # Per-session display timezone (an IANA zone name), picked on the
    # Create Session form. None ⇒ the service falls back to the
    # creating operator's default. Segment 18B PR 4.
    display_timezone: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str | None
    status: str
    deadline: datetime | None
    help_contact: str | None
    created_at: datetime
