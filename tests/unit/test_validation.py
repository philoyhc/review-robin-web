from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.schemas.validation import Severity
from app.services.validation import validate_session_setup


def _user(db: Session) -> User:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User) -> ReviewSession:
    s = ReviewSession(name="Spring", code="spring-2026", created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def test_empty_session_reports_no_reviewers_and_no_reviewees(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)

    issues = validate_session_setup(db, session)

    errors = [i for i in issues if i.severity is Severity.error]
    sources = {i.source for i in errors}
    assert "reviewers" in sources
    assert "reviewees" in sources


def test_populated_session_has_no_errors(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    db.add(Reviewer(session_id=session.id, name="Alice", email="alice@example.edu"))
    db.add(
        Reviewee(
            session_id=session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
        )
    )
    db.flush()

    issues = validate_session_setup(db, session)

    assert [i for i in issues if i.severity is Severity.error] == []


def test_duplicate_reviewer_email_is_flagged(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    db.add(Reviewer(session_id=session.id, name="Alice", email="dup@example.edu"))
    db.add(Reviewer(session_id=session.id, name="Alice2", email="DUP@example.edu"))
    db.add(
        Reviewee(
            session_id=session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
        )
    )
    db.flush()

    issues = validate_session_setup(db, session)

    dup = [i for i in issues if "Duplicate reviewer" in i.message]
    assert len(dup) == 1
    assert dup[0].severity is Severity.error


# --------------------------------------------------------------------------- #
# Segment 11G PR B — rule registry tests
# --------------------------------------------------------------------------- #


def test_registry_rule_keys_are_unique() -> None:
    """Stable, unique rule keys are the audit-log identity for each
    check; duplicates would silently corrupt the detail log."""
    from app.services.validation import REGISTERED_RULES

    keys = [rule.key for rule in REGISTERED_RULES]
    assert len(keys) == len(set(keys)), f"duplicate rule keys: {keys}"


def test_registry_rules_have_non_empty_metadata() -> None:
    """Every rule has a non-empty key, why, source, and a fix_url
    callable that returns a non-empty string."""
    from app.services.validation import REGISTERED_RULES

    fake_session = type(
        "_S", (), {"id": 1, "code": "x", "name": "x", "help_contact": None}
    )()
    for rule in REGISTERED_RULES:
        assert rule.key
        assert rule.source
        assert rule.why
        assert rule.fix_page_label
        url = rule.fix_url(fake_session)
        assert url and url.startswith("/operator/sessions/1/")


def test_validate_stamps_rule_key_and_fix_url(db: Session) -> None:
    """Each issue carries the registry-stamped ``rule_key`` and a
    ``fix_url`` resolving to the right Setup page."""
    user = _user(db)
    session = _session(db, user)  # fully empty → triggers reviewers/reviewees errors

    issues = validate_session_setup(db, session)

    by_rule = {i.rule_key: i for i in issues if i.rule_key}
    assert "reviewers.empty" in by_rule
    assert "reviewees.empty" in by_rule
    assert by_rule["reviewers.empty"].fix_url == (
        f"/operator/sessions/{session.id}/reviewers"
    )
    assert by_rule["reviewees.empty"].fix_url == (
        f"/operator/sessions/{session.id}/reviewees"
    )
    # fix_page_label is operator-facing copy, lands in the
    # "Fix on {label} ↗" anchor.
    assert by_rule["reviewers.empty"].fix_page_label == "Reviewers Setup"


def test_duplicate_email_carries_row_anchor(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    r1 = Reviewer(session_id=session.id, name="A1", email="dup@example.edu")
    r2 = Reviewer(session_id=session.id, name="A2", email="DUP@example.edu")
    db.add_all([r1, r2])
    db.add(
        Reviewee(
            session_id=session.id,
            name="C",
            email_or_identifier="c@example.edu",
        )
    )
    db.flush()

    issues = validate_session_setup(db, session)
    dup = [i for i in issues if i.rule_key == "reviewers.duplicate_email"]
    assert len(dup) == 1
    # Anchor points at the *first* duplicate's row.
    assert dup[0].fix_anchor in (
        f"#reviewer-row-{r1.id}",
        f"#reviewer-row-{r2.id}",
    )


def test_no_help_contact_emits_info_severity(db: Session) -> None:
    """The new info-severity rule fires by default (help_contact is
    null on a freshly-created session)."""
    user = _user(db)
    session = _session(db, user)
    issues = validate_session_setup(db, session)
    info = [
        i for i in issues if i.rule_key == "email_template.no_help_contact"
    ]
    assert len(info) == 1
    assert info[0].severity is Severity.info
    # Crucially info issues don't appear under errors → activation
    # gate keeps working.
    assert [i for i in issues if i.severity is Severity.error and i.rule_key == "email_template.no_help_contact"] == []


def test_no_display_fields_warning_fires_when_response_fields_exist(
    db: Session,
) -> None:
    """The new warning-severity rule fires only on instruments that
    have response fields but no display fields."""
    from app.db.models import Instrument, InstrumentResponseField
    from app.services.instruments import (
        ensure_default_response_type_definitions,
    )

    user = _user(db)
    session = _session(db, user)
    db.add(Reviewer(session_id=session.id, name="A", email="a@example.edu"))
    db.add(
        Reviewee(
            session_id=session.id,
            name="C",
            email_or_identifier="c@example.edu",
        )
    )
    instrument = Instrument(
        session_id=session.id, name="Test", description="Test instrument"
    )
    db.add(instrument)
    db.flush()
    rtds = ensure_default_response_type_definitions(db, session)
    db.add(
        InstrumentResponseField(
            instrument_id=instrument.id,
            field_key="rating",
            label="Rating",
            response_type_id=rtds["1-to-5int"].id,
            required=False,
            order=0,
        )
    )
    db.flush()

    issues = validate_session_setup(db, session)
    warns = [
        i for i in issues if i.rule_key == "instruments.no_display_fields"
    ]
    assert len(warns) == 1
    assert warns[0].severity is Severity.warning
    assert warns[0].fix_anchor == f"#instrument-{instrument.id}"
