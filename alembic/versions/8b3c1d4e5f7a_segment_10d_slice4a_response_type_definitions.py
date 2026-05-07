"""segment 10d slice 4a: response_type_definitions table + RTD FK on RF rows

Adds the per-session ``response_type_definitions`` catalog with the
ten seeded rows, then replaces ``instrument_response_fields.response_type``
(text) with ``response_type_id``, a FK into the new table with
``ON DELETE CASCADE``. Existing RF rows are migrated by the literal-
to-RTD map below.

Revision ID: 8b3c1d4e5f7a
Revises: 543aa71cd452
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b3c1d4e5f7a"
down_revision: Union[str, Sequence[str], None] = "543aa71cd452"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Order matters — the index drives ``seed_order`` and the on-screen
# read-only catalog ordering. Keep in sync with
# ``app/services/instruments.py:SEEDED_RESPONSE_TYPE_DEFINITIONS``
# and ``spec/instruments.md`` "Default seed".
_SEEDED_RTDS: list[dict] = [
    {"response_type": "Long_text",  "data_type": "String",  "min": 0,    "max": 200,  "step": None, "list_csv": None},
    {"response_type": "Short_text", "data_type": "String",  "min": 0,    "max": 50,   "step": None, "list_csv": None},
    {"response_type": "Yes_no",     "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Yes, No"},
    {"response_type": "Grade",      "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "A+, A, A-, B+, B, B-, C+, C, D+, D, F"},
    {"response_type": "Likert5",    "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Strongly Disagree, Disagree, Neutral, Agree, Strongly Agree"},
    {"response_type": "100int",     "data_type": "Integer", "min": 0,    "max": 100,  "step": 1,    "list_csv": None},
    {"response_type": "0-to-2int",  "data_type": "Integer", "min": 0,    "max": 2,    "step": 1,    "list_csv": None},
    {"response_type": "1-to-5int",  "data_type": "Integer", "min": 1,    "max": 5,    "step": 1,    "list_csv": None},
    {"response_type": "1-to-5half", "data_type": "Decimal", "min": 1.0,  "max": 5.0,  "step": 0.5,  "list_csv": None},
    {"response_type": "1-to-5dec",  "data_type": "Decimal", "min": 1.0,  "max": 5.0,  "step": 0.1,  "list_csv": None},
]

# Map legacy ``instrument_response_fields.response_type`` text values
# to the seeded RTD row's ``response_type`` name. Per the Slice 4a
# plan: ``integer`` is ambiguous and gets the canonical ``1-to-5int``.
_LEGACY_TO_RTD: dict[str, str] = {
    "integer": "1-to-5int",
    "short_text": "Short_text",
    "long_text": "Long_text",
    "yes_no": "Yes_no",
}


def upgrade() -> None:
    op.create_table(
        "response_type_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("response_type", sa.String(length=64), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("step", sa.Float(), nullable=True),
        sa.Column("list_csv", sa.Text(), nullable=True),
        sa.Column(
            "is_seeded", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "seed_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "session_id", "response_type", name="uq_rtd_session_name"
        ),
    )

    bind = op.get_bind()
    session_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM sessions")).fetchall()
    ]
    for session_id in session_ids:
        for index, spec in enumerate(_SEEDED_RTDS):
            bind.execute(
                sa.text(
                    "INSERT INTO response_type_definitions "
                    "(session_id, response_type, data_type, min, max, step, "
                    " list_csv, is_seeded, seed_order) "
                    "VALUES (:session_id, :response_type, :data_type, :min, "
                    "        :max, :step, :list_csv, :is_seeded, :seed_order)"
                ),
                {
                    "session_id": session_id,
                    "response_type": spec["response_type"],
                    "data_type": spec["data_type"],
                    "min": spec["min"],
                    "max": spec["max"],
                    "step": spec["step"],
                    "list_csv": spec["list_csv"],
                    "is_seeded": True,
                    "seed_order": index,
                },
            )

    # Add ``response_type_id`` as nullable initially; backfill via the
    # legacy-to-RTD map; then enforce NOT NULL + FK + drop the old text
    # column.
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.add_column(
            sa.Column(
                "response_type_id", sa.Integer(), nullable=True
            )
        )

    rf_rows = bind.execute(
        sa.text(
            "SELECT irf.id, irf.response_type, i.session_id "
            "FROM instrument_response_fields irf "
            "JOIN instruments i ON i.id = irf.instrument_id"
        )
    ).fetchall()
    for rf_id, legacy_type, session_id in rf_rows:
        rtd_name = _LEGACY_TO_RTD.get(legacy_type)
        if rtd_name is None:
            # Defensive: should never hit in practice — every legacy
            # value is in the map. If a forged value escapes, route it
            # to ``Long_text`` as the most permissive String type.
            rtd_name = "Long_text"
        rtd_row = bind.execute(
            sa.text(
                "SELECT id FROM response_type_definitions "
                "WHERE session_id = :session_id "
                "AND response_type = :response_type"
            ),
            {"session_id": session_id, "response_type": rtd_name},
        ).fetchone()
        if rtd_row is None:
            raise RuntimeError(
                f"Slice 4a migration: no RTD row '{rtd_name}' for "
                f"session_id={session_id} (rf_id={rf_id})"
            )
        bind.execute(
            sa.text(
                "UPDATE instrument_response_fields "
                "SET response_type_id = :rtd_id "
                "WHERE id = :rf_id"
            ),
            {"rtd_id": rtd_row[0], "rf_id": rf_id},
        )

    # Now enforce NOT NULL, add the FK with ON DELETE CASCADE, drop
    # the legacy ``response_type`` column. SQLite needs ``batch_alter_table``
    # for ALTER COLUMN + DROP COLUMN; Postgres handles them natively but
    # batch mode round-trips cleanly there too.
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.alter_column(
            "response_type_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.create_foreign_key(
            "fk_irf_response_type_id",
            "response_type_definitions",
            ["response_type_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index(
            "ix_irf_response_type_id",
            ["response_type_id"],
        )
        batch.drop_column("response_type")


def downgrade() -> None:
    bind = op.get_bind()

    # Re-add the legacy text column, populate it from the FK row's
    # ``data_type`` (so a downgrade lands on a valid legacy value),
    # then drop the FK + index + new column.
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.add_column(
            sa.Column("response_type", sa.String(length=64), nullable=True)
        )

    rf_rows = bind.execute(
        sa.text(
            "SELECT irf.id, rtd.response_type "
            "FROM instrument_response_fields irf "
            "JOIN response_type_definitions rtd "
            "ON rtd.id = irf.response_type_id"
        )
    ).fetchall()
    rtd_to_legacy = {v: k for k, v in _LEGACY_TO_RTD.items()}
    for rf_id, rtd_name in rf_rows:
        legacy = rtd_to_legacy.get(rtd_name, "long_text")
        bind.execute(
            sa.text(
                "UPDATE instrument_response_fields "
                "SET response_type = :legacy "
                "WHERE id = :rf_id"
            ),
            {"legacy": legacy, "rf_id": rf_id},
        )

    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.alter_column(
            "response_type",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch.drop_index("ix_irf_response_type_id")
        batch.drop_constraint("fk_irf_response_type_id", type_="foreignkey")
        batch.drop_column("response_type_id")

    op.drop_table("response_type_definitions")
