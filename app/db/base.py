from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def column_length(model: type[Base], name: str) -> int:
    """The declared length of ``model``'s ``String`` column ``name``,
    for refusing a value before Postgres does. Raises ``TypeError`` if
    the column is not a ``String`` of fixed length."""
    column_type = model.__table__.columns[name].type
    if not isinstance(column_type, String) or column_type.length is None:
        raise TypeError(f"{model.__name__}.{name} has no declared length")
    return column_type.length


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
