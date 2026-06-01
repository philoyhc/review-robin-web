"""participants S12: visibility window axis + release-until datetime swap

Lands the two-column S12 prep ahead of the Phase 3 W15 (Band 3
editor) + W7 (resolver) slices, and the operator-facing
Release-now / Stop-release buttons. See
``guide/participant_model_prep.md`` S12 and
``guide/participant_model_upgrade.md`` §3.3 + §3.4.

What lands:

- ``instrument_view_policies.visible_when`` (String(16), NULL) —
  per-(instrument, audience) window pick. Values:
  ``while_ongoing`` (the session-activated → deadline window),
  ``after_release`` (the responses_release window),
  ``throughout`` (union of the two),
  ``always`` (reserved; only meaningful for the operator, who
  isn't an audience row in this table). Nullable / inert; W15
  writes, W7 reads.

- ``sessions.responses_release_until`` (DateTime(tz), NULL) —
  absolute datetime when the release window closes. Replaces
  the W14-shipped ``release_until_offset`` (ISO 8601 duration).
  Both the Edit / Create form's "Release responses until"
  input (a ``datetime-local``) and the new session-level
  **Stop release** button write to this column; **Release
  responses now** clears it so the window re-opens
  open-ended.

- ``sessions.release_until_offset`` — **dropped**. Migration
  backfills ``responses_release_until = responses_release_at +
  parse_iso_duration(release_until_offset)`` for any row where
  both source columns are set. **Offset-only rows**
  (``release_until_offset`` set, ``responses_release_at``
  NULL — today allowed by the W14 validator under the
  §8.2.2 anchor-null rule) have their staged offset dropped
  silently; the new absolute-datetime model has no shape to
  carry an offset without an anchor (you can't compute a
  close datetime without a start datetime). Operators who
  had staged offset alone re-enter a close datetime on the
  form after the migration.

The two new audit event types
(``session.responses_released`` /
``session.responses_release_stopped``) land alongside this
migration as code additions to ``app/services/audit.py``
``EVENT_SCHEMAS``.

Revision ID: f4a92b3c6d18
Revises: c8d4e9f1a2b3
Create Date: 2026-06-01
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4a92b3c6d18"
down_revision: Union[str, Sequence[str], None] = "c8d4e9f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Subset of the ISO 8601 duration grammar shared with
# ``app/services/scheduled_events.parse_iso_duration``. Inlined
# here so the migration doesn't import application code (per
# Alembic best practice — migrations should be self-contained).
_ISO_DURATION_RE = re.compile(
    r"^(?P<sign>-)?P"
    r"(?:(?P<years>\d+)Y)?"
    r"(?:(?P<months>\d+)M)?"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def _parse_iso_duration(text: str) -> timedelta:
    """Local copy of ``app.services.scheduled_events.parse_iso_duration``
    — kept tight (years → 365d, months → 30d) since the migration's
    use is just to convert the few production rows with both source
    columns set."""
    match = _ISO_DURATION_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"not an ISO 8601 duration: {text!r}")
    parts = match.groupdict()
    if all(
        parts[k] is None
        for k in ("years", "months", "days", "hours", "minutes", "seconds")
    ):
        raise ValueError(f"empty ISO 8601 duration: {text!r}")
    years = int(parts["years"] or 0)
    months = int(parts["months"] or 0)
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    delta = timedelta(
        days=years * 365 + months * 30 + days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )
    return -delta if parts["sign"] else delta


def upgrade() -> None:
    # 1. visible_when on instrument_view_policies.
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.add_column(
            sa.Column("visible_when", sa.String(length=16), nullable=True)
        )

    # 2. responses_release_until on sessions.
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "responses_release_until",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    # 3. Backfill responses_release_until from
    #    responses_release_at + parse_iso_duration(release_until_offset)
    #    for any row where both source columns are set. Offset-only
    #    rows are dropped silently per guide/participant_model_prep.md
    #    S12.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, responses_release_at, release_until_offset "
            "FROM sessions "
            "WHERE responses_release_at IS NOT NULL "
            "AND release_until_offset IS NOT NULL"
        )
    ).fetchall()
    for row in rows:
        try:
            delta = _parse_iso_duration(row.release_until_offset)
        except ValueError:
            # Existing storage is already validated at write time;
            # an unparseable row is a data-integrity surprise — skip
            # rather than blow up the migration (the column is
            # dropped below anyway and the operator can re-enter).
            continue
        bind.execute(
            sa.text(
                "UPDATE sessions SET responses_release_until = "
                ":until WHERE id = :id"
            ),
            {"until": row.responses_release_at + delta, "id": row.id},
        )

    # 4. Drop release_until_offset.
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("release_until_offset")


def downgrade() -> None:
    # 1. Re-add release_until_offset.
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(
            sa.Column("release_until_offset", sa.String(length=16), nullable=True)
        )

    # 2. Backfill release_until_offset from
    #    (responses_release_until - responses_release_at) where both
    #    are set. The reverse is best-effort — we encode the delta as
    #    a whole-days / whole-hours ISO duration; rows whose new shape
    #    can't be reversed (e.g. responses_release_until set with no
    #    anchor — created via Stop-release on a never-released
    #    session, an edge case) leave release_until_offset NULL.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, responses_release_at, responses_release_until "
            "FROM sessions "
            "WHERE responses_release_at IS NOT NULL "
            "AND responses_release_until IS NOT NULL"
        )
    ).fetchall()
    for row in rows:
        delta = row.responses_release_until - row.responses_release_at
        # ``delta`` is a Python timedelta; reverse-encode to ISO 8601
        # as a sum of days / hours / minutes / seconds (no months /
        # years — the forward path's months=30d / years=365d
        # approximation isn't reversible exactly).
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            continue
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        date_part = f"{days}D" if days else ""
        time_parts = []
        if hours:
            time_parts.append(f"{hours}H")
        if minutes:
            time_parts.append(f"{minutes}M")
        if seconds:
            time_parts.append(f"{seconds}S")
        time_part = ("T" + "".join(time_parts)) if time_parts else ""
        offset = "P" + date_part + time_part
        if offset == "P":
            continue
        bind.execute(
            sa.text(
                "UPDATE sessions SET release_until_offset = :offset "
                "WHERE id = :id"
            ),
            {"offset": offset, "id": row.id},
        )

    # 3. Drop responses_release_until + visible_when.
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("responses_release_until")
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.drop_column("visible_when")
