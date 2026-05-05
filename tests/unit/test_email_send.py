"""Unit tests for ``app.services.email_send``.

Exercises the SMTP backend over a mocked ``smtplib.SMTP`` /
``smtplib.SMTP_SSL`` (no real network), the typed-stub Graph
backend's ``NotImplementedError``, and the ``transport_for``
factory's dispatch.
"""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_send import (
    EmailMessage,
    GraphEmailTransport,
    SmtpEmailTransport,
    transport_for,
)
from app.services.operator_settings import EmailSettings


def _settings(*, encryption: str = "starttls") -> EmailSettings:
    return EmailSettings(
        transport="smtp",
        host="smtp.office365.com",
        port=587 if encryption == "starttls" else 465,
        username="alice@example.edu",
        password="app-pw-1234",
        from_display_name="Alice's Reviews",
        encryption=encryption,
    )


def _msg(*, cc: list[str] | None = None, bcc: list[str] | None = None) -> EmailMessage:
    return EmailMessage(
        from_addr="alice@example.edu",
        from_display_name="Alice's Reviews",
        to="rae@example.edu",
        subject="Invitation",
        body="Hello Rae.",
        cc=cc or [],
        bcc=bcc or [],
    )


# ── transport_for factory ────────────────────────────────────────────────


def test_transport_for_returns_smtp_backend() -> None:
    transport = transport_for(_settings())
    assert isinstance(transport, SmtpEmailTransport)


def test_transport_for_unknown_value_raises() -> None:
    bad = EmailSettings(
        transport="rot13",  # type: ignore[arg-type]
        host="x",
        port=1,
        username="x",
        password="x",
        from_display_name=None,
        encryption="starttls",
    )
    with pytest.raises(ValueError, match="unknown transport"):
        transport_for(bad)


def test_smtp_backend_rejects_non_smtp_settings() -> None:
    bad = EmailSettings(
        transport="graph",  # type: ignore[arg-type]
        host="x",
        port=1,
        username="x",
        password="x",
        from_display_name=None,
        encryption="starttls",
    )
    with pytest.raises(ValueError, match="settings.transport='smtp'"):
        SmtpEmailTransport(bad)


# ── SMTP backend success paths ───────────────────────────────────────────


def test_smtp_send_starttls_happy_path() -> None:
    transport = SmtpEmailTransport(_settings())
    fake_smtp = MagicMock()
    with patch("smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = fake_smtp
        # The transport uses ``with smtp`` via the ``_connect`` helper;
        # patching the constructor's instance directly is cleaner since
        # the helper returns the (logged-in) connection. Patch the
        # private helper instead so we keep the test focused on the
        # outer send flow.
        with patch.object(transport, "_connect") as connect:
            connect.return_value.__enter__.return_value = fake_smtp
            connect.return_value.__exit__.return_value = False
            result = transport.send(_msg())
    assert result.ok is True
    assert result.error_message is None
    fake_smtp.send_message.assert_called_once()
    kwargs = fake_smtp.send_message.call_args.kwargs
    assert kwargs["from_addr"] == "alice@example.edu"
    assert kwargs["to_addrs"] == ["rae@example.edu"]


def test_smtp_send_includes_cc_and_bcc_recipients() -> None:
    transport = SmtpEmailTransport(_settings())
    fake_smtp = MagicMock()
    with patch.object(transport, "_connect") as connect:
        connect.return_value.__enter__.return_value = fake_smtp
        connect.return_value.__exit__.return_value = False
        transport.send(_msg(cc=["cc@x.edu"], bcc=["bcc@x.edu"]))
    kwargs = fake_smtp.send_message.call_args.kwargs
    assert kwargs["to_addrs"] == ["rae@example.edu", "cc@x.edu", "bcc@x.edu"]


def test_smtp_send_uses_implicit_ssl_when_encryption_is_ssl() -> None:
    """``encryption='ssl'`` ⇒ ``SMTP_SSL`` (port 465 style); ``starttls``
    is the implicit alternative — covered by the happy-path test."""
    transport = SmtpEmailTransport(_settings(encryption="ssl"))
    with patch("smtplib.SMTP_SSL") as ssl_cls, patch("smtplib.SMTP") as plain_cls:
        plain_cls.return_value = MagicMock()
        ssl_cls.return_value = MagicMock()
        transport._connect()
    ssl_cls.assert_called_once_with("smtp.office365.com", 465, timeout=30)
    plain_cls.assert_not_called()


def test_smtp_send_uses_starttls_when_encryption_is_starttls() -> None:
    transport = SmtpEmailTransport(_settings(encryption="starttls"))
    with patch("smtplib.SMTP") as plain_cls, patch("smtplib.SMTP_SSL") as ssl_cls:
        plain_cls.return_value = MagicMock()
        ssl_cls.return_value = MagicMock()
        transport._connect()
    plain_cls.assert_called_once_with("smtp.office365.com", 587, timeout=30)
    ssl_cls.assert_not_called()
    # ``starttls()`` and ``login()`` invoked on the SMTP instance.
    smtp_instance = plain_cls.return_value
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("alice@example.edu", "app-pw-1234")


# ── SMTP backend failure paths ───────────────────────────────────────────


def test_smtp_auth_error_returns_failed_send_result() -> None:
    transport = SmtpEmailTransport(_settings())
    with patch.object(transport, "_connect") as connect:
        connect.side_effect = smtplib.SMTPAuthenticationError(
            535, b"5.7.3 Authentication unsuccessful"
        )
        result = transport.send(_msg())
    assert result.ok is False
    assert "Authentication failed" in (result.error_message or "")
    assert result.transport_response is not None


def test_smtp_connection_error_returns_failed_send_result() -> None:
    transport = SmtpEmailTransport(_settings())
    with patch.object(transport, "_connect") as connect:
        connect.side_effect = smtplib.SMTPConnectError(
            421, b"4.4.1 Service not available"
        )
        result = transport.send(_msg())
    assert result.ok is False
    assert "Couldn't connect" in (result.error_message or "")


def test_smtp_recipients_refused_returns_failed_send_result() -> None:
    transport = SmtpEmailTransport(_settings())
    with patch.object(transport, "_connect") as connect:
        fake_smtp = MagicMock()
        fake_smtp.send_message.side_effect = smtplib.SMTPRecipientsRefused(
            {"rae@example.edu": (550, b"5.1.1 user unknown")}
        )
        connect.return_value.__enter__.return_value = fake_smtp
        connect.return_value.__exit__.return_value = False
        result = transport.send(_msg())
    assert result.ok is False
    assert "refused one or more recipients" in (result.error_message or "")


def test_smtp_oserror_during_connect_returns_failed_send_result() -> None:
    """Network blip / DNS failure surfaces as ``OSError``; the backend
    catches it and returns a failed ``SendResult`` rather than letting
    the exception bubble into the dispatcher."""
    transport = SmtpEmailTransport(_settings())
    with patch.object(transport, "_connect") as connect:
        connect.side_effect = OSError("name or service not known")
        result = transport.send(_msg())
    assert result.ok is False
    assert "SMTP send failed" in (result.error_message or "")


# ── Graph stub ───────────────────────────────────────────────────────────


def test_graph_transport_send_raises_not_implemented() -> None:
    settings = EmailSettings(
        transport="smtp",  # the stub doesn't enforce; the factory does
        host="x",
        port=1,
        username="x",
        password="x",
        from_display_name=None,
        encryption="starttls",
    )
    transport = GraphEmailTransport(settings)
    with pytest.raises(NotImplementedError, match="future segment"):
        transport.send(_msg())
