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
    # Segment 18J Wave 2 PR iii-a — FK is now nullable. List-type
    # fields point at a per-session List RTD (option-list reuse).
    # Numerical / string fields hold their type + bounds inline on
    # ``_inline_*`` columns below; ``response_type_id`` is NULL for
    # them. The full RTD library tier retires in PR iii-b.
    response_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("response_type_definitions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
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
    response_type_definition: Mapped[ResponseTypeDefinition | None] = relationship(
        back_populates="response_fields",
    )
    responses: Mapped[list[Response]] = relationship(
        back_populates="response_field",
        cascade="all, delete-orphan",
    )

    @property
    def response_type(self) -> str:
        # Segment 18J Wave 2 PR iii-a — inline columns are the
        # source of truth. List-type fields keep the FK around for
        # option-list reuse across instruments; numerical / string
        # fields land with response_type_id = NULL post-iii-a (the
        # seeded non-List RTDs are dropped by the iii-a migration).
        # The fallback to response_type_definition is belt-and-
        # braces for the brief window where a transitional creator
        # path might still be setting the FK without the listener
        # firing; it retires in PR iii-b alongside the FK column
        # itself.
        if self._inline_response_type is not None:
            return self._inline_response_type
        if self.response_type_definition is not None:
            return self.response_type_definition.response_type
        return ""

    @property
    def data_type(self) -> str:
        if self._inline_data_type is not None:
            return self._inline_data_type
        if self.response_type_definition is not None:
            return self.response_type_definition.data_type
        return ""


@event.listens_for(InstrumentResponseField, "before_insert")
def _sync_inline_bounds_from_rtd(mapper, connection, target) -> None:
    """Bridge listener: when a new ``InstrumentResponseField`` row
    sets ``response_type_id`` (typical for List fields, and for
    backward-compatible numerical / string creation paths that
    haven't yet been updated to populate inline directly), copy
    the RTD's bounds onto the inline columns so reads land in the
    right shape regardless of which API the caller used.

    Originally added in PR i; survives iii-a so the FK still
    works as a bound source for callers in transition. Retires in
    PR iii-b alongside the FK column itself, once every creator
    populates inline columns explicitly.
    """
    if target._inline_data_type is not None:
        return
    if target.response_type_id is None:
        return
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
