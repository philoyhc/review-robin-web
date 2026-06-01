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
    # Segment 18G Part 1 — operator-set anchor for the scheduled
    # ``validated → ready`` transition. None ⇒ no scheduled
    # activation (operator must Activate manually). Minimum lead
    # time enforced at the route layer
    # (``SCHEDULED_OPERATIONAL_LEAD_HOURS``).
    scheduled_activate_at: datetime | None = None
    # Segment 18G Part 2 — operator-set list of invitation send
    # offsets, each an ISO 8601 duration (e.g. ``"-P1D"``) anchored
    # on ``scheduled_activate_at``. None / empty list ⇒ no auto-send.
    # Per-entry rules (operational lead, reviewer-notice gap)
    # enforced at the route layer when ``scheduled_activate_at`` is
    # also set; inert via the §8.2.2 anchor-null rule otherwise.
    invite_offsets: list[str] | None = None
    # Segment 18G Part 3 — operator-set list of reminder send
    # offsets, anchored on ``deadline`` (End). Same shape as
    # ``invite_offsets``. Inert via the §8.2.2 anchor-null rule
    # when ``deadline`` is unset.
    reminder_offsets: list[str] | None = None
    # Participant-model Phase 2 — per-session feature toggles
    # gating the optional Setup tabs. Both default ``False``;
    # operators opt in via the User interface settings card on
    # Session Edit Details. See
    # ``guide/participant_model_upgrade.md`` §3.8.
    relationships_enabled: bool = False
    observers_enabled: bool = False
    # Participant-model Phase 3 (W14 + S12) — Release-responses
    # window. ``responses_release_at`` is the moment reviewees /
    # observers can start viewing collated responses;
    # ``responses_release_until`` is the absolute close datetime
    # (NULL ⇒ open-ended, or no window scheduled). The Edit / Create
    # form's "Release responses until" input and the operator's
    # Stop release button both write the until column;
    # ``responses_release_at = NULL`` makes the window inert per
    # the §8.2.2 anchor-null rule. S12 retired the original
    # ``release_until_offset`` (ISO 8601 duration) in favour of
    # this absolute datetime — see
    # ``guide/participant_model_upgrade.md`` §3.3 + §3.4.
    responses_release_at: datetime | None = None
    responses_release_until: datetime | None = None


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
