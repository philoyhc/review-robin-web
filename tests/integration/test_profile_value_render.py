"""A profile value that is not a web address renders a marker, not a link.

ProfileLink updates Item 3 (``guide/profilelink_updates.md``): only an
``http://`` / ``https://`` value becomes an ``href``; any other
non-empty value renders a muted ``•••`` whose ``title`` carries the
value; an empty one renders nothing. One macro
(``_partials/profile_value.html``) on every surface that renders the
value, and the Band 2 preview's ``profileCell`` in JS. Downloads carry
the value whole.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentDisplayField, Reviewee, Reviewer
from app.web.views import is_web_link

from .test_reviewer_identity_level import _download, _results
from .test_reviewer_surface_display_fields import (
    _activate,
    _operator_creates_session_with_pair,
)

LINK = "https://example.edu/carol"
TEXT = "AB1234"
SCRIPT = "javascript:alert(1)"


@pytest.fixture
def rae() -> AuthenticatedUser:
    """The reviewer ``_operator_creates_session_with_pair`` rosters."""
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _masked(value: str) -> str:
    return (
        f'<span class="muted" title="{value}" data-profile-masked>'
        f'<span aria-hidden="true">•••</span>'
        f'<span class="visually-hidden">{value}</span></span>'
    )


def _hrefs(body: str) -> list[str]:
    return re.findall(r'href="([^"]*)"', body)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.edu/a", True),
        ("HTTP://example.edu", True),
        ("  https://example.edu  ", True),
        ("http://", False),
        ("https:example.edu", False),
        ("//example.edu", False),
        ("www.example.edu/a", False),
        ("AB1234", False),
        (SCRIPT, False),
        ("", False),
        (None, False),
    ],
)
def test_only_an_http_address_is_a_link(value: str | None, expected: bool) -> None:
    assert is_web_link(value) is expected


# ── The operator's rosters ───────────────────────────────────────────


def _rosters(
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
    alice: AuthenticatedUser,
    code: str,
    value: str,
) -> tuple[str, str]:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator, db, code=code,
        reviewer_email="rae@example.edu", reviewee_ident="carol@example.edu",
    )
    for model in (Reviewer, Reviewee):
        row = db.execute(
            select(model).where(model.session_id == review_session.id)
        ).scalar_one()
        row.profile_link = value
    db.commit()
    base = f"/operator/sessions/{review_session.id}"
    return (
        operator.get(f"{base}/reviewers").text,
        operator.get(f"{base}/reviewees").text,
    )


def test_the_rosters_link_an_address(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    for body in _rosters(db, make_client, alice, "pv-roster-link", LINK):
        assert f'<a href="{LINK}" target="_blank" rel="noopener">link</a>' in body
        assert "data-profile-masked" not in body


@pytest.mark.parametrize("value", [TEXT, SCRIPT])
def test_the_rosters_mask_anything_else(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
    value: str,
) -> None:
    code = "pv-roster-" + ("text" if value == TEXT else "js")
    for body in _rosters(db, make_client, alice, code, value):
        assert _masked(value) in body
        assert value not in _hrefs(body)


# ── The reviewer's surface ───────────────────────────────────────────


def _surface(
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
    alice: AuthenticatedUser,
    rae_user: AuthenticatedUser,
    code: str,
    value: str,
) -> str:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator, db, code=code,
        reviewer_email="rae@example.edu", reviewee_ident="carol@example.edu",
    )
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()
    reviewee.profile_link = value
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    db.add(InstrumentDisplayField(
        instrument_id=instrument.id, label="", source_type="reviewee",
        source_field="profile_link", order=10, visible=True,
    ))
    db.commit()
    _activate(operator, db, review_session)
    response = make_client(rae_user).get(f"/me/sessions/{review_session.id}")
    assert response.status_code == 200, response.text
    return response.text


def test_the_surface_masks_a_value_that_is_not_an_address(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    body = _surface(db, make_client, alice, rae, "pv-surface-text", TEXT)
    assert ">Profile<" in body
    assert _masked(TEXT) in body
    assert TEXT not in _hrefs(body)
    # The column still sorts on the stored value.
    assert f'data-sort-value="{TEXT}"' in body


def test_the_surface_never_links_a_script(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    body = _surface(db, make_client, alice, rae, "pv-surface-js", SCRIPT)
    assert _masked(SCRIPT) in body
    assert not any(href.startswith("javascript:") for href in _hrefs(body))


# ── The reviewer's summary and the reviewee's results ────────────────


def _pages(
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
    alice: AuthenticatedUser,
    code: str,
    value: str,
) -> tuple[str, str]:
    from .test_reviewee_results_body import (
        _enable_reviewee_after_release_raw,
        _enable_reviewer_after_release_raw,
        _operator_user,
        _seed_and_activate,
        _seed_submitted_responses,
    )

    rae_user = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae Reviewer", provider="aad"
    )
    carol = AuthenticatedUser(
        principal_id="carol-oid", email="carol@example.edu", name="Carol Reviewee", provider="aad"
    )
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code=code)
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().first()
    for reviewee in db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars():
        reviewee.profile_link = value
    db.add(InstrumentDisplayField(
        instrument_id=instrument.id, label="", source_type="reviewee",
        source_field="profile_link", order=10, visible=True,
    ))
    db.commit()
    _seed_submitted_responses(db, review_session, comments_value="Solid work.")
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )
    _enable_reviewer_after_release_raw(db, review_session, operator=_operator_user(db))
    summary = make_client(rae_user).get(f"/me/sessions/{review_session.id}/summary").text
    results = make_client(carol).get(f"/me/sessions/{review_session.id}/results").text
    return summary, results


def test_the_summary_and_the_results_link_an_address(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    for name, body in zip(
        ("summary", "results"), _pages(db, make_client, alice, "pv-pages-link", LINK)
    ):
        assert f'<a href="{LINK}">View</a>' in body, name
        assert "data-profile-masked" not in body, name


def test_the_summary_and_the_results_mask_anything_else(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    for name, body in zip(
        ("summary", "results"), _pages(db, make_client, alice, "pv-pages-text", TEXT)
    ):
        assert ">Profile</th>" in body, name
        assert _masked(TEXT) in body, name
        assert TEXT not in _hrefs(body), name


# ── The reviewer card (Item 2's profile level) ───────────────────────


@pytest.fixture
def carol() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="carol-oid",
        email="carol@example.edu",
        name="Carol Reviewee",
        provider="aad",
    )


def test_the_reviewer_card_masks_a_value_that_is_not_an_address(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    body = _results(
        db, alice, carol, make_client,
        code="pv-card-text", level="name_email_profile", link=TEXT,
    )
    assert _masked(TEXT) in body
    assert TEXT not in _hrefs(body)


def test_the_reviewer_card_shows_nothing_below_the_profile_level(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    body = _results(
        db, alice, carol, make_client,
        code="pv-card-hidden", level="name_email", link=TEXT,
    )
    assert TEXT not in body


# ── The observer's download carries it whole ─────────────────────────


def test_the_download_carries_a_value_that_is_not_an_address(
    client: TestClient, db: Session
) -> None:
    header, row = _download(
        client, db, code="pv-csv-text", level="name_email_profile", link=TEXT
    )
    assert header[2] == "ReviewerProfileLink"
    assert row[2] == TEXT


# ── The Band 2 preview ───────────────────────────────────────────────


def test_the_preview_mirrors_the_rule(client: TestClient, db: Session) -> None:
    from .test_instrument_builder_routes import _new_model_with_tags

    review_session, instrument = _new_model_with_tags(client, db, code="pv-preview")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    for line in (
        r"return /^https?:\/\/[^\/?#\s]/i.test(String(v || '').trim());",
        "if (isWebLink(v)) { return '<a href=\"' + esc(v) + '\">View</a>'; }",
        "return '<span class=\"muted\" title=\"' + esc(v) + '\" data-profile-masked>'",
        "cell = profileCell(v);",
    ):
        assert line in flat, line
