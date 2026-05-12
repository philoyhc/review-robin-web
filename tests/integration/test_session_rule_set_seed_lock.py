"""Tests for the seeded-SessionRuleSet spec-lock behaviour.

Symmetric to the RTD spec-lock model. Seeded session copies
(``is_seeded=True``, materialised from ``SEEDED_RULE_SETS`` on
session create) refuse:

- Update in place (Save with the same ``rule_set_id``).
- Rename.
- Delete.
- Save-to-library.

The Copy action stays available so operators customise via
Copy → Save-As, which writes a fresh row with
``is_seeded=False`` that is fully editable / deletable.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionRuleSet
from app.services.rules import session_library


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "SeedLock", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_row(
    db: Session, *, session_id: int, name: str = "Full Matrix"
) -> SessionRuleSet:
    return db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == name,
        )
    ).scalar_one()


def _builder_url(session_id: int, *parts: str) -> str:
    base = (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )
    return base if not parts else base + "/" + "/".join(parts)


# --- materialisation flags seeded rows --------------------------------------


def test_materialise_seed_rule_sets_writes_is_seeded_true(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-mat")
    rows = list(
        db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    )
    assert rows
    assert all(row.is_seeded for row in rows), (
        "Every materialised seed must land with is_seeded=True"
    )


# --- service-layer guards ---------------------------------------------------


def test_update_session_rule_set_in_place_refuses_seed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-upd")
    seed = _seed_row(db, session_id=review_session.id)

    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetSchema,
    )

    schema = RuleSetSchema(
        id=seed.id,
        name=seed.name,
        description=seed.description,
        scope="personal",  # type: ignore[arg-type]
        combinator=Combinator(seed.combinator),
        rules=[],
        options=RuleSetOptions(
            excludeSelfReviews=seed.exclude_self_reviews, seed=seed.seed
        ),
    )
    with pytest.raises(session_library.SessionRuleSetLockedError):
        session_library.update_session_rule_set_in_place(
            db,
            session_rule_set=seed,
            rule_set_schema=schema,
            actor=review_session.created_by_user,
            correlation_id="c",
        )


def test_rename_session_rule_set_refuses_seed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-ren")
    seed = _seed_row(db, session_id=review_session.id)
    with pytest.raises(session_library.SessionRuleSetLockedError):
        session_library.rename_session_rule_set(
            db,
            session_rule_set=seed,
            new_name="Renamed",
            new_description=None,
            actor=review_session.created_by_user,
            correlation_id="c",
        )


def test_delete_session_rule_set_refuses_seed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-del")
    seed = _seed_row(db, session_id=review_session.id)
    with pytest.raises(session_library.SessionRuleSetLockedError):
        session_library.delete_session_rule_set(
            db,
            session_rule_set=seed,
            actor=review_session.created_by_user,
            correlation_id="c",
        )


def test_save_to_library_refuses_seed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-s2l")
    seed = _seed_row(db, session_id=review_session.id)
    with pytest.raises(session_library.SessionRuleSetLockedError):
        session_library.save_to_library(
            db,
            session_rule_set=seed,
            actor=review_session.created_by_user,
            correlation_id="c",
        )


# --- route-layer 409 conversions --------------------------------------------


def test_route_save_in_place_on_seed_returns_409(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-rt-save")
    seed = _seed_row(db, session_id=review_session.id)
    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "rule_set_id": seed.id,
            "name": seed.name,
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_route_delete_on_seed_returns_409(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-rt-del")
    seed = _seed_row(db, session_id=review_session.id)
    response = client.post(
        _builder_url(review_session.id, "delete"),
        data={"rule_set_id": seed.id, "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_route_save_to_library_on_seed_returns_409(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sl-rt-s2l")
    seed = _seed_row(db, session_id=review_session.id)
    response = client.post(
        _builder_url(review_session.id, "save-to-library"),
        data={"rule_set_id": seed.id},
        follow_redirects=False,
    )
    assert response.status_code == 409


# --- Copy → Save-As path still works ---------------------------------------


def test_copy_seed_then_save_as_creates_editable_personal(
    client: TestClient, db: Session
) -> None:
    """Operators customise a seed by Copy → Save-As; the resulting
    row has ``is_seeded=False`` and the full edit / delete surface."""
    review_session = _make_session(client, db, code="sl-copy")
    seed = _seed_row(db, session_id=review_session.id)

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": seed.id,
            "name": "My Customized Matrix",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            "auto_name": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    customised = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "My Customized Matrix",
        )
    ).scalar_one()
    assert customised.is_seeded is False
    # Delete now works on the non-seeded copy.
    response = client.post(
        _builder_url(review_session.id, "delete"),
        data={"rule_set_id": customised.id, "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
