"""How much of a reviewer a Raw released view names.

ProfileLink updates Item 2 rung 2 (``guide/profilelink_updates.md``):
``instrument_view_policies.after_release_reviewer_identity`` on the
reviewee and observer rows. ``name`` drops the email (and, in the
observer download, the reviewer tags); ``name_email`` is Raw as it was;
``name_email_profile`` adds the reviewer's ``ProfileLink``. Anonymized
never reads it. Until rung 3, only the Settings CSV sets it.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    Reviewer,
    ReviewSession,
)
from app.services import visibility_policies as vp
from app.services.instruments import copy_view_policies

from .test_observer_collation_body import (
    _MATH_RULE,
    _add_observer,
    _make_session,
    _seed_one_instrument,
)
from .test_reviewee_results_body import (
    _enable_reviewee_after_release_raw,
    _operator_user,
    _seed_and_activate,
    _seed_submitted_responses,
)

LINK = "https://example.edu/rae"


@pytest.fixture
def carol() -> AuthenticatedUser:
    """The reviewee ``_seed_and_activate`` rosters."""
    return AuthenticatedUser(
        principal_id="carol-oid",
        email="carol@example.edu",
        name="Carol Reviewee",
        provider="aad",
    )


# ── The service ──────────────────────────────────────────────────────


def test_an_unset_or_unknown_level_reads_as_name_and_email() -> None:
    assert vp.reviewer_identity(None) == "name_email"
    row = InstrumentViewPolicy(audience="reviewee")
    assert vp.reviewer_identity(row) == "name_email"
    row.after_release_reviewer_identity = "everything"
    assert vp.reviewer_identity(row) == "name_email"
    row.after_release_reviewer_identity = "name"
    assert vp.reviewer_identity(row) == "name"


def test_a_level_is_refused_off_the_list_or_on_the_reviewer_row() -> None:
    for audience in ("reviewee", "observer"):
        for level in (None, *vp.REVIEWER_IDENTITY_LEVELS):
            vp.validate_reviewer_identity(audience, level)
    with pytest.raises(vp.VisibilityPolicyError):
        vp.validate_reviewer_identity("reviewee", "everything")
    with pytest.raises(vp.VisibilityPolicyError):
        vp.validate_reviewer_identity("peer_reviewer", "name")
    vp.validate_reviewer_identity("peer_reviewer", None)


# ── The reviewee's results page ──────────────────────────────────────


def _results(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
    *,
    code: str,
    level: str | None,
    mode: str = "raw",
) -> str:
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code=code)
    _seed_submitted_responses(db, review_session)
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    policy = vp.list_for_instrument(db, instrument.id)["reviewee"]
    granularity, identification = vp.encode_mode(mode)
    policy.after_release_granularity = granularity
    policy.after_release_identification = identification
    policy.after_release_reviewer_identity = level
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewer.profile_link = LINK
    db.commit()
    response = make_client(carol).get(f"/me/sessions/{review_session.id}/results")
    assert response.status_code == 200, response.text
    assert "Solid work." in response.text
    return response.text


@pytest.mark.parametrize(
    ("level", "email", "link"),
    [
        (None, True, False),
        ("name", False, False),
        ("name_email", True, False),
        ("name_email_profile", True, True),
    ],
)
def test_the_raw_identity_cell_follows_the_level(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
    level: str | None,
    email: bool,
    link: bool,
) -> None:
    body = _results(
        db, alice, carol, make_client, code=f"rid-{level or 'unset'}", level=level
    )
    assert "<strong>Rae</strong>" in body
    assert ("rae@example.edu" in body) is email
    assert (f'href="{LINK}"' in body) is link
    if link:
        assert f'<a href="{LINK}" target="_blank" rel="noopener">link</a>' in body


def test_anonymized_never_reads_the_level(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    body = _results(
        db,
        alice,
        carol,
        make_client,
        code="rid-anon",
        level="name_email_profile",
        mode="anonymized",
    )
    assert "rae@example.edu" not in body
    assert LINK not in body
    assert "<strong>Rae</strong>" not in body


# ── The observer's download ──────────────────────────────────────────


def _download(client: TestClient, db: Session, *, code: str, level: str | None, identification: str = "identified") -> list[list[str]]:
    review_session = _make_session(client, db, code=code)
    seeded = _seed_one_instrument(
        db, review_session, while_ongoing_identification=identification
    )
    seeded["reviewer"].profile_link = LINK
    policy = vp.list_for_instrument(db, seeded["instrument"].id)["observer"]
    policy.after_release_reviewer_identity = level
    db.commit()
    _add_observer(db, review_session, email="alice@example.edu", cohort_rule=_MATH_RULE)
    response = client.get(
        f"/me/sessions/{review_session.id}/collation/instruments/"
        f"{seeded['instrument'].id}.csv"
    )
    assert response.status_code == 200, response.text
    rows = list(csv.reader(io.StringIO(response.text)))
    start = next(i for i, row in enumerate(rows) if row and row[0] == "ReviewerName")
    return rows[start:]


def test_name_only_blanks_the_email_and_the_reviewer_tags(
    client: TestClient, db: Session
) -> None:
    header, row = _download(client, db, code="rid-csv-name", level="name")
    assert header[:2] == ["ReviewerName", "ReviewerEmail"]
    assert "ReviewerProfileLink" not in header
    assert row[0] == "Rev"
    assert row[1:5] == ["", "", "", ""]
    # The reviewee's side is not the reviewer's identity: it stays.
    assert row[5:8] == ["Ree", "ree@x", "mathcohort"]


@pytest.mark.parametrize("level", [None, "name_email"])
def test_name_and_email_is_raw_as_it_was(
    client: TestClient, db: Session, level: str | None
) -> None:
    header, row = _download(
        client, db, code=f"rid-csv-{level or 'unset'}", level=level
    )
    assert "ReviewerProfileLink" not in header
    assert row[:3] == ["Rev", "rev@x", "mathcohort"]


def test_the_profile_level_adds_a_column_after_the_email(
    client: TestClient, db: Session
) -> None:
    header, row = _download(
        client, db, code="rid-csv-profile", level="name_email_profile"
    )
    assert header[:3] == ["ReviewerName", "ReviewerEmail", "ReviewerProfileLink"]
    assert row[:4] == ["Rev", "rev@x", LINK, "mathcohort"]
    assert len(row) == len(header)


def test_an_anonymized_download_ignores_the_level(
    client: TestClient, db: Session
) -> None:
    header, row = _download(
        client,
        db,
        code="rid-csv-anon",
        level="name_email_profile",
        identification="deidentified",
    )
    assert "ReviewerProfileLink" not in header
    assert LINK not in ",".join(row)
    assert row[1] == ""


# ── Writers that carry it ────────────────────────────────────────────


def _session_with_policy(
    client: TestClient, db: Session, code: str
) -> tuple[ReviewSession, Instrument, InstrumentViewPolicy]:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().first()
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={"reviewee_after_release_mode": "raw"},
        follow_redirects=False,
    )
    policy = vp.list_for_instrument(db, instrument.id)["reviewee"]
    policy.after_release_reviewer_identity = "name"
    db.commit()
    return review_session, instrument, policy


def test_the_cards_save_keeps_a_stored_level(
    client: TestClient, db: Session
) -> None:
    review_session, instrument, policy = _session_with_policy(client, db, "rid-keep")
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={"reviewee_after_release_mode": "anonymized"},
        follow_redirects=False,
    )
    db.refresh(policy)
    assert policy.after_release_identification == "deidentified"
    assert policy.after_release_reviewer_identity == "name"


def test_a_copy_carries_the_level(client: TestClient, db: Session) -> None:
    from app.db.models import User

    review_session, instrument, _ = _session_with_policy(client, db, "rid-copy")
    replica = Instrument(session_id=review_session.id, name="Replica", order=9)
    db.add(replica)
    db.flush()
    actor = db.execute(select(User).where(User.email == "alice@example.edu")).scalar_one()
    copy_view_policies(db, review_session, instrument, replica, actor)
    db.commit()
    copied = vp.list_for_instrument(db, replica.id)["reviewee"]
    assert copied.after_release_reviewer_identity == "name"
