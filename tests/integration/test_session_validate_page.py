"""Tests for the Validate page surface introduced in Segment 11G PR A.

The page replaces the thin issue-list body with a structured layout:
- Readiness summary card (verdict line, severity counts, last-validated
  marker, lifecycle-aware secondary line)
- Setup-coverage matrix (per-entity inventory the operator scans before
  reading the diagnostic issue list)
- Existing issue-list partial (extended with `id="issue-source-{source}"`
  anchors so the matrix can deep-link)

Subsequent 11G PRs add the rule-registry refactor + per-issue fix-links
(PR B), severity filter chips + "Why" disclosure (PR C), and the
activate-warns detour from Home (PR D).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession
from app.web import views


# --------------------------------------------------------------------------- #
# Setup helpers
# --------------------------------------------------------------------------- #


def _make_session(
    client: TestClient, db: Session, *, code: str = "vp"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair(
    client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str = "r@example.edu",
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nC,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    return review_session


def _activate(
    client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)


# --------------------------------------------------------------------------- #
# Lifecycle copy lookup — pure function
# --------------------------------------------------------------------------- #


def test_validate_lifecycle_copy_draft_clean() -> None:
    assert (
        views.validate_lifecycle_copy("draft", has_errors=False, has_warnings=False)
        == "Activate from the Next Action card on Session Home."
    )


def test_validate_lifecycle_copy_draft_with_errors() -> None:
    assert (
        views.validate_lifecycle_copy("draft", has_errors=True, has_warnings=False)
        == "Resolve the errors below before activating."
    )


def test_validate_lifecycle_copy_validated() -> None:
    assert (
        views.validate_lifecycle_copy("validated", has_errors=False, has_warnings=True)
        == "Setup is validated. Activate from Session Home."
    )


def test_validate_lifecycle_copy_ready() -> None:
    assert (
        "live" in views.validate_lifecycle_copy("ready", False, False)
        and "Setup is locked" in views.validate_lifecycle_copy("ready", False, False)
    )


# --------------------------------------------------------------------------- #
# Readiness summary card
# --------------------------------------------------------------------------- #


def test_readiness_summary_clean_verdict_renders_green(
    client: TestClient, db: Session
) -> None:
    """A draft session with reviewers + reviewees + assignments has no
    errors → "Ready to activate." with the verdict-clean accent."""
    review_session = _seed_pair(client, db, code="ready-verdict")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert "Ready to activate." in body
    assert "verdict-clean" in body


def test_readiness_summary_error_verdict_renders_red(
    client: TestClient, db: Session
) -> None:
    """A bare session (no reviewers / no reviewees) has multiple
    errors → "Has N errors." with the verdict-error accent."""
    review_session = _make_session(client, db, code="error-verdict")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # "Has N errors." with N > 1 (no reviewers + no reviewees + no
    # assignments).
    assert "errors." in body
    assert "verdict-error" in body


def test_readiness_summary_severity_counts_render(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="counts")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # Pills + "Validated just now" hint render together.
    assert 'class="pill pill-error"' in body
    assert 'class="pill pill-empty"' in body
    assert 'class="pill pill-count"' in body
    assert "Validated just now" in body


# --------------------------------------------------------------------------- #
# Setup-coverage matrix
# --------------------------------------------------------------------------- #


def test_setup_coverage_matrix_renders_canonical_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="cov-rows")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert "Setup coverage" in body
    for label in (
        "Session name",
        "Session code",
        "Reviewers",
        "Reviewees",
        "Instruments",
        "Assignments",
        "Email template",
        "Help contact",
    ):
        assert f">{label}</th>" in body, f"matrix row missing: {label}"


def test_setup_coverage_matrix_links_to_issue_source_anchor_when_issues(
    client: TestClient, db: Session
) -> None:
    """When a setup source has issues, the matrix's row carries a
    pill-error / pill-empty count that anchor-links to the matching
    section in the issue list (e.g. `#issue-source-reviewers`)."""
    review_session = _make_session(client, db, code="cov-links")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # Bare session has no reviewers → reviewers row carries an
    # error-pill anchor link to the issue-list anchor.
    assert 'href="#issue-source-reviewers"' in body
    # The issue-list partial now emits the matching anchor on its
    # per-source <h3>.
    assert 'id="issue-source-reviewers"' in body


def test_setup_coverage_matrix_omits_issue_pill_when_clean(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="cov-clean")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # When a session is fully populated, no error-pill anchors render
    # in the matrix.
    assert 'href="#issue-source-reviewers"' not in body


def test_validate_page_renders_fix_on_link_per_issue(
    client: TestClient, db: Session
) -> None:
    """Each issue carries a "Fix on {Setup page} ↗" anchor pointing
    at the rule's ``fix_url`` (with ``fix_anchor`` appended where the
    rule emits one)."""
    review_session = _make_session(client, db, code="fix-link")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # Bare session has no reviewers → reviewers.empty rule fires →
    # "Fix on Reviewers Setup ↗" link surfaces.
    assert (
        f'href="/operator/sessions/{review_session.id}/reviewers"'
        in body
    )
    assert "Fix on Reviewers Setup ↗" in body


def test_validate_page_renders_per_issue_id_anchors(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="issue-ids")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # rule_key + loop index combine into the per-issue id; every
    # registry-emitted issue carries an id="issue-{rule_key}-N".
    assert 'id="issue-reviewers.empty-1"' in body


# --------------------------------------------------------------------------- #
# Severity filter chips + per-source group counts + "Why" disclosure (PR C)
# --------------------------------------------------------------------------- #


def test_validate_page_renders_severity_chip_strip(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="chip-strip")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # Four chips render with their unfiltered totals.
    assert "All issues (" in body
    assert "Errors only (" in body
    assert "Warnings only (" in body
    assert "Info (" in body
    # Default no-filter state: All chip is active.
    assert "severity-chip active" in body
    assert 'aria-current="page"' in body


def test_validate_page_filter_errors_only(
    client: TestClient, db: Session
) -> None:
    """``?severity=error`` filters the issue list to errors and
    flips the All chip's active styling onto Errors only."""
    review_session = _make_session(client, db, code="errors-only")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate?severity=error"
    ).text
    # The assignments.no_mode warning is the only warning in the bare
    # session; under errors-only it should not appear in the body.
    assert "assignments.no_mode" not in body
    # Errors chip carries the active styling now.
    assert (
        'href="/operator/sessions/' in body
        and "/validate?severity=error" in body
    )


def test_validate_page_filter_no_match_shows_empty_message(
    client: TestClient, db: Session
) -> None:
    """``?severity=`` narrowing to zero matches renders the
    filter-empty placeholder."""
    review_session = _seed_pair(client, db, code="filter-empty")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate?severity=error"
    ).text
    # Seeded session has no errors → filter-empty message renders.
    assert "No issues match the current severity filter." in body


def test_validate_page_per_source_group_count_summary(
    client: TestClient, db: Session
) -> None:
    """Per-source <h3> carries an inline count summary line — e.g.
    ``Reviewers (1 error)`` — that respects the filter."""
    review_session = _make_session(client, db, code="grp-count")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    # Bare session has reviewers.empty error → "1 error" summary
    # under the Reviewers <h3>.
    assert "1 error" in body


def test_validate_page_renders_why_disclosure_per_issue(
    client: TestClient, db: Session
) -> None:
    """Each registered-rule issue ships a default-collapsed
    ``<details>`` with the rule's ``why`` paragraph."""
    review_session = _make_session(client, db, code="why-disclosure")
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert "Why this check?" in body
    # "<details" (no closing >) — actual element renders with the
    # "issue-why" class so this is a stable anchor.
    assert 'class="issue-why"' in body
    # Body of one of the rule.why paragraphs surfaces.
    assert "Activation creates per-reviewer invitations" in body


def test_validate_page_lifecycle_copy_for_ready_session(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _seed_pair(operator, db, code="ready-copy")
    _activate(operator, db, review_session)

    body = operator.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert "This session is live." in body
    assert "Setup is locked" in body


# --------------------------------------------------------------------------- #
# Activate-warns detour from Home (PR D)
# --------------------------------------------------------------------------- #


def _seed_validated_with_warnings(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Set up a session in validated state with one warning
    (assignments.no_mode) so the activate-warns detour path is
    reachable. Reviewers + reviewees imported, but no assignments
    generated."""
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nC,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # ?validated=1 marks the session validated when can_activate
    # (no errors). Warnings don't block.
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    db.refresh(review_session)
    assert review_session.status == "validated"
    return review_session


def test_session_home_validated_with_warnings_links_to_validate_detour(
    client: TestClient, db: Session
) -> None:
    """Per PR D, when a validated session has warnings the
    Next Action card's Activate button is an anchor to
    `/validate?activate=1` rather than a POST submit. The
    acknowledge_warnings checkbox is gone."""
    review_session = _seed_validated_with_warnings(
        client, db, code="home-detour"
    )
    body = client.get(f"/operator/sessions/{review_session.id}").text
    # Activate Session anchor points at the detour URL.
    assert (
        f'href="/operator/sessions/{review_session.id}/validate?activate=1"'
        in body
    )
    # No acknowledge_warnings checkbox on Home.
    assert 'name="acknowledge_warnings"' not in body
    # Warning-count line under the primary button surfaces.
    assert "warning" in body and "review on Validate" in body


def test_session_home_validated_no_warnings_keeps_direct_post(
    client: TestClient, db: Session
) -> None:
    """Validated session with zero warnings keeps the direct
    Activate POST — no detour."""
    review_session = _seed_pair(client, db, code="no-detour")
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    db.refresh(review_session)
    assert review_session.status == "validated"

    body = client.get(f"/operator/sessions/{review_session.id}").text
    # Direct POST form to /activate is present.
    assert (
        f'action="/operator/sessions/{review_session.id}/activate"'
        in body
    )
    # No detour anchor.
    assert (
        f'href="/operator/sessions/{review_session.id}/validate?activate=1"'
        not in body
    )


def test_validate_activate_param_renders_warning_banner(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_validated_with_warnings(
        client, db, code="banner-warn"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate?activate=1"
    ).text
    assert "Acknowledge warnings to activate" in body
    assert 'id="activate-confirm-banner"' in body
    assert "banner-scroll-target" in body
    # The acknowledge POST submit + Cancel link both render.
    assert "Acknowledge and activate" in body
    assert (
        f'href="/operator/sessions/{review_session.id}/validate"'
        in body
    )


def test_validate_activate_param_acknowledge_post_activates_session(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_validated_with_warnings(
        client, db, code="ack-post"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.status == "ready"


def test_validate_activate_param_on_draft_redirects_to_clean_url(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="draft-redir")
    # Session stays draft (no ?validated=1).
    response = client.get(
        f"/operator/sessions/{review_session.id}/validate?activate=1",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{review_session.id}/validate"
    )


def test_validate_activate_param_no_warnings_redirects(
    client: TestClient, db: Session
) -> None:
    """Validated session with no warnings: ?activate=1 has nothing
    to acknowledge → 303 to clean /validate URL."""
    review_session = _seed_pair(client, db, code="no-warn-redir")
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    db.refresh(review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/validate?activate=1",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{review_session.id}/validate"
    )
