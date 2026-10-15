"""The database refuses a visibility cell the per-cell rule refuses

``instrument_view_policies`` gains ``ck_view_policy_cell``: each window's
``(granularity, identification)`` pair is off (both NULL) or one of the
three modes, and each ``(audience, window)`` cell allows only the modes
``spec/visibility_policy.md`` §3.1 lists. The Band 3 editor and the
Settings import already refuse anything else; the constraint refuses it
from any other path too, so the Visibility grid audit card, which looked
for such rows after the fact, can retire (``guide/archive/visibility_cell_constraint.md``).

Before adding it, the upgrade re-applies ``14db60023e88``'s
normalization under the same ruling (author, 2026-10-05: each illegal
cell becomes the nearest legal one, never wider than what it granted),
so a stray row cannot stop the constraint applying, and it logs how many
rows that rewrote, by id — on real data, the answer the audit card was going to
be read for. A row whose audience is none of the three stops the upgrade
instead: nothing reads such a row, and deleting it is not this
migration's call.

The downgrade drops the constraint and leaves the data as it is: every
normalized value is legal before and after.

Revision ID: e5c1a9d3b7f2
Revises: c4a8e2f6d1b3
Create Date: 2026-10-15

"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5c1a9d3b7f2"
down_revision: Union[str, Sequence[str], None] = "c4a8e2f6d1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_log = logging.getLogger("alembic.runtime.migration")

# Frozen here rather than imported: a migration must keep meaning what it
# meant when it ran, whatever the model or the service later becomes.
_MODES = {
    ("row", "identified"): "raw",
    ("row", "deidentified"): "anonymized",
    ("aggregated", "deidentified"): "summarized",
}
_PAIRS = {mode: pair for pair, mode in _MODES.items()}
_VALID = {
    ("peer_reviewer", "while_ongoing"): ("raw",),
    ("peer_reviewer", "after_release"): (None, "raw"),
    ("reviewee", "while_ongoing"): (None,),
    ("reviewee", "after_release"): (None, "raw", "anonymized", "summarized"),
    ("observer", "while_ongoing"): (None, "summarized"),
    ("observer", "after_release"): (None, "raw", "anonymized", "summarized"),
}
_AUDIENCES = ("peer_reviewer", "reviewee", "observer")
_WINDOWS = ("while_ongoing", "after_release")


def _window_sql(window: str, modes) -> str:
    terms = []
    for mode in modes:
        if mode is None:
            terms.append(
                f"({window}_granularity IS NULL AND {window}_identification IS NULL)"
            )
        else:
            granularity, identification = _PAIRS[mode]
            # COALESCE: a CHECK passes on NULL, so `=` against a NULL
            # column must read false, not unknown.
            terms.append(
                f"(COALESCE({window}_granularity, '') = '{granularity}' "
                f"AND COALESCE({window}_identification, '') = '{identification}')"
            )
    return "(" + " OR ".join(terms) + ")"


_CHECK = " OR ".join(
    f"(audience = '{audience}' "
    f"AND {_window_sql('while_ongoing', _VALID[(audience, 'while_ongoing')])} "
    f"AND {_window_sql('after_release', _VALID[(audience, 'after_release')])})"
    for audience in _AUDIENCES
)


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
        return valid[0]
    if (audience, window) == ("observer", "while_ongoing") and mode in (
        "raw",
        "anonymized",
    ):
        return "summarized"
    return None


def _normalize(bind) -> list[int]:
    rows = bind.execute(
        sa.text(
            "SELECT id, audience, while_ongoing_granularity, "
            "while_ongoing_identification, after_release_granularity, "
            "after_release_identification FROM instrument_view_policies"
        )
    ).fetchall()
    unknown = sorted(row.id for row in rows if row.audience not in _AUDIENCES)
    if unknown:
        raise RuntimeError(
            "instrument_view_policies rows with an unknown audience stop "
            f"ck_view_policy_cell applying: ids {unknown}. Nothing reads "
            "them; delete them by hand, then upgrade again."
        )
    rewritten: list[int] = []
    for row in rows:
        params = {"id": row.id}
        changed = False
        for window, g, i in (
            ("while_ongoing", row.while_ongoing_granularity,
             row.while_ongoing_identification),
            ("after_release", row.after_release_granularity,
             row.after_release_identification),
        ):
            target = _normalized(row.audience, window, _mode(g, i))
            pair = _PAIRS[target] if target is not None else (None, None)
            params[f"{window}_g"], params[f"{window}_i"] = pair
            if pair != (g, i):
                changed = True
        if changed:
            rewritten.append(row.id)
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
    return rewritten


def upgrade() -> None:
    rewritten = _normalize(op.get_bind())
    _log.info(
        "ck_view_policy_cell: normalized %d instrument_view_policies row(s) "
        "before adding the constraint%s",
        len(rewritten),
        f": ids {rewritten}" if rewritten else ".",
    )
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.create_check_constraint("ck_view_policy_cell", _CHECK)


def downgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.drop_constraint("ck_view_policy_cell", type_="check")
