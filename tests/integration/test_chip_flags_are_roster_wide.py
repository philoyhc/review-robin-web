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

# The chip markup. Since rung 3 there is only one state: a slot with
# data renders a live chip, and a slot without renders nothing at
# all — no chip, and no column for it to govern.
LIVE = 'tag-chip is-selected" data-col-toggle="{slot}"'


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
    """``"live"`` or ``"absent"`` for one chip.

    The third state — a struck ``is-disabled`` chip marking a column
    with no data — retired in rung 3. Its absence is asserted rather
    than assumed, because "absent" and "struck" would otherwise be
    indistinguishable to every caller below.
    """
    flat = " ".join(body.split())
    if LIVE.format(slot=slot) in flat:
        return "live"
    assert f'is-disabled" data-col-toggle="{slot}"' not in flat, (
        f"{slot} rendered the retired disabled-chip state"
    )
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
    assert _chip_state(body, "tag-2") == "absent"


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
    assert _chip_state(body, "tag-1") == "absent"


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


def test_a_slot_with_no_data_anywhere_renders_no_chip_and_no_column(
    db: Session, client: TestClient
) -> None:
    """The other half of the contract: roster-wide must not mean
    "always live"."""
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
    assert _chip_state(body, "tag-2") == "absent"
    assert _chip_state(body, "tag-3") == "absent"

    # And the columns go with the chips. Scoped to the table: the
    # page's own <style> block still names every ``.tag-col-N`` in a
    # ``col-hidden-`` rule, so an unscoped assertion matches the CSS.
    _t = body.index("<table id=")
    table = body[_t : body.index("</table>", _t)]
    assert "tag-col-1" in table
    assert "tag-col-2" not in table
    assert "tag-col-3" not in table


def test_a_roster_with_no_tags_at_all_renders_no_chip_row(
    db: Session, client: TestClient
) -> None:
    """``Show columns:`` with nothing after it is a label, not a
    control."""
    review_session = _session(client, db, code="chip-none")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert "Show columns:" not in body
    assert 'data-col-toggles-for="reviewers-table"' not in body
    _t = body.index("<table id=")
    table = body[_t : body.index("</table>", _t)]
    for slot in ("tag-col-1", "tag-col-2", "tag-col-3"):
        assert slot not in table
    # The table itself still renders its remaining columns.
    assert "Alpha" in table


def test_edit_mode_renders_every_tag_column_even_when_empty(
    db: Session, client: TestClient
) -> None:
    """The chicken-and-egg guard, and the one place rung 3's rule
    must not apply.

    A tag with no data renders no column — but an operator adding or
    editing a row has to be able to type into an empty tag, which is
    the only way it ever stops being empty. ``edit_mode`` overrides
    the gate, exactly as the Photo column has always done.
    """
    review_session = _session(client, db, code="chip-editmode")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alpha",
            email="alpha@example.edu",
        )
    )
    db.commit()

    plain = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    adding = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?add=1"
    ).text

    _p = plain.index("<table id=")
    _a = adding.index("<table id=")
    plain_table = plain[_p : plain.index("</table>", _p)]
    add_table = adding[_a : adding.index("</table>", _a)]

    assert "tag-col-1" not in plain_table
    for slot in ("tag-col-1", "tag-col-2", "tag-col-3"):
        assert slot in add_table, slot
    assert 'name="tag_1"' in add_table


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
    assert _chip_state(body, "rt2") == "absent"


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

    assert _chip_state(assignments_body, "p1") == "absent"
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


def test_an_assignments_group_with_no_data_renders_no_row(
    db: Session, client: TestClient
) -> None:
    """Assignments is the only page with several chip rows, so it is
    the only one that can render a group label with no chips after
    it. Reviewer tags are populated here; reviewee tags and
    pair-context are empty, so those two rows go entirely.

    A mutation removing this gate survived the first pass — nothing
    else in the suite looks at the group labels.
    """
    review_session = _session(client, db, code="chip-group-empty")
    for i in range(2):
        db.add(
            Reviewer(
                session_id=review_session.id,
                name=f"R{i}",
                email=f"r{i}@example.edu",
                tag_1="Team A",
            )
        )
        db.add(
            Reviewee(
                session_id=review_session.id,
                name=f"E{i}",
                email_or_identifier=f"e{i}@example.edu",
            )
        )
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Show reviewers:" in body
    assert "Show reviewees:" not in body
    assert "Show relationships:" not in body
    assert _chip_state(body, "rt1") == "live"
    assert _chip_state(body, "et1") == "absent"
