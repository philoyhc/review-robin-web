from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.instrument import Instrument


# The per-cell rule (`spec/visibility_policy.md` §3.1) as the database
# enforces it, so no write path can store a cell the Band 3 editor and
# the Settings import refuse (author, 2026-10-15,
# `guide/visibility_audit.md`). Each window's stored pair is off (both
# NULL) or one of the three modes, and each `(audience, window)` cell
# allows only some. `visibility_policies._PER_CELL_VALID_MODES` states
# the same rule for the validators; a test inserts every combination
# and checks the two agree.
_MODE_PAIRS: dict[str | None, tuple[str, str] | None] = {
    None: None,
    "raw": ("row", "identified"),
    "anonymized": ("row", "deidentified"),
    "summarized": ("aggregated", "deidentified"),
}
_CELL_MODES: dict[str, tuple[tuple[str | None, ...], tuple[str | None, ...]]] = {
    # audience: (while_ongoing modes, after_release modes)
    "peer_reviewer": (("raw",), (None, "raw")),
    "reviewee": ((None,), (None, "raw", "anonymized", "summarized")),
    "observer": ((None, "summarized"), (None, "raw", "anonymized", "summarized")),
}


def _window_sql(window: str, modes: tuple[str | None, ...]) -> str:
    terms = []
    for mode in modes:
        pair = _MODE_PAIRS[mode]
        if pair is None:
            terms.append(
                f"({window}_granularity IS NULL AND {window}_identification IS NULL)"
            )
        else:
            # COALESCE, so a NULL column compares false rather than
            # NULL: a CHECK passes on NULL, and an `=` against NULL
            # would let a half-set or unset pair through.
            terms.append(
                f"(COALESCE({window}_granularity, '') = '{pair[0]}' "
                f"AND COALESCE({window}_identification, '') = '{pair[1]}')"
            )
    return "(" + " OR ".join(terms) + ")"


VIEW_POLICY_CELL_CHECK = " OR ".join(
    f"(audience = '{audience}' AND {_window_sql('while_ongoing', ongoing)} "
    f"AND {_window_sql('after_release', released)})"
    for audience, (ongoing, released) in _CELL_MODES.items()
)


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
        CheckConstraint(VIEW_POLICY_CELL_CHECK, name="ck_view_policy_cell"),
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
    # How much of the reviewer a Raw released view names, on a reviewee
    # or observer row: ``name`` / ``name_email`` /
    # ``name_email_profile``; ``NULL`` reads as ``name_email``, which
    # is what Raw showed before the level existed. Only Raw reads it.
    # ``guide/profilelink_updates.md`` Item 2.
    after_release_reviewer_identity: Mapped[str | None] = mapped_column(
        String(24)
    )

    instrument: Mapped[Instrument] = relationship(back_populates="view_policies")
