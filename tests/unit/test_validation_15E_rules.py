"""Segment 15E PR 1 coverage for the new per-instrument validation
rules + the ``assignments.no_mode`` → ``assignments.no_included_pairs``
replacement.

Rules covered:

- ``instruments.no_rule_pinned`` — warning per unpinned instrument
  once the session has reviewers + reviewees. (Severity is
  ``warning`` rather than ``error`` to mirror sibling rules like
  ``assignments.instrument_empty`` and ``assignments.reviewer_missing``
  that produce the same operator-visible outcome — silent empty
  reviewer page.)
- ``assignments.no_included_pairs`` — warning when sum of
  ``included_count_per_instrument`` is zero. Replaces the retired
  ``assignments.no_mode`` rule (broader: catches all-deactivated
  case too, not just never-generated).
- ``instruments.stale_generated`` — warning per pinned instrument
  whose eligible-pair count diverges from its generated row count.
- ``instruments.zero_included`` — warning per instrument with
  ``generated_count > 0`` and ``included_count == 0``.

Plus a focused test for the lifted ``compute_staleness`` helper.
"""
from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.schemas.assignments import AssignmentMode
from app.schemas.validation import Severity
from app.services import assignments as assignments_service
from app.services.instruments import ensure_default_instrument
from app.services.validation import validate_session_setup


def _issues_with_key(issues: list, key: str) -> list:
    return [i for i in issues if i.rule_key == key]


def _seed(
    db: Session,
    *,
    code: str,
    with_reviewers: bool = True,
    with_reviewees: bool = True,
) -> tuple[User, ReviewSession, Instrument, SessionRuleSet]:
    """One reviewer, one reviewee, default instrument, one
    Full-Matrix SessionRuleSet (unpinned). Each test pins /
    generates / deactivates rows as needed."""
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="V15E", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    if with_reviewers:
        db.add(
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            )
        )
    if with_reviewees:
        db.add(
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            )
        )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    db.commit()
    return user, review_session, instrument, rule_set


def _generate(
    db: Session, *, review_session: ReviewSession, user: User
) -> None:
    assignments_service.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=uuid.uuid4().hex,
        mode=AssignmentMode.rule_based,
    )


# --------------------------------------------------------------------------- #
# compute_staleness helper
# --------------------------------------------------------------------------- #


def test_compute_staleness_false_when_unpinned() -> None:
    assert assignments_service.compute_staleness(None, 5, 0) is False


def test_compute_staleness_false_when_counts_match() -> None:
    assert assignments_service.compute_staleness(7, 4, 4) is False


def test_compute_staleness_true_when_pinned_and_divergent() -> None:
    # eligible > generated (never generated yet)
    assert assignments_service.compute_staleness(7, 4, 0) is True
    # generated > eligible (roster shrank post-generate)
    assert assignments_service.compute_staleness(7, 2, 4) is True


# --------------------------------------------------------------------------- #
# instruments.no_rule_pinned
# --------------------------------------------------------------------------- #


def test_no_rule_pinned_silent_without_rosters(db: Session) -> None:
    """Bare session (no reviewers / reviewees) → silent. The
    ``reviewers.empty`` / ``reviewees.empty`` errors cover that
    state more specifically."""
    _user, review_session, _instr, _rs = _seed(
        db,
        code="nrp-bare",
        with_reviewers=False,
        with_reviewees=False,
    )
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


def test_no_rule_pinned_fires_when_rosters_present_but_unpinned(
    db: Session,
) -> None:
    """Reviewers + reviewees imported, default instrument unpinned →
    error per unpinned instrument."""
    _user, review_session, instrument, _rs = _seed(db, code="nrp-fire")
    issues = validate_session_setup(db, review_session)
    fired = _issues_with_key(issues, "instruments.no_rule_pinned")
    assert len(fired) == 1
    assert fired[0].severity is Severity.warning
    assert fired[0].fix_anchor == f"#instrument-{instrument.id}"


def test_no_rule_pinned_silent_once_every_instrument_pinned(
    db: Session,
) -> None:
    _user, review_session, instrument, rule_set = _seed(db, code="nrp-pin")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


def test_no_rule_pinned_fires_per_unpinned_instrument(db: Session) -> None:
    """Multi-instrument session: one pinned, one unpinned → one
    error for the unpinned one."""
    _user, review_session, instrument_a, rule_set = _seed(
        db, code="nrp-multi"
    )
    instrument_a.rule_set_id = rule_set.id
    instrument_b = Instrument(
        session_id=review_session.id, name="Peer survey", order=99
    )
    db.add(instrument_b)
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    fired = _issues_with_key(issues, "instruments.no_rule_pinned")
    assert len(fired) == 1
    assert "Peer survey" in fired[0].message
    assert fired[0].fix_anchor == f"#instrument-{instrument_b.id}"


# --------------------------------------------------------------------------- #
# Wave 4 PR 2 — new-model carve-out on instruments.no_rule_pinned
# --------------------------------------------------------------------------- #


def test_no_rule_pinned_skips_new_model_instruments(db: Session) -> None:
    """Wave 4 PR 2 — a new-model instrument with NULL ``rule_set_id``
    no longer trips ``instruments.no_rule_pinned`` (the rule's pre-
    PR-2 message is wrong for new-model — Generate now produces a
    Full Matrix instead of skipping). The seeded default response
    fields (Rating + Comments) are ``visible=True`` out of the box,
    so the parallel ``no_visible_response_fields`` rule stays
    silent too."""
    _user, review_session, instrument, _rs = _seed(db, code="nrp-newmodel")
    instrument.is_new_model = True
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


# --------------------------------------------------------------------------- #
# instruments.no_visible_response_fields (Wave 4 PR 2)
# --------------------------------------------------------------------------- #


def test_no_visible_response_fields_silent_for_legacy(db: Session) -> None:
    """Legacy instrument with all response fields hidden → silent
    (the rule only fires for ``is_new_model=True``). The
    legacy-flavoured ``instruments.no_rule_pinned`` covers the
    legacy "not set up" gap."""
    _user, review_session, instrument, _rs = _seed(db, code="nvrf-legacy")
    db.execute(
        update(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .values(visible=False)
    )
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    assert (
        _issues_with_key(issues, "instruments.no_visible_response_fields")
        == []
    )


def test_no_visible_response_fields_fires_when_none_visible(
    db: Session,
) -> None:
    """New-model instrument with zero ``visible=True`` response fields
    → warning per instrument."""
    _user, review_session, instrument, _rs = _seed(db, code="nvrf-fire")
    instrument.is_new_model = True
    # Hide all seeded response fields.
    db.execute(
        update(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .values(visible=False)
    )
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    fired = _issues_with_key(
        issues, "instruments.no_visible_response_fields"
    )
    assert len(fired) == 1
    assert fired[0].severity is Severity.warning
    assert fired[0].fix_anchor == f"#instrument-{instrument.id}"


def test_no_visible_response_fields_silent_when_at_least_one_visible(
    db: Session,
) -> None:
    """Seeded defaults (Rating + Comments) are ``visible=True``, so
    a freshly-created new-model instrument is configured."""
    _user, review_session, instrument, _rs = _seed(db, code="nvrf-ok")
    instrument.is_new_model = True
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    assert (
        _issues_with_key(issues, "instruments.no_visible_response_fields")
        == []
    )


# --------------------------------------------------------------------------- #
# assignments.no_included_pairs (replaces assignments.no_mode)
# --------------------------------------------------------------------------- #


def test_no_included_pairs_fires_when_never_generated(db: Session) -> None:
    """Fresh session with rosters, no Generate → warning fires
    (sum included = 0)."""
    _user, review_session, _instr, _rs = _seed(db, code="nip-never")
    issues = validate_session_setup(db, review_session)
    fired = _issues_with_key(issues, "assignments.no_included_pairs")
    assert len(fired) == 1
    assert fired[0].severity is Severity.warning


def test_no_included_pairs_silent_post_clean_generate(db: Session) -> None:
    """Generate produces at least one included row → silent."""
    user, review_session, instrument, rule_set = _seed(db, code="nip-gen")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    _generate(db, review_session=review_session, user=user)
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "assignments.no_included_pairs") == []


def test_no_included_pairs_fires_when_all_deactivated(db: Session) -> None:
    """Generate, then deactivate every row → warning fires again."""
    user, review_session, instrument, rule_set = _seed(db, code="nip-deact")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    _generate(db, review_session=review_session, user=user)
    db.query(Assignment).filter(
        Assignment.session_id == review_session.id
    ).update({Assignment.include: False})
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    fired = _issues_with_key(issues, "assignments.no_included_pairs")
    assert len(fired) == 1


# --------------------------------------------------------------------------- #
# instruments.stale_generated
# --------------------------------------------------------------------------- #


def test_stale_generated_silent_when_no_instrument_pinned(
    db: Session,
) -> None:
    """No instrument has a rule_set_id → silent (no_rule_pinned
    carries the upstream signal)."""
    _user, review_session, _instr, _rs = _seed(db, code="stale-unpinned")
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.stale_generated") == []


def test_stale_generated_silent_after_wave_5_retirement(
    db: Session,
) -> None:
    """Wave 5 PR 5.1 — ``instruments.stale_generated`` retired as a
    no-op check. The per-rule eligibility helper retired with the
    operator-library tier; without it the rule can't compare
    eligible vs. generated counts. The rule key stays registered
    so audit history remains addressable, but it never fires."""
    user, review_session, instrument, rule_set = _seed(
        db, code="stale-retired"
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    # Pre-generate: would have fired pre-Wave-5; now silent.
    assert _issues_with_key(
        validate_session_setup(db, review_session),
        "instruments.stale_generated",
    ) == []
    _generate(db, review_session=review_session, user=user)
    # Post-roster change: would have fired pre-Wave-5; now silent.
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
        )
    )
    db.flush()
    db.commit()
    assert _issues_with_key(
        validate_session_setup(db, review_session),
        "instruments.stale_generated",
    ) == []


# --------------------------------------------------------------------------- #
# instruments.zero_included
# --------------------------------------------------------------------------- #


def test_zero_included_silent_when_never_generated(db: Session) -> None:
    """Generated count == 0 → silent. The
    ``assignments.no_included_pairs`` / ``instruments.no_rule_pinned``
    rules carry the upstream signals."""
    _user, review_session, _instr, _rs = _seed(db, code="zi-never")
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.zero_included") == []


def test_zero_included_silent_post_clean_generate(db: Session) -> None:
    """Generate + at least one included row → silent."""
    user, review_session, instrument, rule_set = _seed(db, code="zi-clean")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    _generate(db, review_session=review_session, user=user)
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.zero_included") == []


def test_zero_included_fires_when_all_rows_deactivated(db: Session) -> None:
    """Generate then deactivate every row on the instrument →
    warning fires."""
    user, review_session, instrument, rule_set = _seed(db, code="zi-deact")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    _generate(db, review_session=review_session, user=user)
    db.query(Assignment).filter(
        Assignment.session_id == review_session.id
    ).update({Assignment.include: False})
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    fired = _issues_with_key(issues, "instruments.zero_included")
    assert len(fired) == 1
    assert fired[0].severity is Severity.warning
    assert fired[0].fix_anchor == f"#instrument-{instrument.id}"
    assert "none are included" in fired[0].message


# --------------------------------------------------------------------------- #
# assignments.no_mode retirement
# --------------------------------------------------------------------------- #


def test_no_mode_rule_no_longer_registered(db: Session) -> None:
    """``assignments.no_mode`` is retired in 15E PR 1; the
    successor ``assignments.no_included_pairs`` covers a strictly
    broader case. No issue should ever surface with the legacy key."""
    _user, review_session, _instr, _rs = _seed(db, code="nm-retired")
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "assignments.no_mode") == []
