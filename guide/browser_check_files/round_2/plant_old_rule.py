"""Store a Band 1 rule the card can no longer save, for Part 6 of this
folder's README: no route stores one any more, so a fresh database cannot
hold the case without writing it directly.

Run from the repository root, with the virtualenv active, against the
database `.env` names (uvicorn can keep running):

    python guide/browser_check_files/round_2/plant_old_rule.py r-pairs same-side
    python guide/browser_check_files/round_2/plant_old_rule.py r-pairs retired

The session's first instrument must already have a saved Band 1 rule (Part
6 saves one). ``same-side`` makes Who is being reviewed compare two
relationship tags; ``retired`` makes Who does the review filter on a
person-level relationship tag, a field retired on 2026-10-18.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from sqlalchemy import select  # noqa: E402

from app.db.models import Instrument, ReviewSession, SessionRuleSet  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402

RULES = {
    "same-side": {
        "id": "link2",
        "field": "pair_context.tag1",
        "operator": "same_as",
        "operand": "pair_context.tag2",
    },
    "retired": {
        "id": "link1",
        "field": "reviewer.pair_tag1",
        "operator": "equals",
        "operand": "North",
    },
}


def main(code: str, case: str) -> None:
    rule = RULES[case]
    with get_sessionmaker()() as db:
        review_session = db.execute(
            select(ReviewSession).where(ReviewSession.code == code)
        ).scalar_one()
        instrument = db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.session_seq)
        ).scalars().first()
        if instrument is None or instrument.rule_set_id is None:
            sys.exit("Save a Band 1 rule on the session's first instrument first.")
        rule_set = db.get(SessionRuleSet, instrument.rule_set_id)
        rule_set.rules_json = [
            {
                "id": rule["id"],
                "enabled": True,
                "kind": "COMPOSITE",
                "op": "AND",
                "rules": [
                    {
                        "id": f"{rule['id']}-r0",
                        "enabled": True,
                        "kind": "MATCH",
                        "predicate": {
                            "field": rule["field"],
                            "operator": rule["operator"],
                            "operand": rule["operand"],
                            "case_sensitive": False,
                        },
                    }
                ],
            }
        ]
        # A rule saved through the card marked its link touched; an
        # untouched link renders Not set, and its next Save drops the rule.
        instrument.band1_touched_links = sorted(
            set(instrument.band1_touched_links or []) | {rule["id"]}
        )
        db.commit()
    print(f"{code}: stored the {case} rule on {instrument.short_label or 'Instrument_1'}.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in RULES:
        sys.exit(f"usage: plant_old_rule.py <session code> {{{'|'.join(RULES)}}}")
    main(sys.argv[1], sys.argv[2])
