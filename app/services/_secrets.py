"""Symmetric encryption for at-rest secrets.

Today's only caller is ``app.services.operator_settings`` for SMTP
passwords; the helper is general enough to take other secrets if a
future segment needs them.

**Fail-loud on missing / malformed key.** ``encrypt_password`` /
``decrypt_password`` raise ``MissingEncryptionKey`` when
``settings.smtp_encryption_key`` is unset or doesn't decode as a
valid Fernet key, rather than silently writing unrecoverable
ciphertext or losing decryption later. Tests / local dev that don't
exercise the operator Settings page never trigger the check, so
the missing-key check is lazy (at first use) rather than at
import / startup.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class MissingEncryptionKey(RuntimeError):
    """Raised when SMTP_ENCRYPTION_KEY isn't configured or doesn't
    parse as a valid Fernet key. Surface as a 500 with operator-
    actionable copy ("Configure SMTP_ENCRYPTION_KEY in deployment
    settings") rather than the default Fernet error message."""


def _fernet() -> Fernet:
    key = settings.smtp_encryption_key
    if not key:
        raise MissingEncryptionKey(
            "SMTP_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and set it in "
            "deployment settings before saving SMTP credentials."
        )
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise MissingEncryptionKey(
            "SMTP_ENCRYPTION_KEY is not a valid Fernet key "
            "(must be a 32-byte url-safe Base64-encoded string). "
            "Regenerate via `Fernet.generate_key()`."
        ) from exc


def encrypt_password(plaintext: str) -> bytes:
    """Returns Fernet ciphertext bytes. Empty / whitespace plaintext
    is rejected — the operator-settings layer normalises blank input
    to ``None`` before reaching here, so an empty plaintext means a
    caller bug."""
    if not plaintext:
        raise ValueError("encrypt_password: plaintext must be non-empty")
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_password(ciphertext: bytes) -> str:
    """Returns the plaintext password. Re-raises the underlying
    ``InvalidToken`` (a ``cryptography`` exception) so the caller can
    distinguish "rotated key" from "missing key" if they need to."""
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        # Re-raise as-is. A token-mismatch usually means
        # ``SMTP_ENCRYPTION_KEY`` rotated since the row was written;
        # operator action is to clear + re-enter the password.
        raise
