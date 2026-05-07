"""Unit coverage for the canonical-shape audit helpers.

Helpers under test live in `app/services/audit.py`:

- `audit.changes(...)`, `audit.snapshot(...)`, `audit.counts(...)`,
  `audit.set_changes(...)` payload constructors.
- `audit.write_event(...)` shape composition (identity slots
  derived from `session=`, payload + orthogonal slots merged
  in, FK column derived from session).
- The `detail=` legacy back-compat path emits a
  ``DeprecationWarning`` under pytest so unmigrated callsites
  surface in CI.

The integration-level "this emit produces this row" coverage
lives in the per-feature integration tests; this file only
covers the helpers themselves in isolation.
"""
from __future__ import annotations

import warnings
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit


def _make_user_and_session(db: Session, code: str) -> tuple[User, ReviewSession]:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return user, review_session


# --------------------------------------------------------------------------- #
# Payload constructors
# --------------------------------------------------------------------------- #


def test_changes_serialises_datetimes_and_passes_scalars_through() -> None:
    when = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
    payload = audit.changes(
        {
            "name": ["Spring", "Spring v2"],
            "deadline": [None, when],
            "active": [True, False],
        }
    )
    assert payload.to_dict() == {
        "changes": {
            "name": ["Spring", "Spring v2"],
            "deadline": [None, "2026-05-07T12:00:00+00:00"],
            "active": [True, False],
        }
    }


def test_snapshot_mirrors_columns_and_serialises_dates() -> None:
    payload = audit.snapshot(
        {"id": 17, "code": "CS101", "deadline": date(2026, 6, 1), "name": "Final"}
    )
    assert payload.to_dict() == {
        "snapshot": {
            "id": 17,
            "code": "CS101",
            "deadline": "2026-06-01",
            "name": "Final",
        }
    }


def test_counts_keeps_only_named_integers() -> None:
    payload = audit.counts(reviewers=8, reviewees=13, assignments=104)
    assert payload.to_dict() == {
        "counts": {"reviewers": 8, "reviewees": 13, "assignments": 104}
    }


def test_set_changes_defaults_each_branch_to_empty_list() -> None:
    payload = audit.set_changes(updated=[{"key": "tag_2", "changes": {"label": ["A", "B"]}}])
    assert payload.to_dict() == {
        "set_changes": {
            "added": [],
            "removed": [],
            "updated": [{"key": "tag_2", "changes": {"label": ["A", "B"]}}],
        }
    }


# --------------------------------------------------------------------------- #
# write_event — canonical path
# --------------------------------------------------------------------------- #


def test_write_event_packs_identity_payload_and_orthogonal_slots(db: Session) -> None:
    user, review_session = _make_user_and_session(db, "wrt-canon")
    event = audit.write_event(
        db,
        event_type="session.updated",
        summary="Session wrt-canon updated",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"name": ["A", "B"]}),
        reason="operator_edit",
        refs={"reviewer_id": 42},
        context={"source": "edit_form"},
        correlation_id="corr-1",
    )
    assert event.session_id == review_session.id
    assert event.detail == {
        "session_id": review_session.id,
        "session_code": "wrt-canon",
        "changes": {"name": ["A", "B"]},
        "reason": "operator_edit",
        "refs": {"reviewer_id": 42},
        "context": {"source": "edit_form"},
    }


def test_write_event_with_session_none_omits_top_level_identity(db: Session) -> None:
    """session.deleted-style: FK column NULL, identity inside snapshot."""
    user, review_session = _make_user_and_session(db, "wrt-deleted")
    original_id = review_session.id
    db.delete(review_session)
    db.flush()

    event = audit.write_event(
        db,
        event_type="session.deleted",
        summary="Deleted session wrt-deleted",
        actor_user_id=user.id,
        session=None,
        payload=audit.snapshot(
            {"id": original_id, "code": "wrt-deleted", "name": "Wrt-Deleted"}
        ),
        correlation_id="corr-del",
    )
    assert event.session_id is None
    assert event.detail == {
        "snapshot": {"id": original_id, "code": "wrt-deleted", "name": "Wrt-Deleted"}
    }


def test_write_event_canonical_with_no_payload_returns_orthogonal_only(
    db: Session,
) -> None:
    """session.invalidated-style: reason without a payload envelope."""
    user, review_session = _make_user_and_session(db, "wrt-reason")
    event = audit.write_event(
        db,
        event_type="session.invalidated",
        summary="Session wrt-reason invalidated",
        actor_user_id=user.id,
        session=review_session,
        reason="setup_mutation",
        correlation_id="corr-inv",
    )
    assert event.detail == {
        "session_id": review_session.id,
        "session_code": "wrt-reason",
        "reason": "setup_mutation",
    }


def test_write_event_rejects_mixing_canonical_and_legacy_kwargs(db: Session) -> None:
    user, review_session = _make_user_and_session(db, "wrt-mix")
    with pytest.raises(TypeError, match="not both"):
        audit.write_event(
            db,
            event_type="session.updated",
            summary="x",
            actor_user_id=user.id,
            session=review_session,
            payload=audit.changes({"name": ["A", "B"]}),
            detail={"legacy": True},
        )


# --------------------------------------------------------------------------- #
# write_event — legacy back-compat
# --------------------------------------------------------------------------- #


def test_write_event_legacy_detail_path_still_writes_dict_as_is(db: Session) -> None:
    user, review_session = _make_user_and_session(db, "wrt-legacy")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        event = audit.write_event(
            db,
            event_type="legacy.event",
            summary="Legacy emit",
            actor_user_id=user.id,
            session_id=review_session.id,
            detail={"shape": "freeform", "n": 3},
        )
    assert event.session_id == review_session.id
    assert event.detail == {"shape": "freeform", "n": 3}
    deprecation_messages = [
        str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)
    ]
    assert any("legacy.event" in msg for msg in deprecation_messages), (
        "legacy detail= path should emit a DeprecationWarning under pytest "
        "so unmigrated callsites surface in CI"
    )


def test_write_event_legacy_call_without_detail_does_not_warn(db: Session) -> None:
    """No-detail legacy calls (rare but legal) shouldn't be flagged."""
    user, review_session = _make_user_and_session(db, "wrt-legacy-empty")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        audit.write_event(
            db,
            event_type="legacy.no_detail",
            summary="Empty legacy emit",
            actor_user_id=user.id,
            session_id=review_session.id,
        )
    assert not [
        w for w in caught if issubclass(w.category, DeprecationWarning)
    ]
