"""The column chips answer over the roster, not over the rows on
screen — Segment 19I Item 12 rung 2.

Before this rung every one of the six chip surfaces computed its
has-data flags in Jinja, by scanning whatever row list the route
had handed it. Each list was narrower than the roster, in one of
two ways, so each page could strike out a chip for a column that
holds data:

- the three Setup rosters scanned the **filtered and capped**
  display list (200 rows, 500 when filtered);
- Invitations and Responses scanned the **filtered** set;
- Assignments used a deliberately *unfiltered* sample that still
  carried ``list_pairs``' default ``limit=PAIR_PREVIEW_LIMIT``, so
  it was capped at 200.

Both failure modes are pinned here, because rung 3 turns a struck
chip into **no column at all** — at which point the same bug stops
being cosmetic and starts hiding imported data.

The seeds put the tagged row where the old code could not see it:
past the cap, or behind the filter. A test that tagged row 1 would
pass against the code this rung replaces.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)

# The chip markup, per state. ``is-disabled`` is what "no data in
# this column" renders as until rung 3 retires it.
LIVE = 'tag-chip is-selected" data-col-toggle="{slot}"'
DEAD = 'tag-chip is-disabled" data-col-toggle="{slot}"'


def _session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    relationships: bool = False,
) -> ReviewSession:
    data = {"name": "Chip flags", "code": code}
    if relationships:
        # The Relationships Setup page 404s until the session opts in.
        data["relationships_enabled"] = "on"
    response = client.post(
        "/operator/sessions",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _rows(body: str) -> str:
    """Just the rendered table rows.

    The vacuity guards below ask "did the row I tagged stay out of
    the table?", and the whole page is the wrong place to ask: the
    search box's ``<datalist>`` lists every roster member by name
    and handle, so an unscoped ``"Bravo" not in body`` fails on a
    typeahead option and the guard reports a vacuous seed that is
    not vacuous. Found by running it — the same unscoped-substring
    trap this segment has now hit four times.
    """
    start = body.index('<tbody class="rrw-rows">')
    return body[start : body.index("</tbody>", start)]


def _chip_state(body: str, slot: str) -> str:
    """``"live"`` / ``"dead"`` / ``"absent"`` for one chip."""
    flat = " ".join(body.split())
    if LIVE.format(slot=slot) in flat:
        return "live"
    if DEAD.format(slot=slot) in flat:
        return "dead"
    return "absent"


# --------------------------------------------------------------------------- #
# Past the cap.
# --------------------------------------------------------------------------- #


def test_a_tag_past_the_reviewers_cap_still_lights_its_chip(
    db: Session, client: TestClient
) -> None:
    """250 reviewers, and only the last one carries ``tag_1``. The
    page renders 200, so the row holding the data is not among
    them."""
    review_session = _session(client, db, code="chip-cap-rev")
    for i in range(250):
        db.add(
            Reviewer(
                session_id=review_session.id,
                name=f"R{i:04d}",
                email=f"r{i:04d}@example.edu",
                tag_1="Team A" if i == 249 else None,
            )
        )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert "R0249" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "tag-1") == "live"
    assert _chip_state(body, "tag-2") == "dead"


def test_a_tag_past_the_reviewees_cap_still_lights_its_chip(
    db: Session, client: TestClient
) -> None:
    review_session = _session(client, db, code="chip-cap-ree")
    for i in range(250):
        db.add(
            Reviewee(
                session_id=review_session.id,
                name=f"E{i:04d}",
                email_or_identifier=f"e{i:04d}@example.edu",
                tag_2="Unit 9" if i == 249 else None,
            )
        )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert "E0249" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "tag-2") == "live"
    assert _chip_state(body, "tag-1") == "dead"


def test_a_photo_past_the_cap_still_lights_the_profile_chip(
    db: Session, client: TestClient
) -> None:
    """The one non-tag slot on any of the six pages."""
    review_session = _session(client, db, code="chip-cap-photo")
    for i in range(250):
        db.add(
            Reviewee(
                session_id=review_session.id,
                name=f"E{i:04d}",
                email_or_identifier=f"e{i:04d}@example.edu",
                profile_link="https://example.edu/p.png" if i == 249 else None,
            )
        )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert "E0249" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "profile") == "live"


# --------------------------------------------------------------------------- #
# Behind a filter.
# --------------------------------------------------------------------------- #


def test_a_filter_that_excludes_the_tagged_row_keeps_its_chip_live(
    db: Session, client: TestClient
) -> None:
    """Two reviewers; only Bravo carries ``tag_1``; the search
    matches only Alpha. Bravo's tag is still in the roster."""
    review_session = _session(client, db, code="chip-filter-rev")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
        )
    )
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bravo",
            email="bravo@example.edu",
            tag_1="Team A",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?q=Alpha"
    ).text
    assert "Bravo" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "tag-1") == "live"


def test_the_invitations_chip_reads_the_roster_not_the_filtered_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _session(client, db, code="chip-filter-inv")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
        )
    )
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bravo",
            email="bravo@example.edu",
            tag_3="Cohort 7",
        )
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Echo",
            email_or_identifier="echo@example.edu",
        )
    )
    db.commit()
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/invitations?q=Alpha"
    ).text
    assert "bravo@example.edu" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "tag-3") == "live"


def test_the_responses_chip_reads_the_roster_not_the_filtered_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _session(client, db, code="chip-filter-resp")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
        )
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Echo",
            email_or_identifier="echo@example.edu",
        )
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Foxtrot",
            email_or_identifier="foxtrot@example.edu",
            tag_2="Unit 3",
        )
    )
    db.commit()
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/responses?q=Echo"
    ).text
    assert "foxtrot@example.edu" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "tag-2") == "live"


# --------------------------------------------------------------------------- #
# The empty case still reads empty.
# --------------------------------------------------------------------------- #


def test_a_slot_with_no_data_anywhere_still_strikes_its_chip(
    db: Session, client: TestClient
) -> None:
    """The other half of the contract: roster-wide must not mean
    "always live". Rung 3 turns this state into no chip at all."""
    review_session = _session(client, db, code="chip-empty")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
            tag_1="Team A",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert _chip_state(body, "tag-1") == "live"
    assert _chip_state(body, "tag-2") == "dead"
    assert _chip_state(body, "tag-3") == "dead"


# --------------------------------------------------------------------------- #
# Assignments — the page that already tried, and was still capped.
# --------------------------------------------------------------------------- #


def test_a_tag_past_the_assignments_pair_cap_still_lights_its_chip(
    db: Session, client: TestClient
) -> None:
    """Assignments is the near-miss: its flags already read a
    deliberately **unfiltered** sample (Item 9's comment says so),
    but ``list_pairs`` defaults to ``limit=PAIR_PREVIEW_LIMIT``, so
    the sample stopped at 200 rows.

    16 x 16 = 256 pairs, ordered by ``(reviewer_id, reviewee_id)``.
    Only the last-created reviewer carries ``tag_1``, so every pair
    that could reveal it sits past row 240.
    """
    review_session = _session(client, db, code="chip-cap-asg")
    for i in range(16):
        db.add(
            Reviewer(
                session_id=review_session.id,
                name=f"R{i:02d}",
                email=f"r{i:02d}@example.edu",
                tag_1="Team Z" if i == 15 else None,
            )
        )
        db.add(
            Reviewee(
                session_id=review_session.id,
                name=f"E{i:02d}",
                email_or_identifier=f"e{i:02d}@example.edu",
            )
        )
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "r15@example.edu" not in _rows(body), (
        "seed is vacuous — the tagged reviewer's pairs rendered, so the "
        "capped sample could have seen the tag"
    )
    assert _chip_state(body, "rt1") == "live"
    assert _chip_state(body, "rt2") == "dead"


def test_assignments_pair_context_chips_stay_active_only(
    db: Session, client: TestClient
) -> None:
    """``active_only`` is preserved, not rationalized: the pair-context
    group counts only ``active`` relationships, matching the rule
    engine, while the Relationships Setup page counts every row. An
    inactive relationship's tag lights the chip on one page and not
    the other."""
    review_session = _session(
        client, db, code="chip-active-only", relationships=True
    )
    reviewer = Reviewer(
        session_id=review_session.id,
        name="Alpha",
        email="alpha@example.edu",
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Echo",
        email_or_identifier="echo@example.edu",
    )
    db.add(reviewer)
    db.add(reviewee)
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            tag_1="Ctx 1",
            status="inactive",
        )
    )
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    assignments_body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    relationships_body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text

    assert _chip_state(assignments_body, "p1") == "dead"
    assert _chip_state(relationships_body, "tag-1") == "live"


def test_the_photo_chip_and_the_photo_column_agree(
    db: Session, client: TestClient
) -> None:
    """A chip that governs a column that is not rendered is a control
    wired to nothing.

    Making the chip roster-wide created exactly that risk: the column
    was gated on a scan of the *displayed* rows, so a photo living
    only past the cap lit the chip and left the column out. Both read
    ``col_data["profile"]`` now, and this pins them together.
    """
    review_session = _session(client, db, code="chip-photo-column")
    for i in range(250):
        db.add(
            Reviewee(
                session_id=review_session.id,
                name=f"E{i:04d}",
                email_or_identifier=f"e{i:04d}@example.edu",
                profile_link="https://example.edu/p.png" if i == 249 else None,
            )
        )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert "E0249" not in _rows(body), "seed is vacuous"
    assert _chip_state(body, "profile") == "live"
    assert 'class="profile-col"' in body, (
        "the chip is live but the column it governs was not rendered"
    )
