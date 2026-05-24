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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.instrument import Instrument
    from app.db.models.response import Response


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
    # Segment 18J Wave 2 PR iii-b4 — the ``response_type_id`` FK to
    # ``response_type_definitions`` retired alongside the
    # before_insert listener + the per-field
    # ``response_type_definition`` relationship. Every field's type
    # + bounds live inline on the ``_inline_*`` columns below.
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    help_text_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Segment 18J Wave 3 PR i — visibility flag mirroring the
    # ``InstrumentDisplayField.visible`` pattern Gap 1 shipped in
    # Wave 1. Band 2's response-field chip toggle dual-writes
    # through to this column via ``set_band2_state``; reviewer-
    # surface read path starts filtering by ``visible=true`` in
    # PR ii.
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Segment 18J Wave 2 PR i — inline bound columns (now the sole
    # source of truth for type + bounds; PR iii-b4 dropped the
    # FK-tier proxy). Semantics depend on ``_inline_data_type``:
    # numeric bounds for integer/decimal; ``_inline_max`` doubles
    # as char-length cap for string; ``_inline_list_csv`` carries
    # list option lists.
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
    responses: Mapped[list[Response]] = relationship(
        back_populates="response_field",
        cascade="all, delete-orphan",
    )

    @property
    def response_type(self) -> str:
        return self._inline_response_type or ""

    @property
    def data_type(self) -> str:
        return self._inline_data_type or ""

    @property
    def response_type_id(self) -> int | None:
        """Segment 18J Wave 2 PR iii-b4 — phantom read-side shim
        for the retired FK column. Always returns None so legacy
        callers reading ``field.response_type_id`` see a stable
        value instead of an AttributeError. The companion ``init``
        listener below pops the kwarg on construction. Retires
        once all callers stop touching the name."""
        return None


@event.listens_for(InstrumentResponseField, "init")
def _drop_retired_response_type_id_kwarg(target, args, kwargs) -> None:
    """Segment 18J Wave 2 PR iii-b4 — phantom write-side shim.
    Silently drops the retired ``response_type_id`` kwarg so
    legacy ORM constructors keep working until they migrate to
    the inline-shape kwargs."""
    kwargs.pop("response_type_id", None)
