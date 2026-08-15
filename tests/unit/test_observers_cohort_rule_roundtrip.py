"""18P PR B — the observers CSV round-trips ``Observer.cohort_rule``.

``serialize_observers`` emits a compact-JSON ``CohortRule`` cell;
``parse_observer_csv`` reads it back and re-validates through
``CohortRuleSet`` (bad JSON / bad shape is a blocking error).
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession, User
from app.schemas.observer_cohort_rule import CohortRuleSet
from app.services.csv_imports import parse_observer_csv
from app.services.extracts.observers_extract import HEADER, serialize_observers

_COHORT: dict[str, object] = {
    "combinator": "AND",
    "rules": [
        {
            "field": "reviewer.tag1",
            "op": "IS",
            "operand_value": "Team A",
            "operand_tag": "",
        }
    ],
}


def _session(db: Session, code: str = "obs-cr") -> ReviewSession:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(),
        code=code,
        created_by_user_id=user.id,
        observers_enabled=True,
    )
    db.add(review_session)
    db.flush()
    return review_session


def _csv_bytes(rows: list[tuple[str, ...]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def test_observer_cohort_rule_round_trips(db: Session) -> None:
    review_session = _session(db)
    validated = CohortRuleSet.model_validate(_COHORT).model_dump(mode="json")
    db.add(
        Observer(
            session_id=review_session.id,
            email="obs@example.edu",
            display_name="Obs",
            cohort_rule=validated,
        )
    )
    db.add(
        Observer(
            session_id=review_session.id,
            email="plain@example.edu",
        )
    )
    db.flush()

    rows = list(serialize_observers(db, review_session))
    result = parse_observer_csv(_csv_bytes(rows))
    assert result.issues == []
    by_email = {r.email: r for r in result.rows}
    assert by_email["obs@example.edu"].cohort_rule == validated
    assert by_email["plain@example.edu"].cohort_rule is None


def test_observer_malformed_cohort_rule_json_rejected(db: Session) -> None:
    rows = [HEADER, ("obs@example.edu", "Obs", "", "active", "{not json")]
    result = parse_observer_csv(_csv_bytes(rows))
    assert result.rows == []
    assert any(issue.field == "CohortRule" for issue in result.issues)


def test_observer_invalid_cohort_rule_shape_rejected(db: Session) -> None:
    bad = (
        '{"combinator":"AND","rules":'
        '[{"field":"nope","op":"IS","operand_value":"x"}]}'
    )
    rows = [HEADER, ("obs@example.edu", "Obs", "", "active", bad)]
    result = parse_observer_csv(_csv_bytes(rows))
    assert result.rows == []
    assert any(issue.field == "CohortRule" for issue in result.issues)
