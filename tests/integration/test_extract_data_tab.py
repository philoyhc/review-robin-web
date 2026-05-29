"""Skeleton for the new Extract data Operations-strip tab
(per ``guide/extract_data.md``). Verifies the route renders
200, surfaces the page heading, the three placeholder lens
sections, and that the tab appears in the operations strip on
its own page + on a sibling Operations page (Responses).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "extract-tab"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "ExtractTab", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_extract_data_tab_renders_skeleton(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-tab-basic")
    response = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    )
    assert response.status_code == 200, response.text
    body = response.text

    # Page heading.
    assert ">Extract all data</h2>" in body
    # Three lens placeholder sections present.
    assert 'id="extract-data-by-instrument"' in body
    assert 'id="extract-data-by-reviewer"' in body
    assert 'id="extract-data-by-reviewee"' in body
    # Lens headings — every lens card uses h2 to match the
    # Extract data intro card's text styling (Wave 2 PR — chip
    # row layout shipped).
    assert ">By instrument</h2>" in body
    assert ">Reviewer response metadata</h2>" in body
    assert ">Reviewee response metadata</h2>" in body


def test_extract_data_tab_appears_in_operations_strip(
    client: TestClient, db: Session
) -> None:
    """The Extract data tab is the last Operations tab (after
    Responses). Both the new page and the sibling Responses page
    should render the tab in their nav strip."""

    review_session = _make_session(client, db, code="ed-tab-nav")

    # On the new Extract data page itself, the tab is active.
    own = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    )
    assert own.status_code == 200
    assert "Extract data</a>" in own.text
    assert (
        f'href="/operator/sessions/{review_session.id}/extract-data"'
        in own.text
    )
    # The active class lands on the matching tab.
    assert 'class="nav-tab active"' in own.text

    # On a sibling Operations page (Responses), the tab also
    # appears (inactive).
    sibling = client.get(
        f"/operator/sessions/{review_session.id}/responses"
    )
    assert sibling.status_code == 200
    assert (
        f'href="/operator/sessions/{review_session.id}/extract-data"'
        in sibling.text
    )


def test_extract_data_tab_breadcrumbs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-tab-crumbs")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # operator_session_child renders "Sessions › <name> › Extract data".
    assert "Extract data" in body


def test_data_shaper_placeholder_card_renders(
    client: TestClient, db: Session
) -> None:
    """The Data shaper placeholder lives below the 2-column
    grid as a full-width card; the intro card's chip row
    carries a matching ``Data shaper`` selector defaulting to
    selected so the shaper output can be folded into the
    top-level ``Zip all`` once the engine ships."""
    review_session = _make_session(client, db, code="ed-shaper")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Intro card chip.
    assert 'data-extract-all-chip="data-shaper"' in body
    # Placeholder card shell + bottom ``Zip all`` button stays
    # disabled in this slice (no file-gen wiring yet).
    assert 'id="extract-data-shaper"' in body
    assert ">Data shaper</h2>" in body
    assert 'id="extract-data-shaper-zip"' in body


def test_data_shaper_axis_chip_row_and_pools(
    client: TestClient, db: Session
) -> None:
    """The axis chip row at the top of the outer Data shaper
    card carries the two **mutually exclusive** axis chips
    (Reviewer / Reviewee), all default-unselected. Each axis
    has a hidden ``<template data-shaper-chip-pool>`` carrying
    its relevant column chips for the progressive-enhancement
    JS to clone when the axis toggles on. Instrument is no
    longer an axis — it became a per-axis-pool scope filter
    rendered to the right of the intra-pool pipe."""
    review_session = _make_session(client, db, code="ed-shaper-axes")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    for axis, label in [
        ("reviewer", "Reviewer"),
        ("reviewee", "Reviewee"),
    ]:
        # Axis chip itself.
        assert f'data-shaper-axis-chip="{axis}"' in body
        assert f'>{label}</span>' in body
        # Hidden pool template for the axis's column chips.
        assert f'data-shaper-chip-pool="{axis}"' in body

    # Instrument axis chip retired — it lives as a per-axis
    # scope chip inside the Reviewer / Reviewee pools now.
    assert 'data-shaper-axis-chip="instrument"' not in body
    assert 'data-shaper-chip-pool="instrument"' not in body

    # Reviewer pool carries the identity chips + the six
    # aggregate chips that mirror the Reviewer response
    # metadata card's column shape.
    for slot in (
        "reviewer:name",
        "reviewer:email",
        "reviewer:tag-1",
        "reviewer:tag-2",
        "reviewer:tag-3",
        "reviewer:count",
        "reviewer:mean",
        "reviewer:median",
        "reviewer:min",
        "reviewer:max",
        "reviewer:length",
    ):
        assert f'data-shaper-col-chip="{slot}"' in body


def test_data_shaper_axis_pool_has_intra_pool_pipe_and_instrument_chips(
    client: TestClient, db: Session
) -> None:
    """Each axis chip pool carries three sub-groups separated
    by a ``|`` pipe: identification chips, then per-instrument
    scope chips (one per session instrument, labelled like the
    By-instrument card), then the aggregate data chips.

    With no instrument scope chip selected the aggregates
    span every session instrument — matching the "By
    reviewer" / "By reviewee" general-data framing."""
    review_session = _make_session(client, db, code="ed-shaper-pool")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Slice the Reviewer chip pool's body.
    reviewer_pool = body.split('data-shaper-chip-pool="reviewer"')[1].split(
        "</template>"
    )[0]
    # ID chip ➝ pipe ➝ instrument chip ➝ aggregate chip in
    # that order. ``str.index`` will raise if any is absent.
    name_at = reviewer_pool.index('data-shaper-col-chip="reviewer:name"')
    pipe_at = reviewer_pool.index('shaper-axis-pipe')
    instrument_at = reviewer_pool.index(
        'data-shaper-col-chip="reviewer:instrument-'
    )
    count_at = reviewer_pool.index('data-shaper-col-chip="reviewer:count"')
    assert name_at < pipe_at < instrument_at < count_at

    # Reviewee pool follows the same shape.
    reviewee_pool = body.split('data-shaper-chip-pool="reviewee"')[1].split(
        "</template>"
    )[0]
    assert 'data-shaper-col-chip="reviewee:name"' in reviewee_pool
    assert 'shaper-axis-pipe' in reviewee_pool
    assert 'data-shaper-col-chip="reviewee:instrument-' in reviewee_pool
    assert 'data-shaper-col-chip="reviewee:count"' in reviewee_pool


def test_data_shaper_initial_blank_shape_card(
    client: TestClient, db: Session
) -> None:
    """One always-present blank Data shape sub-card renders on
    initial load so the operator has an immediate edit target
    (matches the band-3 response-field builder's
    always-present-empty-row pattern). The card carries the
    preview row stub + the four action icons (save / edit /
    delete / add)."""
    review_session = _make_session(client, db, code="ed-shaper-blank")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert "data-shaper-stack" in body
    # One non-template ``data-shape`` div sits in the stack on
    # first render. (The ``<template>`` clones don't render
    # in the DOM until the JS spawns them.)
    stack_block = body.split("data-shaper-stack")[1].split(
        "extract-data-card-actions"
    )[0]
    assert 'data-shape-mode="edit"' in stack_block
    assert "data-shape-preview-row" in stack_block
    assert "data-shape-name" in stack_block
    for action in ("save", "edit", "delete", "add"):
        assert f"data-shape-{action}" in stack_block


def test_extract_all_card_renders_lens_selector_chips(
    client: TestClient, db: Session
) -> None:
    """The intro card (``Extract all data``) carries three
    placeholder selector chips — ``By instruments``,
    ``Reviewer response metadata``, ``Reviewee response
    metadata`` — all defaulting to selected. Wiring lands
    later; this slice is layout."""
    review_session = _make_session(client, db, code="ed-all-chips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert 'data-extract-all-chip="by-instruments"' in body
    assert ">By instruments<" in body
    assert 'data-extract-all-chip="reviewer-metadata"' in body
    assert ">Reviewer response metadata<" in body
    assert 'data-extract-all-chip="reviewee-metadata"' in body
    assert ">Reviewee response metadata<" in body
    assert 'data-extract-all-chip="data-shaper"' in body
    assert ">Data shaper<" in body

    # All three chips start selected.
    chip_block = body.split('id="extract-data-intro"')[1].split(
        "extract-data-card-actions"
    )[0]
    assert chip_block.count("is-selected") == 4
    assert chip_block.count('aria-pressed="true"') == 4


def test_reviewer_metadata_card_renders_selectable_chips(
    client: TestClient, db: Session
) -> None:
    """The Reviewer response metadata card carries one chip per
    instrument (by short label or ``Instrument_{n}`` fallback)
    inline before the ``All reviewers`` toggle. All chips
    default to selected; the per-statistic chips moved into the
    extract column shape (numeric fields ship
    ``.Mean/.Median/.Min/.Max``, string fields ship ``.Length``)."""
    review_session = _make_session(client, db, code="ed-revwr-meta-chips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    chip_block = body.split('id="extract-data-by-reviewer"')[1].split(
        "extract-data-card-actions"
    )[0]
    # Default-seeded session has one instrument; its chip plus
    # the ``All reviewers`` toggle = 2 chips.
    assert 'data-reviewer-metadata-chip="instrument-' in chip_block
    assert 'data-reviewer-metadata-chip="all-reviewers"' in chip_block
    assert ">All reviewers<" in chip_block
    # The old per-statistic chips (Count / Mean / etc.) retired —
    # the only labels left are the instrument chips + the toggle.
    assert chip_block.count("is-selected") == 2
    assert chip_block.count('aria-pressed="true"') == 2


def test_reviewee_metadata_card_renders_selectable_chips(
    client: TestClient, db: Session
) -> None:
    """Mirror of the Reviewer metadata chips on the Reviewee
    card — one chip per instrument followed by ``All
    reviewees``."""
    review_session = _make_session(client, db, code="ed-revwe-meta-chips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    chip_block = body.split('id="extract-data-by-reviewee"')[1].split(
        "extract-data-card-actions"
    )[0]
    assert 'data-reviewee-metadata-chip="instrument-' in chip_block
    assert 'data-reviewee-metadata-chip="all-reviewees"' in chip_block
    assert ">All reviewees<" in chip_block
    assert chip_block.count("is-selected") == 2
    assert chip_block.count('aria-pressed="true"') == 2


def test_by_instrument_card_renders_selectable_chips(
    client: TestClient, db: Session
) -> None:
    """The By instrument card carries one chip per instrument
    (by short label or ``Instrument_{n}`` fallback) plus the two
    cross-cutting toggles. All default to selected
    (``is-selected`` + ``aria-pressed="true"``)."""
    review_session = _make_session(client, db, code="ed-chips")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Default-seeded session has one instrument with no short
    # label — the chip carries the bare ``#1`` positional prefix
    # (matches the Reviewer-surface heading helper's no-label
    # branch).
    assert "data-by-instrument-chip=\"instrument-" in body
    assert ">#1<" in body
    # Cross-cutting toggles.
    assert "data-by-instrument-chip=\"include-metadata\"" in body
    assert ">Include metadata<" in body
    assert "data-by-instrument-chip=\"all-assignment-rows\"" in body
    assert ">All assignment rows<" in body
    # All chips start selected — the toggle JS flips this later.
    chip_block = body.split("extract-data-by-instrument")[1].split(
        "extract-data-card-actions"
    )[0]
    assert chip_block.count("is-selected") >= 3
    assert chip_block.count('aria-pressed="true"') >= 3
