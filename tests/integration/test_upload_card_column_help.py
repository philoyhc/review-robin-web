"""The three roster Upload cards must describe the CSV the parser accepts.

Card copy is the operator's only account of the contract at the moment
they are about to upload — `spec/csv_contracts.md` is not on screen, and
the setup templates are a separate download. So the copy is asserted
against the parsers rather than reviewed by eye.

This exists because the copy had already drifted: `Status` is optional on
every roster file (`_parse_status` runs in `parse_reviewer_csv`,
`parse_reviewee_csv` and the relationships parser alike), but only the
Relationships card said so. An operator reading the Reviewers card had no
way to learn the column existed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import setup_templates

# page slug -> (required columns, optional columns) per spec/csv_contracts.md
# §3.1 / §3.2 and the parsers themselves.
CARDS = {
    "reviewers": (
        ["ReviewerName", "ReviewerEmail"],
        ["ReviewerTag1", "ReviewerTag2", "ReviewerTag3", "Status"],
    ),
    "reviewees": (
        ["RevieweeName", "RevieweeEmail"],
        [
            "PhotoLink",
            "RevieweeTag1",
            "RevieweeTag2",
            "RevieweeTag3",
            "Status",
        ],
    ),
    "relationships": (
        ["ReviewerEmail", "RevieweeEmail"],
        [
            "PairContextTag1",
            "PairContextTag2",
            "PairContextTag3",
            "Status",
        ],
    ),
}

# The friendly-label example each card shows, per spec/csv_contracts.md §1a.
LABEL_EXAMPLES = {
    "reviewers": ("ReviewerTag1", "Tutor"),
    "reviewees": ("RevieweeTag1", "Tutor"),
    "relationships": ("PairContextTag1", "Interest Group"),
}


@pytest.fixture
def session_id(client: TestClient, db: Session) -> int:
    client.post(
        "/operator/sessions",
        data={"name": "Upload Cards", "code": "upload-cards"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "upload-cards")
    ).scalar_one()
    # Relationships is an optional Setup tab; its route 404s unless the
    # session has it switched on, so the card is unreachable without this.
    review_session.relationships_enabled = True
    db.flush()
    return review_session.id


@pytest.mark.parametrize("slug", sorted(CARDS))
def test_upload_card_names_every_column_the_parser_accepts(
    client: TestClient, session_id: int, slug: str
) -> None:
    required, optional = CARDS[slug]
    body = client.get(f"/operator/sessions/{session_id}/{slug}").text

    for column in required + optional:
        assert f"<code>{column}</code>" in body, f"{slug}: {column} not named"


@pytest.mark.parametrize("slug", sorted(LABEL_EXAMPLES))
def test_upload_card_shows_the_friendly_label_header_suffix(
    client: TestClient, session_id: int, slug: str
) -> None:
    """The `<Slot>.<label>` suffix (§1a) is the sole carrier of friendly tag
    labels through a roster CSV, and nothing else on the page mentions it."""
    column, label = LABEL_EXAMPLES[slug]
    body = client.get(f"/operator/sessions/{session_id}/{slug}").text

    assert "keyed into the header after a period" in body
    assert f"<code>{column}.{label}</code>" in body


@pytest.mark.parametrize("slug", sorted(LABEL_EXAMPLES))
def test_the_card_example_matches_the_shipped_template(slug: str) -> None:
    """An operator comparing the card to the template they downloaded should
    see the same label, not two plausible-looking different ones."""
    column, label = LABEL_EXAMPLES[slug]

    assert setup_templates.LABELS[column] == label
