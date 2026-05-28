"""Integration tests for the Operations-row Previews page (segment 11F PR A).

Covers the reviewer picker (typeahead + datalist + Apply + Prev/Next +
Random) and the page's empty-state behaviors. Artifact cards land in
PRs B-E and have their own test files.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _create_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _import_reviewers(
    client: TestClient, session_id: int, csv_body: bytes
) -> None:
    response = client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={"file": ("r.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text


def test_previews_page_renders_workflow_card(
    client: TestClient, db: Session
) -> None:
    """Per spec/workflow_card.md — the Previews page hosts
    the Workflow card. ``next_action_return_to=previews`` flows
    into the card's forms; full ``value="previews"`` flow-through
    is covered by the cross-page tests in
    test_assignments_next_action_return_to.py (the partial is
    identical regardless of host page)."""
    session = _create_session(client, db, code="prev-card")
    body = client.get(f"/operator/sessions/{session.id}/previews").text
    assert 'id="next-action"' in body
    assert "<h2>Workflow</h2>" in body


def test_first_load_renders_unselected_picker_and_pick_prompt(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-empty-pick")
    _import_reviewers(
        client,
        session.id,
        (
            b"ReviewerName,ReviewerEmail\n"
            b"Alice,alice@example.edu\n"
            b"Bob,bob@example.edu\n"
        ),
    )

    response = client.get(f"/operator/sessions/{session.id}/previews")

    assert response.status_code == 200
    body = response.text
    # Picker rendered with no current selection.
    assert "Pick a reviewer above" in body or "Pick one to preview" in body
    # The "Reviewer N of M" line should not render when nothing's selected.
    assert "Reviewer 1 of" not in body
    # Prev/Next anchors are aria-disabled when no reviewer is selected.
    assert 'aria-disabled="true"' in body


def test_valid_reviewer_email_selects_and_shows_count(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-select")
    _import_reviewers(
        client,
        session.id,
        (
            b"ReviewerName,ReviewerEmail\n"
            b"Alice,alice@example.edu\n"
            b"Bob,bob@example.edu\n"
            b"Carol,carol@example.edu\n"
        ),
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "bob@example.edu"},
    )

    assert response.status_code == 200
    body = response.text
    # Reviewers are sorted alphabetically by email, so Bob is index 1 of 3.
    assert "Reviewer 2 of 3" in body
    assert "bob@example.edu" in body
    # No "no match" note when the email resolves cleanly.
    assert "No reviewer matched" not in body


def test_unmatched_email_shows_no_match_note_does_not_404(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-nomatch")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "ghost@example.edu"},
    )

    assert response.status_code == 200
    body = response.text
    assert "No reviewer matched" in body
    assert "ghost@example.edu" in body
    # Did NOT fall back to first-reviewer; "Reviewer 1 of" must not render.
    assert "Reviewer 1 of" not in body


def test_label_format_value_resolves_via_paren_email(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-label")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice Smith,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "Alice Smith (alice@example.edu)"},
    )

    assert response.status_code == 200
    assert "Reviewer 1 of 1" in response.text
    assert "No reviewer matched" not in response.text


def test_random_post_redirects_to_a_session_reviewer(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-random")
    _import_reviewers(
        client,
        session.id,
        (
            b"ReviewerName,ReviewerEmail\n"
            b"Alice,alice@example.edu\n"
            b"Bob,bob@example.edu\n"
            b"Carol,carol@example.edu\n"
        ),
    )

    response = client.post(
        f"/operator/sessions/{session.id}/previews/random",
        follow_redirects=False,
    )

    assert response.status_code == 303
    parsed = urlparse(response.headers["location"])
    assert parsed.path == f"/operator/sessions/{session.id}/previews"
    qs = parse_qs(parsed.query)
    assert qs.get("reviewer_email"), response.headers["location"]
    chosen = qs["reviewer_email"][0]
    assert chosen in {
        "alice@example.edu",
        "bob@example.edu",
        "carol@example.edu",
    }


def test_random_post_on_empty_session_redirects_without_param(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-random-empty")

    response = client.post(
        f"/operator/sessions/{session.id}/previews/random",
        follow_redirects=False,
    )

    assert response.status_code == 303
    parsed = urlparse(response.headers["location"])
    assert parsed.path == f"/operator/sessions/{session.id}/previews"
    assert parsed.query == ""


def test_empty_session_renders_disabled_picker_and_empty_state(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-zero")

    response = client.get(f"/operator/sessions/{session.id}/previews")

    assert response.status_code == 200
    body = response.text
    assert "No reviewers configured" in body
    # The text input and Apply/Random buttons are all disabled when
    # no reviewers exist.
    assert "disabled" in body


def test_datalist_carries_one_option_per_reviewer(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-datalist")
    _import_reviewers(
        client,
        session.id,
        (
            b"ReviewerName,ReviewerEmail\n"
            b"Alice,alice@example.edu\n"
            b"Bob,bob@example.edu\n"
            b"Carol,carol@example.edu\n"
        ),
    )

    response = client.get(f"/operator/sessions/{session.id}/previews")

    assert response.status_code == 200
    body = response.text
    # Three reviewers => three <option> entries inside the datalist.
    datalist_start = body.index('<datalist id="preview-picker-options">')
    datalist_end = body.index("</datalist>", datalist_start)
    datalist_block = body[datalist_start:datalist_end]
    assert datalist_block.count("<option") == 3
    assert "Alice (alice@example.edu)" in datalist_block
    assert "Bob (bob@example.edu)" in datalist_block
    assert "Carol (carol@example.edu)" in datalist_block


def test_prev_next_links_wrap_around_endpoints(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-wrap")
    _import_reviewers(
        client,
        session.id,
        (
            b"ReviewerName,ReviewerEmail\n"
            b"Alice,alice@example.edu\n"
            b"Bob,bob@example.edu\n"
            b"Carol,carol@example.edu\n"
        ),
    )

    # Selecting the first reviewer should wrap Prev to the last.
    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    )
    body = response.text
    assert "reviewer_email=carol%40example.edu" in body  # Prev wraps
    assert "reviewer_email=bob%40example.edu" in body  # Next advances

    # Selecting the last reviewer should wrap Next to the first.
    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "carol@example.edu"},
    )
    body = response.text
    assert "reviewer_email=bob%40example.edu" in body  # Prev steps back
    assert "reviewer_email=alice%40example.edu" in body  # Next wraps


# --- Email previews region (PR B) ---------------------------------------- #


def test_email_region_not_rendered_when_no_reviewer_selected(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-email-empty-pick")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(f"/operator/sessions/{session.id}/previews")

    assert response.status_code == 200
    body = response.text
    # The email region only appears once a reviewer is picked. Look
    # for the rendered `<div>` rather than the bare class name (the
    # class also appears in <style> rules from base.html).
    assert '<div class="card email-preview-card">' not in body
    # The empty-state "Pick a reviewer" card from PR A still renders.
    assert "Pick a reviewer" in body


def test_invitation_tab_active_by_default(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-email-default")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    )

    body = response.text
    # Invitation tab is the disabled "current view" button.
    assert (
        '<span class="nav-tab active" aria-current="page">Invitation</span>'
        in body
    )
    # All three tabs ship live render adapters as of Segment 11F PR D
    # (reminder) + Segment 11E PR 6 (responses-received), so neither
    # renders as a "(coming soon)" button anymore.
    assert "Reminder (coming soon)" not in body
    assert "Responses received (coming soon)" not in body
    # Tab links carry an ``#email-previews`` fragment so switching
    # tabs scrolls back to the email-preview card after the full-page
    # reload, instead of jumping to the top of the page.
    assert "email=responses_received#email-previews" in body
    assert "email=reminder#email-previews" in body
    assert 'id="email-previews"' in body


def test_invitation_body_renders_with_substituted_session_name(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-email-render")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    )

    body = response.text
    # Default invitation subject is "Invitation to review: $session_name"
    # which substitutes the session's name (capitalized "Prev-Email-Render").
    assert "Invitation to review:" in body
    # `$invite_url` substitutes the preview placeholder, not a real URL.
    assert "preview link" in body.lower()
    # The "To:" header lands the picked reviewer's email.
    assert "<strong>To:</strong> alice@example.edu" in body


def test_unknown_email_param_falls_back_to_invitation(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-email-fallback")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={
            "reviewer_email": "alice@example.edu",
            "email": "nonsense",
        },
    )

    assert response.status_code == 200
    body = response.text
    # Fell through to invitation — Invitation tab is the active button.
    assert (
        '<span class="nav-tab active" aria-current="page">Invitation</span>'
        in body
    )


def test_reminder_tab_renders_card_when_selected(
    client: TestClient, db: Session
) -> None:
    """Segment 11F PR D ships the reminder render adapter, so
    ``?email=reminder`` activates the tab and renders the email body.
    Same shape as the invitation tab; same `$invite_url` placeholder
    in the rendered body."""
    session = _create_session(client, db, code="prev-reminder-active")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={
            "reviewer_email": "alice@example.edu",
            "email": "reminder",
        },
    )

    assert response.status_code == 200
    body = response.text
    # Active tab is reminder (rendered as a disabled "current view"
    # button via the same chrome the invitation tab uses).
    assert (
        '<span class="nav-tab active" aria-current="page">Reminder</span>'
        in body
    )
    # Default subject substitutes the session name.
    assert "Reminder: review for Prev-Reminder-Active" in body
    # `$invite_url` substitutes the preview placeholder, not a real URL.
    assert "preview link" in body.lower()
    # The "To:" header lands the picked reviewer's email.
    assert "<strong>To:</strong> alice@example.edu" in body


def test_responses_received_tab_renders_card_when_selected(
    client: TestClient, db: Session
) -> None:
    """Segment 11E PR 6 ships the responses-received render adapter,
    so ``?email=responses_received`` activates the tab and renders
    the email body. Pre-submit, the body shows the
    "(not yet submitted)" placeholder for ``$submitted_at``."""
    session = _create_session(client, db, code="prev-rr-active")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={
            "reviewer_email": "alice@example.edu",
            "email": "responses_received",
        },
    )

    assert response.status_code == 200
    body = response.text
    # Active tab is responses received (rendered as a disabled "current
    # view" button via the same chrome the invitation tab uses).
    assert (
        '<span class="nav-tab active" aria-current="page">Responses received</span>'
        in body
    )
    # Default subject substitutes the session name.
    assert "Responses received: Prev-Rr-Active" in body
    # Pre-submit placeholder for $submitted_at.
    assert "(not yet submitted)" in body
    # The "To:" header lands the picked reviewer's email.
    assert "<strong>To:</strong> alice@example.edu" in body


def test_email_footer_links_to_setup_pages(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-email-footer")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    )

    body = response.text
    # Setup-page deep link to the matching template tab.
    assert (
        f'href="/operator/sessions/{session.id}/setupinvite?template=invitation"'
        in body
    )
    # Reviewers Setup link.
    assert f'href="/operator/sessions/{session.id}/reviewers"' in body


# PR C iframe surface-card tests (5 of them) + the email/surface
# <hr> ordering test retired in the Segment 18Q follow-on alongside
# the iframe-embedded surface card itself. Reviewer-surface content
# is now exercised by ``test_operator_preview_surface.py`` against
# the dedicated ``/preview-surface/{page_n}`` route; the legacy
# ``/preview`` 308-redirect contract moved to
# ``test_preview_route.py::test_preview_route_returns_308_to_full_preview``.


def _import_reviewees(
    client: TestClient, session_id: int, csv_body: bytes
) -> None:
    response = client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={"file": ("e.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text


def _generate_full_matrix(
    client: TestClient, db: Session, session_id: int
) -> None:
    pin_full_matrix_on_all_instruments(db, session_id)
    response = generate_via_page_button(client, session_id)
    assert response.status_code == 303, response.text


def test_session_home_previews_chrome_link_targets_hub(
    client: TestClient, db: Session
) -> None:
    """The chrome top-nav Previews tab on Session Home points at the
    consolidated previews hub, not the retired /preview route. (Replaces
    the former See previews Next Action card secondary which retired
    with the workflow-stepper redesign.)"""
    session = _create_session(client, db, code="prev-c-home-link")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )
    _import_reviewees(
        client,
        session.id,
        b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
    )
    _generate_full_matrix(client, db, session.id)

    body = client.get(
        f"/operator/sessions/{session.id}/assignments?validated=1"
    ).text

    assert (
        f'href="/operator/sessions/{session.id}/previews">Previews</a>'
        in body
    )
