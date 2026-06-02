"""Unit tests for ``app.services.participant_tokens``."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import ReviewSession, User
from app.services.participant_tokens import (
    ParticipantTokenizer,
    participant_token,
)


def _session(
    db, *, code: str, created_at: datetime | None = None
) -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    sess = ReviewSession(
        name="Sess",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    if created_at is not None:
        sess.created_at = created_at
    db.add(sess)
    db.flush()
    return sess


def test_token_shape_per_role_prefix(db) -> None:
    sess = _session(db, code="tok-shape")
    assert participant_token(sess, "reviewer", 7).startswith("R-")
    assert participant_token(sess, "reviewee", 7).startswith("E-")
    assert participant_token(sess, "observer", 7).startswith("O-")


def test_token_hex_length(db) -> None:
    sess = _session(db, code="tok-hex")
    token = participant_token(sess, "reviewer", 1)
    prefix, _, digest = token.partition("-")
    assert prefix == "R"
    # ``digest_size=4`` ⇒ 8 hex chars.
    assert len(digest) == 8
    assert all(c in "0123456789abcdef" for c in digest)


def test_token_stable_for_same_inputs(db) -> None:
    sess = _session(db, code="tok-stable")
    a = participant_token(sess, "reviewer", 42)
    b = participant_token(sess, "reviewer", 42)
    assert a == b


def test_token_differs_per_individual(db) -> None:
    sess = _session(db, code="tok-ids")
    a = participant_token(sess, "reviewer", 1)
    b = participant_token(sess, "reviewer", 2)
    assert a != b


def test_token_differs_per_role(db) -> None:
    sess = _session(db, code="tok-roles")
    a = participant_token(sess, "reviewer", 1)
    b = participant_token(sess, "reviewee", 1)
    assert a != b


def test_token_differs_across_sessions(db) -> None:
    s1 = _session(
        db,
        code="tok-s1",
        created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    s2 = _session(
        db,
        code="tok-s2",
        created_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    a = participant_token(s1, "reviewer", 1)
    b = participant_token(s2, "reviewer", 1)
    assert a != b


def test_unknown_role_raises_key_error(db) -> None:
    sess = _session(db, code="tok-unknown-role")
    with pytest.raises(KeyError):
        participant_token(sess, "moderator", 1)


def test_token_changes_with_env_salt(db, monkeypatch) -> None:
    sess = _session(db, code="tok-env")
    monkeypatch.setenv("PARTICIPANT_TOKEN_SALT", "salt-one")
    a = participant_token(sess, "reviewer", 1)
    monkeypatch.setenv("PARTICIPANT_TOKEN_SALT", "salt-two")
    b = participant_token(sess, "reviewer", 1)
    assert a != b


def test_tokenizer_class_reuses_salt(db, monkeypatch) -> None:
    """``ParticipantTokenizer`` precomputes the salt once at
    construction — verifying that a later env-var change
    doesn't leak into the same tokenizer's outputs."""
    sess = _session(db, code="tok-class")
    monkeypatch.setenv("PARTICIPANT_TOKEN_SALT", "salt-one")
    tokenizer = ParticipantTokenizer(sess)
    first = tokenizer.token("reviewer", 1)
    monkeypatch.setenv("PARTICIPANT_TOKEN_SALT", "salt-two")
    second = tokenizer.token("reviewer", 1)
    assert first == second
