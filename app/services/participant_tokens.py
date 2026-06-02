"""Per-participant tokens for Anonymized observer surfaces.

Computes a stable per-session opaque short hash for one
``(role, individual_id)`` pair without persisting anything.

The salt mixes a workspace-level secret (the
``PARTICIPANT_TOKEN_SALT`` env var, with a hardcoded default for
local + test runs) with the session's creation-time ISO
timestamp, so:

- the same individual gets the same token across re-renders and
  across redeploys (env var stays put);
- tokens differ across sessions even when the env var is shared
  (every session has a distinct ``created_at``);
- the token is opaque to a consumer who doesn't know the salt,
  so it doesn't disclose the individual's identity or insertion
  order.

Format: ``"<prefix>-<hex8>"`` — ``R`` / ``E`` / ``O`` prefix +
8 hex chars (32-bit blake2b digest). Compact enough to talk
about in support ("which row is ``R-a3f8b2c1``?") yet wide
enough that collisions inside a single session are vanishingly
rare.

See ``guide/observers.md`` "Token design — decisions
(2026-06-02)" for the design rationale.
"""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import ReviewSession


_ENV_SALT_KEY = "PARTICIPANT_TOKEN_SALT"
_DEFAULT_SALT = "review-robin-web-default-token-salt"
_DIGEST_BYTES = 4  # 8 hex chars

_ROLE_PREFIXES: dict[str, str] = {
    "reviewer": "R",
    "reviewee": "E",
    "observer": "O",
}


class ParticipantTokenizer:
    """Bound to one session. Precomputes the per-session salt
    prefix at construction so the per-individual token method
    only does the digest. Use this when computing many tokens
    in one request (the collation surface).
    """

    __slots__ = ("_salt_prefix",)

    def __init__(self, review_session: "ReviewSession") -> None:
        env_salt = os.environ.get(_ENV_SALT_KEY, _DEFAULT_SALT)
        created_at = review_session.created_at
        created_token = (
            created_at.isoformat() if created_at is not None else "0"
        )
        self._salt_prefix = f"{env_salt}|{created_token}"

    def token(self, role: str, individual_id: int) -> str:
        if role not in _ROLE_PREFIXES:
            raise KeyError(role)
        raw = f"{self._salt_prefix}|{role}|{individual_id}"
        digest = hashlib.blake2b(
            raw.encode("utf-8"), digest_size=_DIGEST_BYTES
        ).hexdigest()
        return f"{_ROLE_PREFIXES[role]}-{digest}"


def participant_token(
    review_session: "ReviewSession",
    role: str,
    individual_id: int,
) -> str:
    """Convenience wrapper for one-shot calls. The
    ``ParticipantTokenizer`` class is the right choice when
    computing many tokens per request."""
    return ParticipantTokenizer(review_session).token(role, individual_id)
