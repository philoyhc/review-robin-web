"""Email transport interface + SMTP backend (Segment 11E PR 5).

This module is the "transport-agnostic send abstraction" the
segment plan calls for. It defines the ``EmailTransport`` Protocol,
ships a concrete ``SmtpEmailTransport`` over ``smtplib``, and
leaves a typed-stub ``GraphEmailTransport`` placeholder for the
future Microsoft Graph swap. The factory ``transport_for(settings)``
dispatches on ``settings.transport``; today only ``"smtp"`` is
reachable.

**Nothing in the app calls this yet.** Segment 11C PR F's send
dispatch on the rebuilt Manage Invitations page is the first
caller; until then, outbox rows continue to write
``status="queued"`` as today.

Design notes:

* ``send`` returns a ``SendResult`` rather than raising. Callers
  inspect ``ok`` + ``error_message`` and persist back to the outbox
  row; downstream UI surfaces the failure in the queued / failed
  status pill on Manage Invitations + Outbox.
* Every smtplib-side exception is normalised. A backend that
  bubbles raw exceptions would force the dispatcher into broad
  ``except`` blocks; the Protocol shape keeps that boilerplate in
  one place.
* The Protocol carries ``EmailMessage`` / ``SendResult`` only —
  no DB types, no ``ReviewSession`` / ``Reviewer``. The dispatcher
  builds the message from outbox + session + reviewer rows and
  hands the transport a flat message object.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage as _StdEmailMessage
from typing import Protocol

from app.services.operator_settings import EmailSettings


# How long an aborted SMTP response truncates to before we stash it
# on the outbox row. Real-world SMTP error strings can be long; a
# fixed cap keeps the audit row size predictable.
_RESPONSE_TRUNCATE_AT = 500


@dataclass(frozen=True)
class EmailMessage:
    """Flat, transport-agnostic message shape.

    The dispatcher (Segment 11C PR F) builds one of these from an
    outbox row + the session / reviewer rows, then hands it to the
    transport. The transport never reads from the DB.
    """

    from_addr: str
    from_display_name: str | None
    to: str
    subject: str
    body: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SendResult:
    """Outcome of one ``send`` attempt.

    On failure, ``error_message`` is short operator-facing copy and
    ``transport_response`` carries the truncated raw provider
    response (useful for audit / debugging without ballooning the
    outbox row)."""

    ok: bool
    error_message: str | None = None
    transport_response: str | None = None


class EmailTransport(Protocol):
    """Every backend implements this single method."""

    def send(self, msg: EmailMessage) -> SendResult: ...


# ── SMTP backend ─────────────────────────────────────────────────────────


class SmtpEmailTransport:
    """``smtplib``-backed transport. Handles both STARTTLS (port 587)
    and implicit-SSL (port 465) flavours via the ``encryption`` field
    on the supplied ``EmailSettings``.

    Catches every ``smtplib`` exception and normalises to a failed
    ``SendResult`` rather than propagating. The dispatcher persists
    the result to the outbox row; the UI surfaces it on Manage
    Invitations / Outbox without the route handler needing to know
    about ``smtplib`` exception types.
    """

    def __init__(self, settings: EmailSettings) -> None:
        if settings.transport != "smtp":
            raise ValueError(
                f"SmtpEmailTransport requires settings.transport='smtp', "
                f"got {settings.transport!r}"
            )
        self._settings = settings

    def send(self, msg: EmailMessage) -> SendResult:
        try:
            payload = _build_message(msg, self._settings)
            recipients = [msg.to, *msg.cc, *msg.bcc]
            with self._connect() as smtp:
                smtp.send_message(
                    payload,
                    from_addr=self._settings.username,
                    to_addrs=recipients,
                )
            return SendResult(ok=True)
        except smtplib.SMTPAuthenticationError as exc:
            return _failure(
                "Authentication failed. Check the SMTP username and app "
                "password on /operator/settings.",
                str(exc),
            )
        except smtplib.SMTPRecipientsRefused as exc:
            return _failure(
                "The SMTP server refused one or more recipients.",
                str(exc.recipients),
            )
        except smtplib.SMTPSenderRefused as exc:
            return _failure(
                "The SMTP server refused the sender address.",
                str(exc),
            )
        except smtplib.SMTPDataError as exc:
            return _failure(
                "The SMTP server rejected the message body.",
                str(exc),
            )
        except smtplib.SMTPConnectError as exc:
            return _failure(
                "Couldn't connect to the SMTP server. Check the host "
                "and port on /operator/settings.",
                str(exc),
            )
        except (smtplib.SMTPException, OSError) as exc:
            return _failure(
                "SMTP send failed; see server response for detail.",
                str(exc),
            )

    def _connect(self) -> smtplib.SMTP:
        host = self._settings.host
        port = self._settings.port
        if self._settings.encryption == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
            smtp.starttls()
        smtp.login(self._settings.username, self._settings.password)
        return smtp


def _build_message(msg: EmailMessage, settings: EmailSettings) -> _StdEmailMessage:
    """Assemble an ``email.message.EmailMessage`` for ``smtplib``.

    Uses a display-name when set on the operator's settings;
    falls back to the bare username otherwise."""
    payload = _StdEmailMessage()
    if settings.from_display_name:
        payload["From"] = f"{settings.from_display_name} <{msg.from_addr}>"
    else:
        payload["From"] = msg.from_addr
    payload["To"] = msg.to
    if msg.cc:
        payload["Cc"] = ", ".join(msg.cc)
    # Bcc deliberately not added as a header — it's recipient-only.
    payload["Subject"] = msg.subject
    payload.set_content(msg.body)
    return payload


def _failure(error_message: str, raw: str | None) -> SendResult:
    return SendResult(
        ok=False,
        error_message=error_message,
        transport_response=(raw or "")[:_RESPONSE_TRUNCATE_AT] or None,
    )


# ── Graph backend (typed stub) ───────────────────────────────────────────


class GraphEmailTransport:
    """Microsoft Graph backend — typed stub, not yet implemented.

    The expected swap is roughly: ``httpx.post`` against
    ``https://graph.microsoft.com/v1.0/me/sendMail`` with the
    operator's delegated OAuth2 token (Entra ``Mail.Send`` scope),
    token cache fetched per-operator from a yet-to-exist
    ``OperatorOAuthToken`` table. Lands as its own future segment;
    today this class exists only so ``transport_for`` can dispatch
    on ``settings.transport == "graph"`` once that work begins.
    """

    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    def send(self, msg: EmailMessage) -> SendResult:  # pragma: no cover
        raise NotImplementedError(
            "GraphEmailTransport is a typed stub; the implementation "
            "ships in a future segment alongside an Entra Mail.Send "
            "scope grant + per-operator token cache."
        )


# ── Factory ──────────────────────────────────────────────────────────────


def transport_for(settings: EmailSettings) -> EmailTransport:
    """Pick the right backend for the supplied ``EmailSettings``.

    Raises ``ValueError`` for an unknown ``transport`` rather than
    silently falling back; the operator-settings save path
    constrains the value set, so an unknown value here is a code
    bug."""
    if settings.transport == "smtp":
        return SmtpEmailTransport(settings)
    raise ValueError(
        f"transport_for: unknown transport {settings.transport!r}; "
        f"expected 'smtp' (Graph backend ships in a future segment)."
    )
