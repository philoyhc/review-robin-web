"""The Band 2 card's reviewer-identity chip.

ProfileLink updates Item 2 (``guide/profilelink_updates.md``): beside the
Reviewees and Observers Responses released cells, shown only when the
cell is Raw, a cycle chip over ``Name only`` / ``Name, email`` and, when
some reviewer has a ProfileLink, ``Name, email, profile``. The card's
Save stores it; the locked table and the reviewer's own copy of the card
show it as a plain pill after a Raw Reviewees cell.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, Reviewer, ReviewSession
from app.services import visibility_policies as vp

from .test_reviewee_results_body import (
    _enable_reviewee_after_release_raw,
    _operator_user,
    _seed_and_activate,
)


def _session(client: TestClient, db: Session, code: str) -> tuple[int, int]:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    return session.id, instrument.id


def _save(client: TestClient, session_id: int, instrument_id: int, **data: str) -> None:
    response = client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/fields/save",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text


def _span(body: str, attr: str) -> str:
    match = re.search(rf"<span [^>]*{re.escape(attr)}[^>]*>[^<]*</span>", body)
    assert match, attr
    return " ".join(match.group(0).split())


def _page(client: TestClient, session_id: int) -> str:
    return client.get(f"/operator/sessions/{session_id}/instruments").text


def test_the_chip_hides_unless_the_released_cell_is_raw(
    client: TestClient, db: Session
) -> None:
    session_id, _ = _session(client, db, "vp-ident-off")
    body = _page(client, session_id)
    for attr in (
        'data-new-model-vp-identity="reviewee"',
        'data-new-model-vp-identity="observer"',
        'data-new-model-vp-identity-preview="reviewee"',
    ):
        pill = _span(body, attr)
        assert " hidden" in pill, pill
        assert pill.endswith(">Name, email</span>"), pill
    # A reviewer reading their own work is identified to no one.
    assert 'data-new-model-vp-identity="peer_reviewer"' not in body
    assert 'name="peer_reviewer_after_release_reviewer_identity"' not in body


def test_the_chip_is_a_cycle_control_beside_a_raw_cell(
    client: TestClient, db: Session
) -> None:
    session_id, instrument_id = _session(client, db, "vp-ident-raw")
    _save(
        client,
        session_id,
        instrument_id,
        reviewee_after_release_mode="raw",
        observer_after_release_mode="anonymized",
    )
    body = _page(client, session_id)
    chip = _span(body, 'data-new-model-vp-identity="reviewee"')
    assert " hidden" not in chip, chip
    assert "tag-chip" in chip and 'role="button"' in chip and 'tabindex="0"' in chip
    assert "newModelCycleIdentity(this)" in chip
    assert "newModelChipKey(this, event)" in chip
    # No reviewer has a link yet: the profile level isn't offered.
    assert 'data-new-model-vp-identity-slugs="name|name_email"' in chip
    assert " hidden" in _span(body, 'data-new-model-vp-identity="observer"')
    assert " hidden" not in _span(body, 'data-new-model-vp-identity-preview="reviewee"')
    # Every identity pill widens its table's released column
    # (base.html ``table.vp-grid:has(.vp-identity-pill...)``): the
    # editor's two chips and the locked table's pill.
    for attr in (
        'data-new-model-vp-identity="reviewee"',
        'data-new-model-vp-identity="observer"',
        'data-new-model-vp-identity-preview="reviewee"',
    ):
        assert "vp-identity-pill" in _span(body, attr), attr
    assert body.count('<table class="vp-grid"') == 2


def test_the_profile_level_is_offered_once_a_reviewer_has_a_link(
    client: TestClient, db: Session
) -> None:
    session_id, instrument_id = _session(client, db, "vp-ident-link")
    _save(client, session_id, instrument_id, reviewee_after_release_mode="raw")
    db.add(
        Reviewer(
            session_id=session_id,
            name="Rae",
            email="rae@example.edu",
            profile_link="https://example.edu/rae",
        )
    )
    db.commit()
    chip = _span(_page(client, session_id), 'data-new-model-vp-identity="reviewee"')
    assert (
        'data-new-model-vp-identity-slugs="name|name_email|name_email_profile"'
        in chip
    )


def test_save_stores_the_level_and_the_pills_show_it(
    client: TestClient, db: Session
) -> None:
    session_id, instrument_id = _session(client, db, "vp-ident-save")
    _save(
        client,
        session_id,
        instrument_id,
        reviewee_after_release_mode="raw",
        reviewee_after_release_reviewer_identity="name",
        observer_after_release_mode="raw",
        observer_after_release_reviewer_identity="name_email_profile",
    )
    policies = vp.list_for_instrument(db, instrument_id)
    assert policies["reviewee"].after_release_reviewer_identity == "name"
    assert policies["observer"].after_release_reviewer_identity == "name_email_profile"
    body = _page(client, session_id)
    assert _span(body, 'data-new-model-vp-identity="reviewee"').endswith(">Name only</span>")
    assert _span(body, 'data-new-model-vp-identity-preview="reviewee"').endswith(
        ">Name only</span>"
    )
    # A stored profile level renders as itself with no links, so it can
    # be cycled off; the cycle offers only the first two.
    observer = _span(body, 'data-new-model-vp-identity="observer"')
    assert observer.endswith(">Name, email, profile</span>")
    assert 'data-new-model-vp-identity-slugs="name|name_email"' in observer
    assert re.search(
        r'name="reviewee_after_release_reviewer_identity"\s*'
        r'data-new-model-vp-identity-input="reviewee"\s*value="name"',
        body,
    )


def test_an_empty_input_clears_the_level_and_a_missing_one_keeps_it(
    client: TestClient, db: Session
) -> None:
    session_id, instrument_id = _session(client, db, "vp-ident-clear")
    _save(
        client,
        session_id,
        instrument_id,
        reviewee_after_release_mode="raw",
        reviewee_after_release_reviewer_identity="name",
    )
    _save(client, session_id, instrument_id, reviewee_after_release_mode="raw")
    policy = vp.list_for_instrument(db, instrument_id)["reviewee"]
    db.refresh(policy)
    assert policy.after_release_reviewer_identity == "name"
    _save(
        client,
        session_id,
        instrument_id,
        reviewee_after_release_mode="raw",
        reviewee_after_release_reviewer_identity="",
    )
    db.refresh(policy)
    assert policy.after_release_reviewer_identity is None


def test_a_corrupt_stored_level_does_not_block_save(
    client: TestClient, db: Session
) -> None:
    """A stored value that isn't a level (only a direct database edit
    can write one) renders as the default and goes out empty, so the
    card's ordinary Save still works (Codex on #2966)."""
    session_id, instrument_id = _session(client, db, "vp-ident-corrupt")
    _save(client, session_id, instrument_id, reviewee_after_release_mode="raw")
    policy = vp.list_for_instrument(db, instrument_id)["reviewee"]
    policy.after_release_reviewer_identity = "everything"
    db.commit()
    body = _page(client, session_id)
    assert _span(body, 'data-new-model-vp-identity="reviewee"').endswith(">Name, email</span>")
    match = re.search(
        r'name="reviewee_after_release_reviewer_identity"\s*'
        r'data-new-model-vp-identity-input="reviewee"\s*value="([^"]*)"',
        body,
    )
    assert match and match.group(1) == ""
    _save(
        client,
        session_id,
        instrument_id,
        reviewee_after_release_mode="anonymized",
        reviewee_after_release_reviewer_identity=match.group(1),
    )
    db.refresh(policy)
    assert policy.after_release_identification == "deidentified"
    assert policy.after_release_reviewer_identity is None


def test_save_refuses_a_level_that_is_not_one(
    client: TestClient, db: Session
) -> None:
    session_id, instrument_id = _session(client, db, "vp-ident-bad")
    response = client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/fields/save",
        data={
            "reviewee_after_release_mode": "raw",
            "reviewee_after_release_reviewer_identity": "everything",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert vp.list_for_instrument(db, instrument_id).get("reviewee") is None


# ── The reviewer's own copy of the card ──────────────────────────────


@pytest.fixture
def rae() -> AuthenticatedUser:
    """The reviewer ``_seed_and_activate`` rosters."""
    return AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )


def test_the_reviewer_sees_the_level_after_a_raw_reviewees_cell(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-ident-rs")
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=False
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    vp.list_for_instrument(db, instrument.id)["reviewee"].after_release_reviewer_identity = (
        "name_email_profile"
    )
    db.commit()
    body = make_client(rae).get(f"/me/sessions/{review_session.id}").text
    assert _span(body, "data-rs-reviewer-identity").endswith(
        ">Name, email, profile</span>"
    )
    # The pill widens its column (base.html's ``table.vp-grid:has(...)``;
    # tests/browser/test_vp_identity_chip.py measures it on Band 2).
    assert "vp-identity-pill" in _span(body, "data-rs-reviewer-identity")
    assert '<table class="vp-grid"' in body
    assert 'class="muted vp-col-window vp-col-released"' in body
