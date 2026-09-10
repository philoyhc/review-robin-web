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

import pytest
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
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()
    return review_session


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
    # Import the roster first — a roster import reconciles labels from
    # its header (Segment 19C Item 1), so setting the override via the
    # editor path afterwards is what this test pins.
    csv = (
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Cohort",
        user=actor,
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


def test_reviewees_page_renders_canonical_labels_on_identity_slots(
    client: TestClient, db: Session
) -> None:
    """The reviewee identity slots
    (``name`` / ``email_or_identifier`` / ``profile_link``) retired
    the friendly-label affordance 2026-05-31 per upgrade-doc §3.7.
    The page still renders the canonical defaults
    (``Name`` / ``Email`` / ``Profile``); operators can no longer
    override them, so no friendly-label / canonical-subtext pair
    appears for these slots."""
    review_session = _make_session(client, db, "fl-revee-identity")
    csv = (
        "RevieweeName,RevieweeEmail,PhotoLink\n"
        "Carol,carol@example.edu,https://example.org/c.png\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    # Canonical defaults render; the override-subtext span never
    # appears for the identity slots because no override can exist.
    assert ">Name<" in body
    assert ">Email<" in body
    assert ">Profile<" in body
    assert (
        'class="field-label-canonical">Name</span>' not in body
    )
    assert (
        'class="field-label-canonical">Email</span>' not in body
    )
    assert (
        'class="field-label-canonical">Profile</span>' not in body
    )


def test_upsert_rejects_retired_reviewee_identity_slots(
    client: TestClient, db: Session
) -> None:
    """Retired slots — ``name`` / ``email_or_identifier`` /
    ``profile_link`` — raise ``FieldLabelSourceError`` on upsert.
    The defaults still resolve through ``field_labels.resolve``
    (the resolver is permissive on read by design)."""
    review_session = _make_session(client, db, "fl-revee-retired")
    actor = _actor(db)
    for source_field in ("name", "email_or_identifier", "profile_link"):
        with pytest.raises(field_labels.FieldLabelSourceError):
            field_labels.upsert(
                db,
                review_session,
                source_type="reviewee",
                source_field=source_field,
                label="should not persist",
                user=actor,
            )
    # Read path stays permissive — resolver still returns canonical
    # defaults so display surfaces keep working.
    assert (
        field_labels.resolve(review_session, "reviewee", "name")
        == "Name"
    )
    assert (
        field_labels.resolve(
            review_session, "reviewee", "email_or_identifier"
        )
        == "Email"
    )
    assert (
        field_labels.resolve(review_session, "reviewee", "profile_link")
        == "Profile"
    )


# ── Relationships Setup page ─────────────────────────────────────────────


def test_relationships_page_renders_pair_context_friendly_label(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-rel-pc")
    actor = _actor(db)
    # Seed at least one relationship so the table renders. (Need
    # reviewers + reviewees first.) The override is set via the editor
    # path AFTER the imports, since a roster import reconciles labels
    # from its header (Segment 19C Item 1).
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
    field_labels.upsert(
        db,
        review_session,
        source_type="pair_context",
        source_field="1",
        label="Module reference",
        user=actor,
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
    # One override so we can pin both the table header and the
    # toggle-widget label. Set after the imports — a roster import
    # reconciles labels from its header (Segment 19C Item 1).
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_2",
        label="Lab section",
        user=actor,
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


# ── The column chips carry the friendly label ────────────────────────
#
# Segment 19I Item 12 rung 4 retired the "Fields with data" pills.
# Their one contract that outlived them is this: the thing naming a
# tag column outside the table header reads the operator's friendly
# label, not the raw CSV name. That thing is now the ``Show columns:``
# chip, which both reports that the column holds data and toggles it.
#
# The four tests that stood here for Segment 19H Item 5 went with the
# pills. They pinned ``friendly_fields_with_data``'s per-surface map,
# which existed so one CSV column (``RevieweeEmail``) could read
# ``Email`` on one page and ``Reviewee`` on another. Chips never name
# an identity column — only tag and profile slots, which resolve
# through the renamable-slot path — so the map had no caller left and
# retired with the function.


def _chip_label(body: str, slot: str) -> str:
    """The text of one chip."""
    flat = " ".join(body.split())
    i = flat.index(f'data-col-toggle="{slot}"')
    return flat[i : flat.index("</span>", i)].split(">", 1)[1]


def _chip_row(body: str) -> str:
    """Just the ``Show columns:`` row.

    The raw CSV names these tests check for are also listed, quite
    correctly, in the Upload card's header help — ``<code>ReviewerTag1
    </code>`` and friends. The retired pill tests were scoped by their
    own markup; these have to say so.
    """
    flat = " ".join(body.split())
    i = flat.index('class="col-chip-row"')
    return flat[i : flat.index("</p>", i)]


def test_reviewers_chip_uses_the_friendly_override(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-rev-chip")
    actor = _actor(db)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
                b"Alice,alice@example.edu,senior\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Cohort",
        user=actor,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert _chip_label(body, "tag-1") == "Cohort"
    assert "ReviewerTag1" not in _chip_row(body)


def test_reviewees_chips_use_the_builtin_friendly_defaults(
    client: TestClient, db: Session
) -> None:
    """No override set, so each chip falls back to its builtin
    default rather than the CSV column name."""
    review_session = _make_session(client, db, "fl-ree-chip")
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail,PhotoLink,RevieweeTag1\n"
                b"Carol,carol@example.edu,"
                b"https://example.edu/c.jpg,cohort-a\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert _chip_label(body, "profile") == "Profile"
    assert _chip_label(body, "tag-1") == "Tag 1"
    chips = _chip_row(body)
    assert "PhotoLink" not in chips
    assert "RevieweeTag1" not in chips


def test_relationships_chip_uses_the_friendly_override(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fl-rel-chip")
    actor = _actor(db)
    for path, payload in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"),
        (
            "relationships",
            b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
            b"alice@example.edu,carol@example.edu,mentor\n",
        ),
    ):
        client.post(
            f"/operator/sessions/{review_session.id}/{path}/import",
            files={"file": (f"{path}.csv", payload, "text/csv")},
            follow_redirects=False,
        )
    field_labels.upsert(
        db,
        review_session,
        source_type="pair_context",
        source_field="1",
        label="Mentorship",
        user=actor,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert _chip_label(body, "tag-1") == "Mentorship"
    assert "PairContextTag1" not in _chip_row(body)


def test_no_page_renders_a_fields_with_data_card(
    client: TestClient, db: Session
) -> None:
    """The card itself is gone from all three Setup pages."""
    review_session = _make_session(client, db, "fl-no-card")
    for path, payload in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"),
        (
            "relationships",
            b"ReviewerEmail,RevieweeEmail\nalice@example.edu,carol@example.edu\n",
        ),
    ):
        client.post(
            f"/operator/sessions/{review_session.id}/{path}/import",
            files={"file": (f"{path}.csv", payload, "text/csv")},
            follow_redirects=False,
        )
    for page in ("reviewers", "reviewees", "relationships"):
        body = client.get(
            f"/operator/sessions/{review_session.id}/{page}"
        ).text
        assert "Fields with data" not in body, page
