"""Operator Settings page (Segment 11E PR 4).

Covers the round-trip through ``/operator/settings``:
- GET renders the empty-state intro card when no credentials are
  configured; renders the populated form when they are.
- POST persists the form fields, encrypts the password at rest, and
  emits the ``operator_email_settings.updated`` audit.
- POST with a blank password preserves the existing ciphertext (so
  the page can render the password field empty by default without
  silently wiping a saved value).
- POST /clear wipes every field + emits
  ``operator_email_settings.cleared``.
- ``operator_settings.get_email_settings`` returns ``None`` on a
  partial config; returns a decrypted dataclass once complete.
- Missing ``SMTP_ENCRYPTION_KEY`` is fail-loud at first encrypt /
  decrypt rather than silent.
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


# ── GET ──────────────────────────────────────────────────────────────────


def test_settings_get_renders_empty_state_when_unconfigured(
    client: TestClient, db: Session
) -> None:
    body = client.get("/operator/settings").text
    assert "<h1>Settings</h1>" in body
    assert "Email send (SMTP)" in body
    # Empty-state intro card before the form:
    assert "Bring your own SMTP" in body
    # Password indicator reads "not set" before any save.
    assert "not set" in body


def test_settings_get_renders_populated_form_when_configured(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "app-pw-1234",
            "smtp_encryption": "starttls",
            "smtp_from_display_name": "Alice's Reviews",
        },
        follow_redirects=False,
    )
    body = client.get("/operator/settings").text
    assert 'value="smtp.office365.com"' in body
    assert 'value="587"' in body
    assert 'value="alice@example.edu"' in body
    assert "Alice&#39;s Reviews" in body or "Alice's Reviews" in body
    # Password reads "set" once persisted; plaintext never appears.
    assert "<span class=\"muted\">— set</span>" in body
    assert "app-pw-1234" not in body
    # Empty-state intro card disappears once host is set.
    assert "Bring your own SMTP" not in body


# ── POST /settings ───────────────────────────────────────────────────────


def test_settings_save_persists_and_audits(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    response = client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "app-pw-abcd",
            "smtp_encryption": "starttls",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/settings"

    user = _alice_row(db)
    assert user.smtp_host == "smtp.office365.com"
    assert user.smtp_port == 587
    assert user.smtp_username == "alice@example.edu"
    assert user.smtp_encryption == "starttls"
    assert user.smtp_password_encrypted is not None
    # Stored value is ciphertext; plaintext is recoverable.
    assert user.smtp_password_encrypted != b"app-pw-abcd"
    assert _secrets.decrypt_password(user.smtp_password_encrypted) == "app-pw-abcd"

    # Audit captures the diff but never logs the password bytes.
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "operator_email_settings.updated"
        )
    ).scalar_one()
    changes = event.detail["changes"]
    assert changes["smtp_host"] == [None, "smtp.office365.com"]
    assert changes["smtp_port"] == [None, 587]
    # Password change logged symbolically only.
    assert changes["smtp_password_changed"] == [False, True]
    assert "smtp_password_encrypted" not in changes


def test_settings_save_blank_password_keeps_existing_ciphertext(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "first-password",
            "smtp_encryption": "starttls",
        },
        follow_redirects=False,
    )
    db.expire_all()
    first_ciphertext = _alice_row(db).smtp_password_encrypted

    # Save again with blank password — display name changes; password
    # field empty must NOT wipe the saved ciphertext.
    client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "",
            "smtp_encryption": "starttls",
            "smtp_from_display_name": "Updated name",
        },
        follow_redirects=False,
    )
    db.expire_all()
    user = _alice_row(db)
    assert user.smtp_password_encrypted == first_ciphertext
    assert user.smtp_from_display_name == "Updated name"


def test_settings_save_invalid_port_returns_422(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    response = client.post(
        "/operator/settings",
        data={"smtp_port": "not-a-port"},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_settings_save_invalid_encryption_returns_422(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    response = client.post(
        "/operator/settings",
        data={"smtp_encryption": "double-rot13"},
        follow_redirects=False,
    )
    assert response.status_code == 422


# ── POST /settings/clear ─────────────────────────────────────────────────


def test_settings_clear_wipes_everything_and_audits(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "x",
            "smtp_encryption": "starttls",
        },
        follow_redirects=False,
    )
    response = client.post("/operator/settings/clear", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/settings"

    user = _alice_row(db)
    assert user.smtp_host is None
    assert user.smtp_port is None
    assert user.smtp_username is None
    assert user.smtp_password_encrypted is None
    assert user.smtp_encryption is None
    # Default "smtp" transport survives the clear — it's not a
    # credential, just a backend selector.
    assert user.smtp_transport == "smtp"

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "operator_email_settings.cleared"
        )
    ).scalar_one()
    assert event.actor_user_id == user.id


# ── operator_settings.get_email_settings ─────────────────────────────────


def test_get_email_settings_returns_none_on_partial(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    """Missing app password — the credential set is incomplete, so
    ``get_email_settings`` returns ``None`` rather than a half-baked
    dataclass that the transport factory would unwrap."""
    # Touch a route so the operator user row gets created via
    # ``get_or_create_user``.
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
    client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "very-secret",
            "smtp_encryption": "starttls",
        },
        follow_redirects=False,
    )
    db.expire_all()
    user = _alice_row(db)
    snap = operator_settings.get_email_settings(user)
    assert snap is not None
    assert snap.transport == "smtp"
    assert snap.host == "smtp.office365.com"
    assert snap.port == 587
    assert snap.username == "alice@example.edu"
    assert snap.password == "very-secret"
    assert snap.encryption == "starttls"


# ── _secrets fail-loud on missing key ────────────────────────────────────


def test_save_fails_loudly_when_encryption_key_missing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``SMTP_ENCRYPTION_KEY`` configured + an attempt to save a
    password ⇒ 500 with operator-actionable copy. The Settings page
    GET still works (we don't pre-validate at boot)."""
    monkeypatch.setattr(settings, "smtp_encryption_key", None)
    # GET still loads.
    assert client.get("/operator/settings").status_code == 200
    response = client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "x",
            "smtp_encryption": "starttls",
        },
        follow_redirects=False,
    )
    assert response.status_code == 500
    assert "SMTP_ENCRYPTION_KEY" in response.text


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
    ``app.web.return_to`` and renders the back-link + Cancel target."""
    body = client.get(
        "/operator/settings?return_to=/operator/sessions"
    ).text
    assert "&larr; Back to Sessions" in body
    assert 'class="back-link" href="/operator/sessions"' in body
    # Cancel anchor in the form actions row points at the same URL.
    assert (
        '<a class="btn secondary" href="/operator/sessions">Cancel</a>' in body
    )


def test_settings_save_preserves_return_to_through_redirect(
    client: TestClient, db: Session, fernet_key: str
) -> None:
    """The hidden ``return_to`` form input rides through the Save
    redirect so the back-link stays wired after reload."""
    response = client.post(
        "/operator/settings",
        data={
            "smtp_host": "smtp.office365.com",
            "smtp_port": "587",
            "smtp_username": "alice@example.edu",
            "smtp_password": "x",
            "smtp_encryption": "starttls",
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
