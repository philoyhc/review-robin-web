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
