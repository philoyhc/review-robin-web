"""Integration coverage for the participant_tokens extract +
its bundle inclusion (clean_up item 15).

Operator-side deanonymization key: every Reviewer + Reviewee
with their per-session opaque token. Mirrors the gating used
by the per-observer Observers extract (gated on
``observers_enabled``) since the tokens have no consumer
outside the observer-side Anonymized output today.
"""

from __future__ import annotations

import csv
import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services.participant_tokens import ParticipantTokenizer


def _make_session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    observers_enabled: bool = True,
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Tok", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.observers_enabled = observers_enabled
    db.commit()
    return review_session


def _seed_one_reviewer_and_reviewee(
    db: Session, review_session: ReviewSession
) -> tuple[Reviewer, Reviewee]:
    rev = Reviewer(
        session_id=review_session.id, name="Rev One", email="rev1@x.edu"
    )
    ree = Reviewee(
        session_id=review_session.id,
        name="Ree One",
        email_or_identifier="ree1@x.edu",
    )
    db.add_all([rev, ree])
    db.commit()
    db.refresh(rev)
    db.refresh(ree)
    return rev, ree


# ---------------------------------------------------------------------------
# Per-row export route
# ---------------------------------------------------------------------------


def test_export_participant_tokens_csv_lists_reviewers_then_reviewees(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="tok-csv")
    rev, ree = _seed_one_reviewer_and_reviewee(db, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/participant_tokens.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        f'filename="{review_session.code}_participant_tokens.csv"'
        in response.headers["content-disposition"]
    )

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["Role", "Name", "Email", "Token"]

    # Reviewers block first, then reviewees.
    tokenizer = ParticipantTokenizer(review_session)
    assert rows[1] == [
        "Reviewer",
        "Rev One",
        "rev1@x.edu",
        tokenizer.token("reviewer", rev.id),
    ]
    assert rows[2] == [
        "Reviewee",
        "Ree One",
        "ree1@x.edu",
        tokenizer.token("reviewee", ree.id),
    ]


def test_export_participant_tokens_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="tok-audit")
    _seed_one_reviewer_and_reviewee(db, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/participant_tokens.csv"
    )
    assert response.status_code == 200

    ext_events = (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type
                == "session.participant_tokens_extracted"
            )
        )
        .scalars()
        .all()
    )
    assert len(ext_events) == 1
    detail = ext_events[0].detail
    assert detail["counts"] == {"rows": 2}


def test_export_route_works_even_when_observers_disabled(
    client: TestClient, db: Session
) -> None:
    """The route itself doesn't gate on ``observers_enabled``;
    only the chrome that surfaces the button does. A deep-link
    deanonymization lookup still works if the toggle briefly
    drops."""
    review_session = _make_session(
        client, db, code="tok-no-obs", observers_enabled=False
    )
    _seed_one_reviewer_and_reviewee(db, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/participant_tokens.csv"
    )
    assert response.status_code == 200


def test_export_route_byte_stable_across_calls(
    client: TestClient, db: Session
) -> None:
    """The token chain is deterministic on (env salt, session
    created_at, role, individual_id); two back-to-back calls
    produce the same bytes."""
    review_session = _make_session(client, db, code="tok-stable")
    _seed_one_reviewer_and_reviewee(db, review_session)

    a = client.get(
        f"/operator/sessions/{review_session.id}/export/participant_tokens.csv"
    ).text
    b = client.get(
        f"/operator/sessions/{review_session.id}/export/participant_tokens.csv"
    ).text
    assert a == b


# ---------------------------------------------------------------------------
# Responses-bundle inclusion (Extract data ``Zip all`` button)
# ---------------------------------------------------------------------------


def test_responses_bundle_includes_token_keys_by_default(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="tok-bundle-on")
    _seed_one_reviewer_and_reviewee(db, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses_bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert (
        f"{review_session.code}_participant_tokens.csv"
        in archive.namelist()
    )


def test_responses_bundle_omits_token_keys_when_tokens_param_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="tok-bundle-off")
    _seed_one_reviewer_and_reviewee(db, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/export/responses_bundle.zip?tokens=0"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert all(
        "participant_tokens" not in name for name in archive.namelist()
    )


def test_responses_bundle_omits_token_keys_when_observers_disabled(
    client: TestClient, db: Session
) -> None:
    """Even with the chip default-on, when ``observers_enabled``
    is off the bundle skips the tokens — the chrome that drives
    the chip wouldn't render either."""
    review_session = _make_session(
        client, db, code="tok-bundle-no-obs", observers_enabled=False
    )
    _seed_one_reviewer_and_reviewee(db, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses_bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert all(
        "participant_tokens" not in name for name in archive.namelist()
    )


# ---------------------------------------------------------------------------
# Extract data page chrome
# ---------------------------------------------------------------------------


def test_extract_data_page_renders_token_keys_chrome_when_observers_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="tok-page-on")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    # Intro-card chip rendered (rather than just the JS literal).
    assert (
        'data-extract-all-chip="token-keys"\n' in body
        or 'data-extract-all-chip="token-keys"\r\n' in body
        or 'data-extract-all-chip="token-keys" ' in body
    )
    # Half-width card + Download token keys button.
    assert 'id="extract-data-token-keys"' in body
    assert "Download token keys" in body
    assert (
        f"/operator/sessions/{review_session.id}/export/participant_tokens.csv"
        in body
    )


def test_extract_data_page_omits_token_keys_chrome_when_observers_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="tok-page-off", observers_enabled=False
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    # The chip + card don't render; the JS still references the
    # chip selector defensively but null-checks before use.
    assert 'id="extract-data-token-keys"' not in body
    assert "Download token keys" not in body
