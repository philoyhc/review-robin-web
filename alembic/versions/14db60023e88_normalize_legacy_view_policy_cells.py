"""Normalize instrument_view_policies cells the per-cell rule refuses (findings A17)

The per-window columns were backfilled by ``a7e3b1d92c64`` from the old
``visible_when`` triple, before the per-cell rule
(``visibility_policies._PER_CELL_VALID_MODES``, ``spec/visibility_policy.md``
§3.1) existed, and nothing normalized them since. Such a row breaks every
writer that checks the rule: an observer ``while_ongoing = raw`` row
makes each Save of its Instrument card 422, and a reviewer
``while_ongoing`` NULL row exports a cell the Settings import refuses,
blocking a Quick Setup re-import and Rehydrate.

By the author's ruling (2026-10-05) each illegal cell is rewritten to the
nearest legal one, never wider than what it granted in effect (the
reviewer's ongoing cell becomes ``raw``, which no access check reads —
the reviewer always sees their own answers while ``ready`` — so only the
transparency table's label moves):

- a cell with one legal value takes it: the reviewer's
  ``while_ongoing`` is ``raw`` (what the app already shows there), the
  reviewee's is off;
- an observer ``while_ongoing`` ``raw`` / ``anonymized`` becomes
  ``summarized``, the one mode that cell keeps;
- anything else illegal — a half-set pair, the reserved-incoherent
  ``aggregated`` + ``identified``, an unknown value, or a mode the cell
  does not offer — becomes off.

The downgrade is a no-op: the old values are not recoverable, and every
value written is valid before and after.

Revision ID: 14db60023e88
Revises: a2d16ffeb59a
Create Date: 2026-10-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "14db60023e88"
down_revision: Union[str, Sequence[str], None] = "a2d16ffeb59a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen here rather than imported: a migration must keep meaning what it
# meant when it ran, whatever the service's table later becomes.
_MODES = {
    ("row", "identified"): "raw",
    ("row", "deidentified"): "anonymized",
    ("aggregated", "deidentified"): "summarized",
}
_PAIRS = {mode: pair for pair, mode in _MODES.items()}
_VALID = {
    ("peer_reviewer", "while_ongoing"): {"raw"},
    ("peer_reviewer", "after_release"): {None, "raw"},
    ("reviewee", "while_ongoing"): {None},
    ("reviewee", "after_release"): {None, "raw", "anonymized", "summarized"},
    ("observer", "while_ongoing"): {None, "summarized"},
    ("observer", "after_release"): {None, "raw", "anonymized", "summarized"},
}


def _mode(granularity, identification):
    """The stored pair's mode; None for off; "invalid" for anything else."""
    if granularity is None and identification is None:
        return None
    return _MODES.get((granularity, identification), "invalid")


def _normalized(audience, window, mode):
    valid = _VALID[(audience, window)]
    if mode in valid:
        return mode
    if len(valid) == 1:
        return next(iter(valid))
    if (audience, window) == ("observer", "while_ongoing") and mode in (
        "raw",
        "anonymized",
    ):
        return "summarized"
    return None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, audience, while_ongoing_granularity, "
            "while_ongoing_identification, after_release_granularity, "
            "after_release_identification FROM instrument_view_policies"
        )
    ).fetchall()
    for row in rows:
        if (row.audience, "while_ongoing") not in _VALID:
            continue
        params = {"id": row.id}
        changed = False
        for window, g, i in (
            ("while_ongoing", row.while_ongoing_granularity,
             row.while_ongoing_identification),
            ("after_release", row.after_release_granularity,
             row.after_release_identification),
        ):
            mode = _mode(g, i)
            target = _normalized(row.audience, window, mode)
            pair = _PAIRS[target] if target is not None else (None, None)
            params[f"{window}_g"], params[f"{window}_i"] = pair
            if pair != (g, i):
                changed = True
        if changed:
            bind.execute(
                sa.text(
                    "UPDATE instrument_view_policies SET "
                    "while_ongoing_granularity = :while_ongoing_g, "
                    "while_ongoing_identification = :while_ongoing_i, "
                    "after_release_granularity = :after_release_g, "
                    "after_release_identification = :after_release_i "
                    "WHERE id = :id"
                ),
                params,
            )


def downgrade() -> None:
    pass
