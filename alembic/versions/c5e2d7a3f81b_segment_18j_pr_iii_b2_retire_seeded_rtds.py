"""segment_18J wave 2 PR iii-b2 — retire all seeded RTDs

After PR iii-b1 every numerical / string ``instrument_response_field``
carries its bounds inline. iii-b2 retires the entire seeded RTD
catalog. Per-instrument inline option lists (``_inline_list_csv``)
replace the per-session reuse pattern the List-type seeded RTDs
supported; the new-model card's Band 3 already accepts inline
list_options.

Migration steps:

1. NULL ``instrument_response_fields.response_type_id`` for every
   row pointing at a seeded RTD (``is_seeded=True``). Inline bound
   columns (PR i backfill + PR iii-b1 explicit creators) carry the
   type info forward.
2. DELETE every seeded RTD from ``response_type_definitions``.
   Operator-authored custom RTDs (``is_seeded=False``) are left in
   place — the library tier + the table itself retire in iii-b3 /
   iii-b4.

Revision ID: c5e2d7a3f81b
Revises: b1e8f3c47d92
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e2d7a3f81b"
down_revision: Union[str, Sequence[str], None] = "b1e8f3c47d92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ``is_seeded`` is a Boolean column. SQLite stores booleans as
    # 0/1 integers so ``= 1`` happens to work; psycopg + Postgres
    # rejects the integer comparison with ``operator does not
    # exist: boolean = integer``. ``IS TRUE`` is the portable
    # idiom that both dialects accept.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE instrument_response_fields
            SET response_type_id = NULL
            WHERE response_type_id IN (
                SELECT id FROM response_type_definitions
                WHERE is_seeded IS TRUE
            )
            """
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM response_type_definitions WHERE is_seeded IS TRUE"
        )
    )


def downgrade() -> None:
    """Re-creates the ten seeded RTDs on every existing session. FK
    refs that were NULL'd are NOT restored — the migration can't
    tell which seeded RTD each field originally pointed at."""
    bind = op.get_bind()
    sessions = bind.execute(
        sa.text("SELECT id FROM sessions")
    ).fetchall()
    rows = [
        ("Long_text",  "String",  0,    2000, None, None,    0),
        ("Short_text", "String",  0,    100,  None, None,    1),
        ("Yes_no",     "List",    None, None, None,
         "Yes, No",                                          2),
        ("Grade",      "List",    None, None, None,
         "A+, A, A-, B+, B, B-, C+, C, D+, D, F",            3),
        ("Likert5",    "List",    None, None, None,
         "Strongly Agree, Agree, Neutral, Disagree, Strongly Disagree",
                                                             4),
        ("100int",     "Integer", 0,    100,  1,    None,    5),
        ("0-to-2int",  "Integer", 0,    2,    1,    None,    6),
        ("1-to-5int",  "Integer", 1,    5,    1,    None,    7),
        ("1-to-5half", "Decimal", 1.0,  5.0,  0.5,  None,    8),
        ("1-to-5dec",  "Decimal", 1.0,  5.0,  0.1,  None,    9),
    ]
    for (session_id,) in sessions:
        for (rt, dt, min_, max_, step, lc, seed_order) in rows:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO response_type_definitions
                    (session_id, response_type, data_type, min, max,
                     step, list_csv, is_seeded, seed_order)
                    VALUES (:sid, :rt, :dt, :min, :max, :step, :lc,
                            1, :so)
                    """
                ),
                {
                    "sid": session_id,
                    "rt": rt,
                    "dt": dt,
                    "min": min_,
                    "max": max_,
                    "step": step,
                    "lc": lc,
                    "so": seed_order,
                },
            )
