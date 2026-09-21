"""Segment 15E PR 1 coverage for the new per-instrument validation
rules + the ``assignments.no_mode`` → ``assignments.no_included_pairs``
replacement.

Rules covered:

- ``instruments.no_rule_pinned`` — **inert since Wave 5 PR 5.3**: a
  NULL ``rule_set_id`` is the Full Matrix default, so an unpinned
  instrument is never "not set up". It raised a warning per unpinned
  instrument when this file was written; the tests below now assert
  its silence, and the bullet said otherwise until 19R Item 6.
- ``assignments.no_included_pairs`` — warning when sum of
  ``included_count_per_instrument`` is zero. Replaces the retired
  ``assignments.no_mode`` rule (broader: catches all-deactivated
  case too, not just never-generated).
- ``instruments.stale_generated`` — warning per instrument whose
  **materialized rows** have fallen out of step with what the engine
  would produce now. Not a count comparison and not gated on pinning:
  the verdict is the engine's own reconcile diff via
  ``assignments.staleness_by_instrument``, and an instrument that has
  never generated is not flagged. The count-versus-count,
  pinned-only basis this bullet described was
  ``compute_staleness``'s, retired unused in 19R Item 8.
- ``instruments.zero_included`` — warning per instrument with
  ``generated_count > 0`` and ``included_count == 0``.
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


def test_no_rule_pinned_silent_after_wave_5(
    db: Session,
) -> None:
    """Wave 5 PR 5.3 — ``instruments.no_rule_pinned`` retired as a
    no-op check. Every instrument now defaults to Full Matrix on
    untouched Band 1 (Wave 4 PR 1), so a NULL ``rule_set_id`` is
    never "not set up." The rule key stays registered so audit
    history remains addressable."""
    _user, review_session, _instrument, _rs = _seed(db, code="nrp-retired")
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


def test_no_rule_pinned_silent_once_every_instrument_pinned(
    db: Session,
) -> None:
    _user, review_session, instrument, rule_set = _seed(db, code="nrp-pin")
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


def test_no_rule_pinned_silent_per_unpinned_instrument_after_wave_5(
    db: Session,
) -> None:
    """Wave 5 PR 5.3 — multi-instrument sessions with some pinned
    and some unpinned no longer trigger the retired rule. Every
    instrument defaults to Full Matrix on untouched Band 1."""
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
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


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
    db.flush()
    db.commit()
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.no_rule_pinned") == []


# --------------------------------------------------------------------------- #
# instruments.no_visible_response_fields (Wave 4 PR 2)
# --------------------------------------------------------------------------- #


def test_no_visible_response_fields_fires_when_all_hidden(db: Session) -> None:
    """Wave 5 PR 5.3 — every instrument is now subject to the
    no-visible-response-fields rule (the legacy carve-out
    retired). An instrument with every response-field row's
    ``visible=False`` trips the warning."""
    _user, review_session, instrument, _rs = _seed(db, code="nvrf-hidden")
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
    assert fired[0].fix_anchor == f"#instrument-{instrument.id}"


def test_no_visible_response_fields_fires_when_none_visible(
    db: Session,
) -> None:
    """New-model instrument with zero ``visible=True`` response fields
    → warning per instrument."""
    _user, review_session, instrument, _rs = _seed(db, code="nvrf-fire")
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


def test_stale_generated_silent_before_anything_is_generated(
    db: Session,
) -> None:
    """Nothing has been materialized → silent, because staleness means
    *rows that have fallen out of step* and there are no rows.

    The seeded session is also unpinned, which is why this test used to
    say the silence came from `no_rule_pinned` carrying the signal.
    It does not: since Wave 5 PR 5.3 an unpinned instrument generates
    like any other, and the decision is
    ``stale=bool(diff.existing_rows) and …`` in the engine
    (19R Item 6)."""
    _user, review_session, _instr, _rs = _seed(db, code="stale-unpinned")
    issues = validate_session_setup(db, review_session)
    assert _issues_with_key(issues, "instruments.stale_generated") == []


def test_stale_generated_fires_once_rows_fall_out_of_step(
    db: Session,
) -> None:
    """Silent before Generate, loud after a roster change. Segment 19N.

    Between Wave 5 PR 5.1 and 19N this rule was a **registered no-op** —
    it sat in the registry with a severity, a fix link and a ``why``
    describing exactly this situation, and returned nothing. An operator
    running Validate got a clean bill on the one thing it exists to
    catch.

    The two halves are different properties, not one:

    - **Before Generate: still silent**, and now deliberately so.
      Never-generated is not staleness — every fresh session would light
      up, and an always-stale badge trains the operator to ignore it.
      The Workflow card's Generate step carries that case.
    - **After a roster change: fires.** The materialised rows no longer
      match what the engine would produce, which is the definition.
    """
    user, review_session, instrument, rule_set = _seed(
        db, code="stale-retired"
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    # Nothing materialised yet — not stale, by design.
    assert _issues_with_key(
        validate_session_setup(db, review_session),
        "instruments.stale_generated",
    ) == []
    _generate(db, review_session=review_session, user=user)
    # Freshly generated — in step with the engine, so still silent.
    assert _issues_with_key(
        validate_session_setup(db, review_session),
        "instruments.stale_generated",
    ) == []
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
        )
    )
    db.flush()
    db.commit()
    # The added reviewer is in no assignment: the rows are now stale.
    issues = _issues_with_key(
        validate_session_setup(db, review_session),
        "instruments.stale_generated",
    )
    assert len(issues) == 1, (
        "a reviewer added after Generate should raise the staleness "
        f"warning; got {issues}"
    )
    assert issues[0].severity is Severity.warning


# --------------------------------------------------------------------------- #
# instruments.zero_included
# --------------------------------------------------------------------------- #


def test_zero_included_silent_when_never_generated(db: Session) -> None:
    """Generated count == 0 → silent. ``assignments.no_included_pairs``
    carries the upstream signal; ``instruments.no_rule_pinned`` carries
    nothing, being inert since Wave 5 PR 5.3."""
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
