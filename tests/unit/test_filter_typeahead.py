"""Unit tests for the Manage Invitations / Responses typeahead glue.

Covers:
- `invitations_search_options` and `responses_search_options` produce
  the expected ``"Name (email)"`` / ``"Name (identifier)"`` labels in
  case-insensitive alphabetical order.
- `filter_invitations_rows` / `filter_responses_rows` interpret a
  picked-from-typeahead value (label format) as an exact email or
  identifier match, falling back to substring search otherwise.
"""

from __future__ import annotations

from app.db.models import Reviewee, Reviewer
from app.web import views


def _inv_row(*, name: str, email: str, summary_state: str = "not_started") -> views.InvitationsRow:
    reviewer = Reviewer(name=name, email=email)
    return views.InvitationsRow(
        reviewer=reviewer,
        invitation=None,
        email_status="not sent",
        email_sent_at=None,
        review_progress_state="not started",
        review_progress_done=0,
        review_progress_total=0,
        required_fields_done=0,
        required_fields_total=0,
        last_reminder_at=None,
    )


def _resp_row(*, name: str, identifier: str) -> views.ResponsesRow:
    reviewee = Reviewee(name=name, email_or_identifier=identifier)
    return views.ResponsesRow(
        reviewee=reviewee,
        coverage_state="no responses",
        reviewers_done=0,
        reviewers_total=0,
        last_response_at=None,
    )


# --- search_options helpers -------------------------------------------------


def test_invitations_search_options_yields_name_paren_email_sorted() -> None:
    rows = [
        _inv_row(name="Carol", email="carol@x.edu"),
        _inv_row(name="alice", email="alice@x.edu"),
        _inv_row(name="Bob", email="bob@x.edu"),
    ]

    options = views.invitations_search_options(rows)

    assert options == [
        "alice (alice@x.edu)",
        "Bob (bob@x.edu)",
        "Carol (carol@x.edu)",
    ]


def test_responses_search_options_yields_name_paren_identifier_sorted() -> None:
    rows = [
        _resp_row(name="Zara", identifier="zara@x.edu"),
        _resp_row(name="Alice", identifier="alice-id-001"),
    ]

    options = views.responses_search_options(rows)

    assert options == [
        "Alice (alice-id-001)",
        "Zara (zara@x.edu)",
    ]


# --- typeahead-pick filter path --------------------------------------------


def test_filter_invitations_label_format_does_exact_email_match() -> None:
    rows = [
        _inv_row(name="Alice", email="alice@x.edu"),
        _inv_row(name="Aliyah", email="aliyah@x.edu"),
    ]
    # Substring "ali" would match BOTH; the label-format pick narrows
    # to exactly Alice via the bracketed email.
    out = views.filter_invitations_rows(
        rows, status="all", search="Alice (alice@x.edu)"
    )

    assert len(out) == 1
    assert out[0].reviewer.email == "alice@x.edu"


def test_filter_invitations_substring_still_works_for_typed_text() -> None:
    rows = [
        _inv_row(name="Alice", email="alice@x.edu"),
        _inv_row(name="Aliyah", email="aliyah@x.edu"),
    ]

    out = views.filter_invitations_rows(rows, status="all", search="ali")

    assert {r.reviewer.email for r in out} == {
        "alice@x.edu",
        "aliyah@x.edu",
    }


def test_filter_responses_label_format_does_exact_identifier_match() -> None:
    rows = [
        _resp_row(name="Alice", identifier="alice@x.edu"),
        _resp_row(name="Aliyah", identifier="aliyah@x.edu"),
    ]

    out = views.filter_responses_rows(
        rows, status="all", search="Alice (alice@x.edu)"
    )

    assert len(out) == 1
    assert out[0].reviewee.email_or_identifier == "alice@x.edu"


def test_filter_responses_label_format_works_with_non_email_identifier() -> None:
    """Reviewees often have non-email identifiers (e.g. student IDs)."""
    rows = [
        _resp_row(name="Alice", identifier="STU-001"),
        _resp_row(name="Bob", identifier="STU-002"),
    ]

    out = views.filter_responses_rows(
        rows, status="all", search="Alice (STU-001)"
    )

    assert len(out) == 1
    assert out[0].reviewee.email_or_identifier == "STU-001"


def test_filter_invitations_label_without_at_sign_falls_back_to_substring() -> None:
    """A reviewer name with parens like ``"Alice (Smith)"`` must not be
    misread as a typeahead pick — the bracketed segment has no ``@``,
    so the helper falls back to substring search."""
    rows = [
        _inv_row(name="Alice (Smith)", email="alice@x.edu"),
        _inv_row(name="Bob", email="bob@x.edu"),
    ]

    out = views.filter_invitations_rows(
        rows, status="all", search="Alice (Smith)"
    )

    assert len(out) == 1
    assert out[0].reviewer.email == "alice@x.edu"
