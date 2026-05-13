"""Operator-surface friendly-label rendering tests — 15A Slice 2.

Pins the two-line `Friendly / canonical` header render on the
Reviewers / Reviewees / Relationships / Assignments pages
whenever a session-wide override is set, plus the single-line
canonical render when no override is in effect.

Also pins the reviewer-surface friendly-only render and the
column-visibility toggle widget on the Assignments page picking
up the friendly label.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import field_labels

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _actor(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


# ── Reviewers Setup page ─────────────────────────────────────────────────


def test_reviewers_page_renders_canonical_default_when_no_override(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-rev-default")
    # Seed at least one reviewer so the table renders.
    csv = (
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Single-line canonical render — no .field-label-canonical
    # span. (The CSS class name appears in the inline <style> block
    # in base.html; match on the span tag itself to dodge that.)
    assert "Tag 1" in body
    assert 'class="field-label-canonical"' not in body


def test_reviewers_page_renders_two_line_when_override_set(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-rev-override")
    actor = _actor(db)
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Cohort",
        user=actor,
    )
    csv = (
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Friendly label appears in primary header text; canonical
    # name appears inside the .field-label-canonical subtext.
    assert "Cohort" in body
    assert 'class="field-label-canonical">Tag 1</span>' in body
    # Canonical subtext lives AFTER the sort button — keeps the
    # button inline with the friendly label on the first row
    # rather than getting pushed below by a block-level span.
    btn_idx = body.index('aria-label="Sort by Tag1"')
    canonical_idx = body.index(
        'class="field-label-canonical">Tag 1</span>'
    )
    assert canonical_idx > btn_idx


# ── Reviewees Setup page ─────────────────────────────────────────────────


def test_reviewees_page_renders_friendly_label_on_identity_slots(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-revee-identity")
    actor = _actor(db)
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="name",
        label="Student name",
        user=actor,
    )
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="email_or_identifier",
        label="Student ID",
        user=actor,
    )
    csv = (
        "RevieweeName,RevieweeEmail\n"
        "Carol,carol@example.edu\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert "Student name" in body
    assert 'class="field-label-canonical">Name</span>' in body
    assert "Student ID" in body
    assert 'class="field-label-canonical">Email</span>' in body


# ── Relationships Setup page ─────────────────────────────────────────────


def test_relationships_page_renders_pair_context_friendly_label(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-rel-pc")
    actor = _actor(db)
    field_labels.upsert(
        db,
        review_session,
        source_type="pair_context",
        source_field="1",
        label="Module reference",
        user=actor,
    )
    # Seed at least one relationship so the table renders. (Need
    # reviewers + reviewees first.)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
                b"alice@example.edu,carol@example.edu,bench-a\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert "Module reference" in body
    assert 'class="field-label-canonical">Pair context 1</span>' in body


# ── Assignments page (table + column-toggle widget) ─────────────────────


def test_assignments_page_picks_up_friendly_label_in_table_and_toggle(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-assign")
    actor = _actor(db)
    # One override on each side so we can pin both the table
    # header and the toggle-widget label.
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_2",
        label="Lab section",
        user=actor,
    )

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
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
                b"RevieweeName,RevieweeEmail,RevieweeTag2\n"
                b"Carol,carol@example.edu,cohort-a\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Generate Full Matrix assignments so the table renders.
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # Two-line render in the table header.
    assert "Lab section" in body
    assert 'class="field-label-canonical">Tag 2</span>' in body
    # Toggle-widget chip for reviewee Tag 2 now reads the friendly
    # label instead of literal ``Tag2``.
    assert "Lab section" in body
