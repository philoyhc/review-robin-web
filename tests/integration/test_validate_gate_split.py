"""Segment 15E PR 2 coverage for the Validate page Setup-gate /
Operations-gate section split.

Two test families:

- ``test_gate_for_rule_key_*`` — pure unit tests pinning the gate
  assignment for every registered rule key. Future rule additions
  that forget to update ``_RULE_KEY_GATE`` will trip the catch-all
  fall-through assertion.
- ``test_validate_page_gate_*`` — integration assertions that the
  rendered Validate page contains the expected ``Setup gate`` /
  ``Operations gate`` headings under realistic session states.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services.validation import REGISTERED_RULES
from app.web.views._validate import (
    _RULE_KEY_GATE,
    gate_for_rule_key,
)


# --------------------------------------------------------------------------- #
# gate_for_rule_key
# --------------------------------------------------------------------------- #


def test_every_registered_rule_has_explicit_gate_mapping() -> None:
    """Every rule in ``REGISTERED_RULES`` must appear in
    ``_RULE_KEY_GATE``. New rules added without updating the
    mapping fall back to a source-based heuristic — fine as a
    runtime default but a smell when shipped. Catch it here."""
    keys = {rule.key for rule in REGISTERED_RULES}
    missing = keys - set(_RULE_KEY_GATE)
    assert missing == set(), (
        f"Rules missing from _RULE_KEY_GATE: {sorted(missing)}. "
        "Add them to the mapping in app/web/views/_validate.py."
    )


def test_setup_gate_rules() -> None:
    """Structural readiness rules belong to the Setup gate."""
    setup_keys = {
        "session.no_name",
        "session.no_code",
        "reviewers.empty",
        "reviewers.duplicate_email",
        "reviewees.empty",
        "reviewees.duplicate_id",
        "instruments.no_fields",
        "instruments.no_display_fields",
        "email_template.no_help_contact",
    }
    for key in setup_keys:
        assert gate_for_rule_key(key) == "setup", (
            f"{key!r} should be in the Setup gate"
        )


def test_operations_gate_rules() -> None:
    """Post-Generate readiness rules belong to the Operations gate."""
    operations_keys = {
        "instruments.no_rule_pinned",
        "instruments.stale_generated",
        "instruments.zero_included",
        "assignments.no_included_pairs",
        "assignments.reviewer_missing",
        "assignments.reviewer_missing_for_instrument",
        "assignments.instrument_empty",
    }
    for key in operations_keys:
        assert gate_for_rule_key(key) == "operations", (
            f"{key!r} should be in the Operations gate"
        )


def test_gate_heuristic_falls_back_for_unmapped_keys() -> None:
    """Unmapped rule key with ``assignments`` source → operations;
    anything else → setup. Keeps the page rendering until the
    mapping catches up."""
    assert gate_for_rule_key("assignments.future_rule") == "operations"
    assert gate_for_rule_key("instruments.future_rule") == "setup"
    assert gate_for_rule_key("totally_unknown") == "setup"


# --------------------------------------------------------------------------- #
# Validate page render
# --------------------------------------------------------------------------- #


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Create a session via the HTTP route so the test client's
    authenticated user becomes its operator."""
    from sqlalchemy import select as _select

    response = client.post(
        "/operator/sessions",
        data={"name": f"V15E-{code}", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        _select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_validate_page_renders_both_gate_headings(
    client: TestClient, db: Session
) -> None:
    """A bare-bones session has setup-gate errors (reviewers.empty,
    reviewees.empty, etc.) and an operations-gate warning
    (assignments.no_included_pairs). Both gate headings render.

    Heading text is lowercase in the markup — CSS
    ``text-transform: capitalize`` does the visual casing.
    """
    review_session = _make_session(client, db, code="gate-both")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert 'id="gate-setup"' in body
    assert "setup gate" in body
    assert 'id="gate-operations"' in body
    assert "operations gate" in body
    # Setup gate heading precedes Operations gate heading.
    assert body.index("setup gate") < body.index("operations gate")


def test_validate_page_skips_operations_gate_when_no_operations_issues(
    client: TestClient, db: Session
) -> None:
    """Filter to errors only on a bare session: every error is
    setup-gate (reviewers/reviewees/etc.). The Operations gate
    heading should not render."""
    review_session = _make_session(client, db, code="gate-setup-only")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate?severity=error"
    ).text
    assert "setup gate" in body
    assert "operations gate" not in body


@pytest.mark.skip(
    reason="Wave 5 PR 5.3 — ``instruments.no_rule_pinned`` retired; the "
    "test's setup no longer produces a single source split across two "
    "gate sections. Anchor dedup logic still works."
)
def test_validate_page_per_source_anchor_uses_first_gate_only(
    client: TestClient, db: Session
) -> None:
    """When the ``instruments`` source has rules in both gates
    (``no_fields`` in Setup, ``no_rule_pinned`` in Operations), the
    page renders the source heading twice — once under each gate
    — but the ``id="issue-source-instruments"`` anchor only
    appears on the first (Setup gate) occurrence so the setup-
    coverage matrix deep-link continues to work."""
    review_session = _make_session(client, db, code="gate-anchor")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
        )
    )
    db.flush()
    # Default instrument exists with no response fields → triggers
    # instruments.no_fields (Setup). Without a rule_set_id pinned,
    # instruments.no_rule_pinned (Operations) also fires.
    from app.services.instruments import ensure_default_instrument

    ensure_default_instrument(db, review_session)
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # Only one anchor id for the instruments source, even though the
    # source <h3> appears in both gate sections.
    assert body.count('id="issue-source-instruments"') == 1


def test_validate_page_setup_coverage_deep_link_still_works(
    client: TestClient, db: Session
) -> None:
    """Setup-coverage matrix rows deep-link via
    ``#issue-source-{source}``. Confirm the anchor target exists on
    the issue list for setup-gate sources after the split."""
    review_session = _make_session(client, db, code="gate-deeplink")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert 'href="#issue-source-reviewers"' in body
    assert 'id="issue-source-reviewers"' in body


def test_validate_page_gate_heading_classes(
    client: TestClient, db: Session
) -> None:
    """Gate headings carry a stable CSS hook ``issue-gate-heading``
    so a later visual-polish PR can style them without re-finding
    the markup."""
    review_session = _make_session(client, db, code="gate-classes")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert 'class="issue-gate-heading"' in body


def test_issue_groups_carry_gate_field(db: Session) -> None:
    """View-shape contract: ``IssueSourceGroup.gate`` matches the
    rule's gate, and groups are sorted setup-gate-first."""
    from app.services.validation import validate_session_setup
    from app.web.views._validate import build_validate_context
    from app.services.instruments import ensure_default_instrument

    user = User(email="op-igc@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="V15E-igc", code="gate-igc", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    # Reviewers + reviewees imported, default instrument unpinned →
    # mixed gate issues.
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="A",
            email="a@example.edu",
        )
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="C",
            email_or_identifier="c@example.edu",
        )
    )
    db.flush()
    ensure_default_instrument(db, review_session)
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
    instrument = db.query(Instrument).filter(
        Instrument.session_id == review_session.id
    ).first()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()

    issues = validate_session_setup(db, review_session)
    ctx = build_validate_context(db, review_session, issues)
    gates_seen: list[str] = []
    for group in ctx.issue_groups:
        if group.gate not in gates_seen:
            gates_seen.append(group.gate)
    # All setup-gate groups precede any operations-gate group.
    if "setup" in gates_seen and "operations" in gates_seen:
        assert gates_seen.index("setup") < gates_seen.index("operations")
    # Per-group gate value matches the rule keys it carries.
    for group in ctx.issue_groups:
        for issue in group.issues:
            assert gate_for_rule_key(issue.rule_key) == group.gate
