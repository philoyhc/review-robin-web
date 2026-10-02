from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.instrument import Instrument


class InstrumentViewPolicy(Base, TimestampMixin):
    """Per-instrument response-visibility grant for one of three
    participant audiences (reviewee / peer_reviewer / observer).

    The operator authors at most three rows per instrument — one
    per audience — via the Band 3 visibility editor (Phase 3 /
    Wiring slice W15). The resolver consumes these rows at view
    time (no materialization onto ``assignments``) to decide which
    audiences see this instrument's responses and in what form.

    An ``observer_tag`` column, meant to restrict the observer grant
    to observers carrying a tag, was dropped unread on 2026-10-02
    (findings A19): an observer's cohort rule decides who they see.

    Lands inert per ``guide/archive/participant_model_upgrade.md`` Phase 1;
    the Band 3 editor lights the table up in Phase 3. See
    ``guide/archive/participant_model_upgrade.md`` §3.3.
    """

    __tablename__ = "instrument_view_policies"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "audience",
            name="uq_view_policy_instrument_audience",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), index=True, nullable=False
    )
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    # Per-window mode pairs. Each pair encodes the audience's mode
    # in that window via a ``(granularity, identification)`` tuple;
    # ``NULL`` in both members of a pair ≡ "off in this window".
    # The pair (``aggregated``, ``identified``) is reserved-
    # incoherent and rejected by the service. See
    # ``spec/visibility_policy.md``.
    while_ongoing_granularity: Mapped[str | None] = mapped_column(String(16))
    while_ongoing_identification: Mapped[str | None] = mapped_column(String(16))
    after_release_granularity: Mapped[str | None] = mapped_column(String(16))
    after_release_identification: Mapped[str | None] = mapped_column(String(16))

    instrument: Mapped[Instrument] = relationship(back_populates="view_policies")
