"""Email transport interface + SMTP backend (Segment 11E PR 5).

This module is the "transport-agnostic send abstraction" the
segment plan calls for. It defines the ``EmailTransport`` Protocol,
ships a concrete ``SmtpEmailTransport`` over ``smtplib``, and
ships ``GraphEmailTransport`` over the host's mailer (segment 14F:
delegated Graph as the operator, the send path in use). The factory
``transport_for(settings)`` dispatches the per-operator SMTP settings
on ``settings.transport``, kept for a deployment outside Microsoft 365
(``spec/settings_inventory.md``).

``app.services.email_dispatch`` is the caller: it claims an outbox
row, sends it through a transport, and stamps the outcome.

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
from email.utils import formataddr
from typing import Protocol

from app.services.operator_settings import EmailSettings
from cordware import graph

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
    cc: list[str] = field(default_factory=list[str])
    bcc: list[str] = field(default_factory=list[str])
    reply_to: str | None = None
    #: Graph's ``saveToSentItems`` (14C Item 2's toggle, off by default).
    #: The SMTP transport ignores it: SMTP has no Sent Items.
    save_to_sent_items: bool = False


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
                f"SmtpEmailTransport requires settings.transport='smtp', got {settings.transport!r}"
            )
        self._settings = settings

    def send(self, msg: EmailMessage) -> SendResult:
        if _has_line_break(msg, self._settings):
            # Refused before anything is built or sent: a CR or LF in a
            # header value, a recipient or the envelope sender would
            # start a new header or SMTP command (findings O10). Newer
            # stdlibs refuse these too, but with a ``ValueError`` after
            # connecting, which would escape this method's SendResult.
            return _failure(
                "The message has a line break in its sender, subject or "
                "recipients, so it was not sent.",
                None,
            )
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
                "Authentication failed. Check the SMTP username and app password.",
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
                "Couldn't connect to the SMTP server. Check the host and port.",
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
        # ``formataddr`` quotes a name holding ``,`` / ``"`` / ``<`` and
        # encodes a non-ASCII one, which an f-string does not.
        payload["From"] = formataddr((settings.from_display_name, msg.from_addr))
    else:
        payload["From"] = msg.from_addr
    payload["To"] = msg.to
    if msg.cc:
        payload["Cc"] = ", ".join(msg.cc)
    # Bcc deliberately not added as a header — it's recipient-only.
    payload["Subject"] = msg.subject
    payload.set_content(msg.body)
    return payload


def _has_line_break(msg: EmailMessage, settings: EmailSettings) -> bool:
    """Whether any value bound for a header or an SMTP envelope carries
    a CR or LF. The body is exempt: it is content, not a header."""
    values = [
        settings.username or "",
        msg.from_addr,
        msg.from_display_name or "",
        settings.from_display_name or "",
        msg.to,
        msg.subject,
        *msg.cc,
        *msg.bcc,
    ]
    return any("\r" in value or "\n" in value for value in values)


def _failure(error_message: str, raw: str | None) -> SendResult:
    return SendResult(
        ok=False,
        error_message=error_message,
        transport_response=(raw or "")[:_RESPONSE_TRUNCATE_AT] or None,
    )


# ── Graph backend (segment 14F) ──────────────────────────────────────────

#: Operator-facing copy for each way a Graph send can fail. The kind
#: (with its status and Graph's code) goes on the outbox row as the
#: transport response; this sentence is what the page shows.
_GRAPH_FAILURE_COPY: dict[str, str] = {
    "no_token": "You are not signed in to Microsoft for sending. Reload the page and try again.",
    "unauthorized": "Your Microsoft sign-in has expired. Reload the page and try again.",
    "forbidden": "Microsoft refused to send this from your mailbox.",
    "throttled": "Microsoft is limiting how fast mail can be sent. Try again in a minute.",
    "server": (
        "Microsoft could not take the message. It may or may not have gone; "
        "check before sending again."
    ),
    "network": (
        "The connection to Microsoft failed. It may or may not have gone; "
        "check before sending again."
    ),
    "bad_response": "Microsoft did not accept the message.",
}


class GraphEmailTransport:
    """Sends through the host's ``Mailer`` (``cordware.graph.mailer_for``):
    delegated ``/me/sendMail`` as the signed-in operator, or the fake
    mailer under fake auth. The sender is the operator's own mailbox,
    so ``from_addr`` and ``from_display_name`` are not sent: Graph sets
    the From itself (author, 2026-11-02)."""

    backend = "graph"

    def __init__(self, mailer: graph.Mailer) -> None:
        self._mailer = mailer

    def send(self, msg: EmailMessage) -> SendResult:
        message = graph.MailMessage(
            to=msg.to,
            subject=msg.subject,
            body=msg.body,
            cc=tuple(msg.cc),
            bcc=tuple(msg.bcc),
            reply_to=msg.reply_to,
            save_to_sent_items=msg.save_to_sent_items,
        )
        try:
            self._mailer.send_mail(message)
        except graph.GraphError as exc:
            return _failure(_GRAPH_FAILURE_COPY.get(exc.kind, "The send failed."), exc.reason)
        return SendResult(ok=True)


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
        f"expected 'smtp' (Graph is GraphEmailTransport over the request's mailer)."
    )
