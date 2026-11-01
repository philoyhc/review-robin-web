"""Operator Settings page (Segment 11E PR 4; 14C Item 1).

The page carries the default timezone only: its per-operator SMTP cards
and their two routes retired in 14C Item 1 (2026-11-01). The SMTP storage
stays (``spec/settings_inventory.md``), so its service is tested here
directly: save encrypts and audits, a blank password keeps the stored
one, clear wipes and audits, ``get_email_settings`` is ``None`` until
complete, and a missing ``SMTP_ENCRYPTION_KEY`` fails loudly.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, User
from app.services import _secrets, operator_settings


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Set a real Fernet key on the singleton ``settings`` for the
    duration of the test, then clear. The encryption helper reads
    the key lazily so this is enough to swap it in."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "smtp_encryption_key", key)
    yield key


def _alice_row(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


# ── The page: the SMTP cards retired (14C Item 1) ─────────────────────────


def test_settings_page_has_no_smtp_cards_and_date_time_stands_alone(
    client: TestClient,
) -> None:
    """The send path is Graph (as the operator or a dedicated mailbox), so
    the page asks for no SMTP field and offers no Clear card; Date & time
    is its one card, in the half-width grid."""
    body = client.get("/operator/settings").text
    for gone in ("Email send (SMTP)", "Clear all settings (SMTP)", 'name="smtp_host"',
                 'id="operator-settings-form"', "Bring your own SMTP", "app password"):
        assert gone not in body, gone
    assert '<div class="card" id="timezone-settings">' in body
    assert body.index('class="bottom-grid"') < body.index('id="timezone-settings"')


def test_settings_display_mode_card_retired_toggle_in_chrome(
    client: TestClient,
) -> None:
    body = client.get("/operator/settings").text
    assert "Display mode" not in body.split("<main", 1)[-1].split("</main>")[0]


@pytest.mark.parametrize("path", ["/operator/settings", "/operator/settings/clear"])
def test_the_smtp_routes_are_gone(client: TestClient, path: str) -> None:
    response = client.post(path, data={"confirm": "true"}, follow_redirects=False)
    assert response.status_code in (404, 405)


# ── The kept storage: operator_settings (spec/settings_inventory.md) ──────


def _configure(db: Session, user: User, **overrides: object) -> None:
    fields = {
        "host": "smtp.office365.com", "port": 587, "username": "alice@example.edu",
        "plaintext_password": "very-secret", "from_display_name": "Alice",
        "encryption": "starttls",
    }
    fields.update(overrides)
    operator_settings.save_email_settings(db, user=user, **fields)


def test_save_persists_encrypts_and_audits(client: TestClient, db: Session, fernet_key: str) -> None:
    client.get("/operator/sessions")
    user = _alice_row(db)
    _configure(db, user)
    db.expire_all()
    user = _alice_row(db)
    assert user.smtp_host == "smtp.office365.com" and user.smtp_port == 587
    assert user.smtp_password_encrypted and b"very-secret" not in user.smtp_password_encrypted
    assert _secrets.decrypt_password(user.smtp_password_encrypted) == "very-secret"
    assert db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "operator_email_settings.updated")
    ).scalar_one_or_none() is not None


def test_a_blank_password_keeps_the_stored_one(client: TestClient, db: Session, fernet_key: str) -> None:
    client.get("/operator/sessions")
    user = _alice_row(db)
    _configure(db, user)
    before = _alice_row(db).smtp_password_encrypted
    _configure(db, user, plaintext_password="", host="smtp2.example.edu")
    db.expire_all()
    after = _alice_row(db)
    assert after.smtp_host == "smtp2.example.edu" and after.smtp_password_encrypted == before


def test_clear_wipes_everything_and_audits(client: TestClient, db: Session, fernet_key: str) -> None:
    client.get("/operator/sessions")
    user = _alice_row(db)
    _configure(db, user)
    operator_settings.clear_email_settings(db, user=user)
    db.expire_all()
    user = _alice_row(db)
    assert user.smtp_host is None and user.smtp_password_encrypted is None
    assert db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "operator_email_settings.cleared")
    ).scalar_one_or_none() is not None


def test_get_email_settings_returns_none_on_partial(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    """Missing app password: ``get_email_settings`` returns ``None``
    rather than a half-built dataclass."""
    client.get("/operator/sessions")
    user = _alice_row(db)
    user.smtp_host = "smtp.office365.com"
    user.smtp_port = 587
    user.smtp_username = "alice@example.edu"
    user.smtp_encryption = "starttls"
    db.flush()
    assert operator_settings.get_email_settings(user) is None


def test_get_email_settings_returns_decrypted_when_complete(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    client.get("/operator/sessions")
    user = _alice_row(db)
    _configure(db, user)
    db.expire_all()
    snap = operator_settings.get_email_settings(_alice_row(db))
    assert snap is not None and snap.transport == "smtp"
    assert (snap.host, snap.port, snap.username, snap.password, snap.encryption) == (
        "smtp.office365.com", 587, "alice@example.edu", "very-secret", "starttls"
    )


def test_save_fails_loudly_when_encryption_key_missing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``SMTP_ENCRYPTION_KEY`` and a password to store: the service
    raises rather than storing it in the clear. The page still loads."""
    monkeypatch.setattr(settings, "smtp_encryption_key", None)
    assert client.get("/operator/settings").status_code == 200
    client.get("/operator/sessions")
    with pytest.raises(_secrets.MissingEncryptionKey):
        _configure(db, _alice_row(db), plaintext_password="x")


# ── User-menu chrome link ────────────────────────────────────────────────


def test_user_menu_carries_settings_link_with_return_to(
    client: TestClient,
) -> None:
    """Chrome user-menu Settings link threads ``?return_to=`` so the
    Settings page's back-link knows where the operator came from."""
    body = client.get("/operator/sessions").text
    assert (
        'href="/operator/settings?return_to=/operator/sessions">Settings</a>'
        in body
    )


def test_user_menu_hides_settings_link_on_settings_page(
    client: TestClient,
) -> None:
    body = client.get("/operator/settings").text
    # Strip any return_to query param when looking for the link, since
    # the chrome partial omits the link entirely on the Settings page.
    assert "/operator/settings?return_to=" not in body or ">Settings</a>" not in body
    # Cheaper assertion: the chrome partial just doesn't render the
    # link element at all when on /operator/settings.
    assert "/operator/settings\">Settings</a>" not in body
    assert "Settings</a>" not in body or "Cancel" in body  # only cancel-anchor allowed


def test_settings_get_renders_back_link_to_origin(
    client: TestClient, db: Session
) -> None:
    """``?return_to=/operator/sessions`` resolves via
    ``app.web.return_to`` and renders the back-link. (The SMTP form's
    Cancel retired with it, 14C Item 1.)"""
    body = client.get(
        "/operator/settings?return_to=/operator/sessions"
    ).text
    assert "&larr; Back to Sessions" in body
    assert 'class="back-link" href="/operator/sessions"' in body


def test_timezone_save_preserves_return_to_through_redirect(
    client: TestClient, db: Session
) -> None:
    """The hidden ``return_to`` input rides through the Date & time
    save redirect so the back-link stays wired after reload."""
    response = client.post(
        "/operator/settings/timezone",
        data={
            "display_timezone": "Asia/Singapore",
            "return_to": "/operator/sessions",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/operator/settings?return_to=/operator/sessions"
    )


# ── Display timezone (Segment 18B PR 2) ──────────────────────────────────


def test_settings_get_renders_timezone_card(
    client: TestClient, db: Session
) -> None:
    """The Date & time card renders with a searchable datalist and the
    operator's current default (UTC before any save)."""
    body = client.get("/operator/settings").text
    assert "Date &amp; time" in body
    assert 'name="display_timezone"' in body
    assert 'list="timezone-options"' in body
    assert '<datalist id="timezone-options">' in body
    # Default pre-fill is UTC; a representative zone is in the list.
    assert 'value="UTC"' in body
    assert '<option value="Asia/Singapore">' in body


def test_settings_save_timezone_persists_and_audits(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Asia/Singapore"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/settings"

    user = _alice_row(db)
    assert user.preferences == {"display_timezone": "Asia/Singapore"}

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "operator.display_timezone_set"
        )
    ).scalar_one()
    assert event.detail["changes"]["display_timezone"] == [
        "UTC",
        "Asia/Singapore",
    ]


def test_settings_save_timezone_rejects_unknown_zone(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Mars/Olympus"},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert _alice_row(db).preferences in (None, {})


def test_settings_save_timezone_unchanged_is_noop(
    client: TestClient, db: Session
) -> None:
    """Saving the current value (UTC default) writes nothing and emits
    no audit event."""
    response = client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "UTC"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    events = (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "operator.display_timezone_set"
            )
        )
        .scalars()
        .all()
    )
    assert events == []


def test_settings_save_timezone_preserves_other_preference_keys(
    client: TestClient, db: Session
) -> None:
    """Writing the timezone key leaves unrelated preference keys
    intact — the JSON container is shared by future settings."""
    client.get("/operator/settings")  # materialise the operator row
    user = _alice_row(db)
    user.preferences = {"other_key": "keep-me"}
    db.commit()

    client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Europe/London"},
        follow_redirects=False,
    )

    refreshed = _alice_row(db)
    assert refreshed.preferences == {
        "other_key": "keep-me",
        "display_timezone": "Europe/London",
    }
