from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.instrument import Instrument
    from app.db.models.response import Response
    from app.db.models.response_type_definition import ResponseTypeDefinition


class InstrumentDisplayField(Base):
    __tablename__ = "instrument_display_fields"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    instrument: Mapped[Instrument] = relationship(back_populates="display_fields")


class InstrumentResponseField(Base):
    __tablename__ = "instrument_response_fields"
    __table_args__ = (
        UniqueConstraint("instrument_id", "field_key", name="uq_instrument_field_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), index=True, nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    response_type_id: Mapped[int] = mapped_column(
        ForeignKey("response_type_definitions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    help_text_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Segment 18J Wave 2 PR i — inline bound columns. The RTD FK +
    # the ``response_type`` / ``data_type`` proxy properties below
    # still dereference the RTD on read; subsequent PRs flip
    # readers to these columns and drop the FK. Backfilled from
    # each row's RTD on the same migration that adds them.
    # Semantics depend on ``_inline_data_type``: numeric bounds for
    # integer/decimal; ``_inline_max`` doubles as char-length cap
    # for string; ``_inline_list_csv`` carries list option lists.
    _inline_data_type: Mapped[str | None] = mapped_column(
        "data_type", String(16), nullable=True
    )
    _inline_response_type: Mapped[str | None] = mapped_column(
        "response_type", String(64), nullable=True
    )
    _inline_min: Mapped[float | None] = mapped_column(
        "min", Float, nullable=True
    )
    _inline_max: Mapped[float | None] = mapped_column(
        "max", Float, nullable=True
    )
    _inline_step: Mapped[float | None] = mapped_column(
        "step", Float, nullable=True
    )
    _inline_list_csv: Mapped[str | None] = mapped_column(
        "list_csv", Text, nullable=True
    )

    instrument: Mapped[Instrument] = relationship(back_populates="response_fields")
    response_type_definition: Mapped[ResponseTypeDefinition] = relationship(
        back_populates="response_fields",
    )
    responses: Mapped[list[Response]] = relationship(
        back_populates="response_field",
        cascade="all, delete-orphan",
    )

    @property
    def response_type(self) -> str:
        # Segment 18J Wave 2 PR ii — prefer the inline column,
        # fall back to the RTD-tier relationship for any row whose
        # inline copy is unset (legacy data not yet backfilled, or
        # a brand-new row created in an isolated bind that bypasses
        # the before_insert listener).
        if self._inline_response_type is not None:
            return self._inline_response_type
        return self.response_type_definition.response_type

    @property
    def data_type(self) -> str:
        if self._inline_data_type is not None:
            return self._inline_data_type
        return self.response_type_definition.data_type


@event.listens_for(InstrumentResponseField, "before_insert")
def _sync_inline_bounds_from_rtd(mapper, connection, target) -> None:
    """Segment 18J Wave 2 PR i — populate the inline bound columns
    from the row's associated RTD on insert so the schema is in the
    target shape before PR ii flips readers. Skips when the caller
    already populated ``_inline_data_type`` (idempotent for tests /
    seeders that hand-set the columns). PR iii drops the listener
    + the RTD FK + the seeded numerical / string RTDs.

    Local import of ``ResponseTypeDefinition`` avoids a module-load
    circular dep — the relationship target lives in a sibling file.
    """
    if target._inline_data_type is not None:
        return
    if target.response_type_id is None:
        return
    # Local import — same-package circular dep avoidance.
    from app.db.models.response_type_definition import ResponseTypeDefinition

    row = connection.execute(
        select(
            ResponseTypeDefinition.data_type,
            ResponseTypeDefinition.response_type,
            ResponseTypeDefinition.min,
            ResponseTypeDefinition.max,
            ResponseTypeDefinition.step,
            ResponseTypeDefinition.list_csv,
        ).where(ResponseTypeDefinition.id == target.response_type_id)
    ).first()
    if row is None:
        return
    target._inline_data_type = row.data_type
    target._inline_response_type = row.response_type
    target._inline_min = row.min
    target._inline_max = row.max
    target._inline_step = row.step
    target._inline_list_csv = row.list_csv
