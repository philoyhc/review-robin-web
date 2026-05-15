"""Per-operator settings — SMTP credentials + display preferences.

Segment 11E PR 4 ships the operator-level Settings page at
``/operator/settings`` that populates the seven ``users.smtp_*``
columns. The ``EmailSettings`` dataclass returned by
``get_email_settings`` is the single shape every send-side caller
consumes — Segment 11C PR F's Manage Invitations send handler
calls ``transport_for(settings)`` (Segment 11E PR 5's transport
factory) to pick the right backend.

Segment 18B PR 2 adds the per-operator default display timezone,
stored as the ``display_timezone`` key inside the general
``users.preferences`` JSON container (column pre-positioned by
13F PR 7). ``get_display_timezone`` / ``set_display_timezone``
are the only readers / writers of that key.

**Send-as-me identity model.** Credentials are scoped to the
``User`` row, not to the session. The signed-in operator who hits
Send is the ``From`` of the message; sessions don't carry their own
SMTP creds.

The plaintext password is never persisted. ``save_email_settings``
takes the plaintext input, encrypts it via
``app.services._secrets.encrypt_password``, and stores the
ciphertext bytes on ``users.smtp_password_encrypted``. ``get_email_settings``
decrypts on read, returning a frozen dataclass the transport
backend consumes.
"""

from __future__ import annotations

import zoneinfo
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db.models import User
from app.services import _secrets, audit
from app.services.date_formatting import DEFAULT_TIMEZONE


# Today the only legal transport is SMTP. The ``Literal`` widens to
# include ``"graph"`` once Segment 11E PR 5's typed Graph stub gets a
# real implementation.
EmailTransportName = Literal["smtp"]
SMTP_ENCRYPTION_MODES = ("starttls", "ssl")

# Every IANA zone name, resolved once at import. Used both to
# validate operator input and to populate the Settings-card picker.
_AVAILABLE_TIMEZONES: frozenset[str] = frozenset(
    zoneinfo.available_timezones()
)

# The ``users.preferences`` key holding the operator's default
# display timezone (Segment 18B PR 2).
_DISPLAY_TIMEZONE_KEY = "display_timezone"


@dataclass(frozen=True)
class EmailSettings:
    """Decrypted, send-ready snapshot of an operator's SMTP credentials.

    All fields populated; any ``None`` would mean the operator's
    credential set is incomplete and ``get_email_settings`` returns
    ``None`` for the whole row instead.
    """

    transport: EmailTransportName
    host: str
    port: int
    username: str
    password: str
    from_display_name: str | None
    encryption: str  # "starttls" / "ssl"


def _is_complete(user: User) -> bool:
    """A credential set is complete only when every required field is
    populated. Partial / draft saves persist whatever the operator
    entered, but ``get_email_settings`` treats partial as "not yet
    configured." Display-name is optional and intentionally excluded
    from the completeness check."""
    return all(
        [
            user.smtp_host,
            user.smtp_port,
            user.smtp_username,
            user.smtp_password_encrypted,
            user.smtp_encryption,
            user.smtp_transport,
        ]
    )


def get_email_settings(user: User) -> EmailSettings | None:
    """Returns a decrypted ``EmailSettings`` when the operator's
    credentials are complete; ``None`` otherwise. Callers (Segment
    11C PR F's send dispatcher; the Manage Invitations transport-
    ready chrome pill) treat ``None`` as "operator hasn't configured
    a transport yet."""
    if not _is_complete(user):
        return None
    assert user.smtp_password_encrypted is not None  # _is_complete check
    plaintext = _secrets.decrypt_password(user.smtp_password_encrypted)
    return EmailSettings(
        transport=user.smtp_transport or "smtp",  # type: ignore[arg-type]
        host=user.smtp_host or "",
        port=user.smtp_port or 0,
        username=user.smtp_username or "",
        password=plaintext,
        from_display_name=user.smtp_from_display_name,
        encryption=user.smtp_encryption or "starttls",
    )


def save_email_settings(
    db: Session,
    *,
    user: User,
    host: str | None,
    port: int | None,
    username: str | None,
    plaintext_password: str | None,
    from_display_name: str | None,
    encryption: str | None,
    correlation_id: str | None = None,
) -> None:
    """Upsert the SMTP-credential columns on ``user``.

    Empty / whitespace strings are normalised to ``None`` so a
    cleared field reads as "not set" rather than "set to empty
    string." A ``plaintext_password`` of ``None`` (or whitespace)
    leaves the existing ciphertext intact — the editor's password
    field renders empty by default, and an empty submit must not
    wipe a previously-saved password.
    """
    changes: dict[str, list[Any]] = {}

    def _set(field: str, new_value: Any) -> None:
        old = getattr(user, field)
        if old != new_value:
            changes[field] = [old, new_value]
            setattr(user, field, new_value)

    _set("smtp_host", _normalise(host))
    _set("smtp_port", port if isinstance(port, int) else None)
    _set("smtp_username", _normalise(username))
    _set("smtp_from_display_name", _normalise(from_display_name))
    _set("smtp_encryption", _normalise(encryption))
    _set("smtp_transport", "smtp")  # only legal transport today

    pw_norm = _normalise(plaintext_password)
    if pw_norm is not None:
        ciphertext = _secrets.encrypt_password(pw_norm)
        if ciphertext != user.smtp_password_encrypted:
            # Don't log the actual ciphertext / plaintext in audit
            # detail — record only that the password rotated.
            changes["smtp_password_encrypted"] = ["(unchanged)", "(updated)"]
            user.smtp_password_encrypted = ciphertext

    if changes:
        # Build an audit-safe diff with the password placeholder kept
        # symbolic so the event detail never carries credential bytes.
        audit_changes = {
            field: ([_serialise(old), _serialise(new)])
            for field, (old, new) in changes.items()
            if field != "smtp_password_encrypted"
        }
        if "smtp_password_encrypted" in changes:
            audit_changes["smtp_password_changed"] = [False, True]
        audit.write_event(
            db,
            event_type="operator_email_settings.updated",
            summary=f"Operator {user.email} updated SMTP settings",
            actor_user_id=user.id,
            session=None,
            payload=audit.changes(audit_changes),
            correlation_id=correlation_id,
        )

    db.flush()
    db.commit()


def clear_email_settings(
    db: Session,
    *,
    user: User,
    correlation_id: str | None = None,
) -> None:
    """Wipe every SMTP-credential field. Audit emits whether or not
    the operator had anything configured — clicking Clear is the
    operator's explicit intent, and the absence of a prior config
    is itself worth logging."""
    user.smtp_host = None
    user.smtp_port = None
    user.smtp_username = None
    user.smtp_password_encrypted = None
    user.smtp_from_display_name = None
    user.smtp_encryption = None
    user.smtp_transport = "smtp"
    audit.write_event(
        db,
        event_type="operator_email_settings.cleared",
        summary=f"Operator {user.email} cleared SMTP settings",
        actor_user_id=user.id,
        session=None,
        correlation_id=correlation_id,
    )
    db.flush()
    db.commit()


# --------------------------------------------------------------------------- #
# Display timezone (Segment 18B PR 2)
# --------------------------------------------------------------------------- #


def timezone_options() -> list[str]:
    """Sorted IANA zone names for the Settings-card picker."""
    return sorted(_AVAILABLE_TIMEZONES)


def is_valid_timezone(name: str) -> bool:
    return name in _AVAILABLE_TIMEZONES


def get_display_timezone(user: User) -> str:
    """The operator's configured default display timezone.

    Reads the ``display_timezone`` key out of ``users.preferences``;
    an unset / unknown value falls through to ``UTC``."""
    preferences = user.preferences or {}
    value = preferences.get(_DISPLAY_TIMEZONE_KEY)
    if isinstance(value, str) and is_valid_timezone(value):
        return value
    return DEFAULT_TIMEZONE


def set_display_timezone(
    db: Session,
    *,
    user: User,
    timezone_name: str,
    correlation_id: str | None = None,
) -> None:
    """Persist the operator's default display timezone.

    Writes the ``display_timezone`` key inside the ``users.preferences``
    JSON container, leaving any other keys intact. A no-op when the
    value is unchanged. Raises ``ValueError`` for an unknown zone —
    the route validates first, so this is a defence-in-depth guard.
    """
    if not is_valid_timezone(timezone_name):
        raise ValueError(f"unknown timezone {timezone_name!r}")

    old = get_display_timezone(user)
    if old == timezone_name:
        return

    # JSON columns only flag dirty on reassignment — mutate a copy.
    preferences = dict(user.preferences or {})
    preferences[_DISPLAY_TIMEZONE_KEY] = timezone_name
    user.preferences = preferences

    audit.write_event(
        db,
        event_type="operator.display_timezone_set",
        summary=f"Operator {user.email} set default timezone to {timezone_name}",
        actor_user_id=user.id,
        session=None,
        payload=audit.changes({_DISPLAY_TIMEZONE_KEY: [old, timezone_name]}),
        correlation_id=correlation_id,
    )
    db.flush()
    db.commit()


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _serialise(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return "(binary)"
    return value
