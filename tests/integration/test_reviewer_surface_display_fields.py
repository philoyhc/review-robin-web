from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from ._full_matrix import full_matrix_seed_id
from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    Reviewee,
    ReviewSession,
)


def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_ident}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # 15D PR 6b: pair_context lives on the relationships table now.
    # Upload via the per-entity Relationships CSV; the manual
    # assignments CSV's PairContext columns are silently ignored
    # post-15D.
    operator_client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    f"ReviewerEmail,RevieweeEmail,"
                    f"PairContextTag1,PairContextTag2,PairContextTag3\n"
                    f"{reviewer_email},{reviewee_ident},"
                    f"morning,roomA,cohortX\n"
                ).encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": full_matrix_seed_id(db),
            "exclude_self_review": "true",
        },
        follow_redirects=False,
    )
    return review_session


def _activate(
    operator_client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
    response = operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def test_pair_context_renders_as_separate_columns(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="dfix-cols",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    body = response.text
    assert "<th>Pair context 1</th>" in body
    assert "<th>Pair context 2</th>" in body
    assert "<th>Pair context 3</th>" in body
    assert "morning" in body
    assert "roomA" in body


def test_pair_context_no_longer_renders_inside_identity_cell(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="dfix-noinl",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "P1:" not in response.text
    assert "P2:" not in response.text


def test_profile_link_renders_as_anchor(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="dfix-prof",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()
    reviewee.profile_link = "https://example.edu/carol"
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="",
            source_type="reviewee",
            source_field="profile_link",
            order=10,
            visible=True,
        )
    )
    db.commit()

    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    body = response.text
    assert 'class="rs-narrow">Profile</th>' in body
    assert '<a href="https://example.edu/carol">View</a>' in body


def test_profile_link_empty_renders_empty_cell(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="dfix-empty",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="",
            source_type="reviewee",
            source_field="profile_link",
            order=10,
            visible=True,
        )
    )
    db.commit()

    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert 'class="rs-narrow">Profile</th>' in response.text
    assert "https://example.edu" not in response.text
