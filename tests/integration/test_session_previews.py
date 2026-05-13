"""Integration tests for the Operations-row Previews page (segment 11F PR A).

Covers the reviewer picker (typeahead + datalist + Apply + Prev/Next +
Random) and the page's empty-state behaviors. Artifact cards land in
PRs B-E and have their own test files.
"""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _extract_iframe_srcdoc(body: str) -> str:
    """Pull the `srcdoc` attribute off the surface preview iframe and
    HTML-unescape it so tests can assert against the rendered reviewer-
    surface body.

    Auto-escaping inside Jinja2 attributes encodes `<` `>` `"` `&`
    `'`, so a raw substring assertion against the outer body would
    miss most of the rendered HTML. Decoding once gives the same
    bytes the browser would see when parsing the iframe document.
    """
    match = re.search(
        r'<iframe[^>]*\bclass="surface-preview-iframe"[^>]*\bsrcdoc="([^"]*)"',
        body,
    )
    assert match is not None, "surface preview iframe not found"
    return html.unescape(match.group(1))


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


def test_hr_separator_sits_between_email_region_and_surface_card(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-email-hr")
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
    # The email card precedes the <hr> precedes the reviewer-surface
    # card. Pin the relative DOM order so PRs D / E can rely on the
    # contract.
    email_idx = body.index('<div class="card email-preview-card" id="email-previews">')
    hr_idx = body.index('<hr class="preview-region-divider">')
    surface_idx = body.index('id="reviewer-surface"')
    assert email_idx < hr_idx < surface_idx


# ── PR C: reviewer-surface card ─────────────────────────────────────


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


def _seed_session_with_assignments(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    session = _create_session(client, db, code=code)
    _import_reviewers(
        client,
        session.id,
        (
            b"ReviewerName,ReviewerEmail\n"
            b"Alice,alice@example.edu\n"
            b"Bob,bob@example.edu\n"
        ),
    )
    _import_reviewees(
        client,
        session.id,
        (
            b"RevieweeName,RevieweeEmail\n"
            b"Carol,carol@example.edu\n"
            b"Dan,dan@example.edu\n"
        ),
    )
    _generate_full_matrix(client, db, session.id)
    return session


def test_surface_card_renders_iframe_with_session_name(
    client: TestClient, db: Session
) -> None:
    session = _seed_session_with_assignments(client, db, code="prev-c-iframe")

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    )

    assert response.status_code == 200
    body = response.text
    assert 'class="surface-preview-iframe"' in body
    # `allow-scripts` (without `allow-same-origin`) keeps the
    # reviewer-surface page-toggle JS alive so multi-instrument
    # Page #N controls work inside the iframe; the opaque origin
    # blocks parent-cookie / localStorage access.
    assert 'sandbox="allow-scripts"' in body
    inner = _extract_iframe_srcdoc(body)
    # The iframe's HTML contains the reviewer-surface page header H1.
    assert f"<h1>{session.name}</h1>" in inner


def test_surface_card_iframe_is_filtered_to_picker_reviewer(
    client: TestClient, db: Session
) -> None:
    """When the picker selects Alice, the iframe surfaces Alice's
    assignments (Carol, Dan), not Bob's. Switching the picker to Bob
    shows Bob's assignments — same reviewees in this seed but the
    threading runs through `target_reviewer`."""
    session = _seed_session_with_assignments(client, db, code="prev-c-filter")

    alice_body = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    ).text
    alice_inner = _extract_iframe_srcdoc(alice_body)
    assert "Carol" in alice_inner
    assert "Dan" in alice_inner
    # Sample-Reviewee synthetic rows only render when a reviewer has
    # fewer than three real assignments. Alice has two (Carol + Dan)
    # so one synthetic row pads.
    assert "Sample Reviewee" in alice_inner

    bob_body = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "bob@example.edu"},
    ).text
    bob_inner = _extract_iframe_srcdoc(bob_body)
    assert "Carol" in bob_inner
    assert "Dan" in bob_inner


def test_surface_card_renders_missing_assignments_stub(
    client: TestClient, db: Session
) -> None:
    """A reviewer with no assignments gets the scoped missing-data stub
    (with a Setup-page link), and the email region above the <hr>
    keeps rendering."""
    session = _create_session(client, db, code="prev-c-no-assign")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )

    body = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    ).text

    assert "This reviewer has no reviewees assigned" in body
    assert (
        f'href="/operator/sessions/{session.id}/assignments"' in body
    )
    # Email region above the <hr> still renders.
    assert 'class="card email-preview-card"' in body
    assert 'class="surface-preview-iframe"' not in body


def test_surface_card_renders_missing_instruments_stub(
    client: TestClient, db: Session
) -> None:
    """When a session has no instruments, the surface card surfaces
    the Instruments-Setup link rather than rendering a blank iframe."""
    # Bypass the seed defaults that create instruments by going through
    # SQL directly.
    from app.db.models import Instrument

    session = _create_session(client, db, code="prev-c-no-instr")
    _import_reviewers(
        client,
        session.id,
        b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )
    # Tear down auto-seeded instruments so the missing-instruments
    # branch fires.
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().all()
    for ins in instruments:
        db.delete(ins)
    db.flush()

    body = client.get(
        f"/operator/sessions/{session.id}/previews",
        params={"reviewer_email": "alice@example.edu"},
    ).text

    assert "No instruments configured" in body
    assert f'href="/operator/sessions/{session.id}/instruments"' in body
    assert 'class="surface-preview-iframe"' not in body


def test_preview_singular_route_redirects_308_to_hub(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="prev-c-redir")

    response = client.get(
        f"/operator/sessions/{session.id}/preview", follow_redirects=False
    )

    assert response.status_code == 308
    assert response.headers["location"] == (
        f"/operator/sessions/{session.id}/previews#reviewer-surface"
    )


def test_session_home_see_previews_link_targets_hub(
    client: TestClient, db: Session
) -> None:
    """Session Home's See previews secondary button points at the
    consolidated previews hub anchored on the surface card, not the
    retired /preview route."""
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
        f"/operator/sessions/{session.id}?validated=1"
    ).text

    assert (
        f'href="/operator/sessions/{session.id}/previews#reviewer-surface"'
        in body
    )
    assert ">See previews</a>" in body
