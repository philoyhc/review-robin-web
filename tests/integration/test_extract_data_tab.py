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

from app.db.models import Instrument, ReviewSession


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

    # Reviewer pool carries the identity chips + the seven
    # aggregate chips (Assigned / Count / Mean / Median / Min
    # / Max / Length) that mirror the Reviewer response
    # metadata card's column shape.
    for slot in (
        "reviewer:name",
        "reviewer:email",
        "reviewer:tag-1",
        "reviewer:tag-2",
        "reviewer:tag-3",
        "reviewer:assigned",
        "reviewer:count",
        "reviewer:mean",
        "reviewer:median",
        "reviewer:min",
        "reviewer:max",
        "reviewer:length",
    ):
        assert f'data-shaper-col-chip="{slot}"' in body


def test_data_shaper_numeric_field_carries_discrete_steps_attribute(
    client: TestClient, db: Session
) -> None:
    """Numeric (Integer / Decimal) response fields with a
    finite, small (≤12) number of discrete valid values gain
    a ``data-shaper-field-discrete-steps`` attribute carrying
    the comma-separated step values. The progressive-
    enhancement JS surfaces a ``Discrete steps`` chip in the
    per-axis pool when such a field is selected; clicking it
    emits one preview-row column per step value."""
    from app.db.models import InstrumentResponseField

    review_session = _make_session(client, db, code="ed-shaper-discrete")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    # Integer field 1..5 — five discrete entries.
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="discrete5",
        label="Score 1-5",
        order=88,
        _inline_data_type="Integer",
        _inline_response_type="100int",
        _inline_min=1.0,
        _inline_max=5.0,
        _inline_step=1.0,
    )
    db.add(field)
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    assert 'data-shaper-field-discrete-steps="1,2,3,4,5"' in body
    # The per-axis ``Discrete steps`` chip + its leading pipe
    # render gated behind ``data-shaper-relevant-for="discrete-steps"``
    # so the JS can hide them when the active field doesn't
    # qualify.
    assert 'data-shaper-col-chip="reviewer:discrete-steps"' in body
    assert 'data-shaper-col-chip="reviewee:discrete-steps"' in body


def test_data_shaper_oversized_numeric_field_skips_discrete_steps(
    client: TestClient, db: Session
) -> None:
    """Numeric fields with > 12 discrete entries don't qualify
    for the ``Discrete steps`` chip — the attribute is omitted
    so the JS keeps the chip hidden when the field is selected."""
    from app.db.models import InstrumentResponseField

    review_session = _make_session(
        client, db, code="ed-shaper-discrete-skip"
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    # 0..100 step 1 ⇒ 101 entries, far past the 12 threshold.
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="hundredish",
        label="0-100",
        order=89,
        _inline_data_type="Integer",
        _inline_response_type="100int",
        _inline_min=0.0,
        _inline_max=100.0,
        _inline_step=1.0,
    )
    db.add(field)
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    # Slice the body around the oversized field's chip to
    # confirm its tag doesn't carry the attribute (the
    # default-seeded session may include other in-range
    # fields whose chips do carry it).
    label = ">0-100<"
    end_idx = body.index(label)
    # Walk back to the start of this chip's ``<span``.
    chip_start = body.rfind("<span", 0, end_idx)
    chip_html = body[chip_start:end_idx]
    assert "data-shaper-field-discrete-steps" not in chip_html


def test_data_shaper_list_field_carries_options_attribute(
    client: TestClient, db: Session
) -> None:
    """List-type response fields render an extra
    ``data-shaper-field-list-options`` attribute on their chip
    carrying the CSV of options. The progressive-enhancement
    JS swaps the standard Mean / Median / etc. chips for one
    chip per list option (each contributing a
    count-of-responses column for that option) when the
    operator picks a List field; the attribute is the
    server-rendered hook the JS reads."""
    from app.db.models import InstrumentResponseField

    review_session = _make_session(client, db, code="ed-shaper-list")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    # Seed a List-type response field with a few options.
    list_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="vote",
        label="Vote",
        order=99,
        _inline_data_type="List",
        _inline_response_type="Choice",
        _inline_list_csv="Strong yes,Yes,Maybe,No",
    )
    db.add(list_field)
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    assert (
        'data-shaper-field-list-options="Strong yes,Yes,Maybe,No"' in body
    )


def test_data_shaper_aggregate_chips_carry_data_type_attribute(
    client: TestClient, db: Session
) -> None:
    """``Mean`` / ``Median`` / ``Min`` / ``Max`` chips carry
    ``data-shaper-relevant-for="numeric"`` so the JS hides
    them when a string field is selected; ``Length`` carries
    ``"string"`` (hidden for numeric fields). ``Assigned``
    and ``Count`` carry no such attribute — they apply to
    every data type and stay visible always.

    Field chips carry their ``_inline_data_type`` via
    ``data-shaper-field-data-type`` so the JS knows which
    bucket to apply on toggle."""
    review_session = _make_session(client, db, code="ed-shaper-dtype")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Numeric aggregates carry the ``numeric`` marker.
    for slot in ("reviewer:mean", "reviewer:median", "reviewer:min", "reviewer:max"):
        chip_block = body.split(f'data-shaper-col-chip="{slot}"')[1].split(">")[0]
        assert 'data-shaper-relevant-for="numeric"' in chip_block

    # String aggregate carries the ``string`` marker.
    length_block = body.split('data-shaper-col-chip="reviewer:length"')[1].split(">")[0]
    assert 'data-shaper-relevant-for="string"' in length_block

    # Assigned + Count have no marker.
    for slot in ("reviewer:assigned", "reviewer:count"):
        chip_block = body.split(f'data-shaper-col-chip="{slot}"')[1].split(">")[0]
        assert "data-shaper-relevant-for" not in chip_block

    # Field chips carry ``data-shaper-field-data-type`` so the
    # JS knows which bucket to apply when toggled. List fields
    # additionally carry ``data-shaper-field-list-options``
    # (a CSV of options) so the JS can render one option chip
    # per list value in place of the numeric / string
    # aggregates — exercised by the inline progressive-
    # enhancement script.
    assert "data-shaper-field-data-type=" in body


def test_data_shaper_response_field_chip_pool(
    client: TestClient, db: Session
) -> None:
    """Each session instrument carries a hidden
    ``<template data-shaper-field-pool="{id}">`` on the page,
    each member chip carrying the response field's friendly
    label. The progressive-enhancement JS mounts the pool
    into ``data-shaper-field-chips`` when the matching
    instrument scope chip toggles on (and swaps pools when
    the operator switches instruments, since instrument
    chips are mutex). The intra-row ``data-shaper-field-pipe``
    sits between the instrument scope chips and the field
    slot — the JS hides it when no instrument is selected
    so the row doesn't carry an orphan ``|``."""
    review_session = _make_session(client, db, code="ed-shaper-fields")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Field-section pipe and slot live on the top axis row.
    assert "data-shaper-field-pipe" in body
    assert "data-shaper-field-chips" in body
    # Pool template for the default-seeded instrument lives in
    # the markup, each chip wired with the
    # ``data-shaper-field-chip`` attribute carrying
    # ``{instrument_id}:{field_id}`` as the slot key.
    assert f'data-shaper-field-pool="{instrument.id}"' in body
    pool = body.split(
        f'data-shaper-field-pool="{instrument.id}"'
    )[1].split("</template>")[0]
    assert f'data-shaper-field-chip="{instrument.id}:' in pool


def test_data_shaper_tag_chip_labels_resolve_friendly_overrides(
    client: TestClient, db: Session
) -> None:
    """Reviewer / Reviewee tag chip labels render through
    ``field_labels.resolve`` so they pick up operator renames
    done on the Setup pages — falling back to the built-in
    ``Tag 1`` / ``Tag 2`` / ``Tag 3`` when no override is
    set."""
    from app.db.models import User
    from app.services import field_labels

    review_session = _make_session(client, db, code="ed-shaper-friendly")
    actor = db.execute(select(User)).scalars().first()
    assert actor is not None
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Position",
        user=actor,
        correlation_id="ed-shaper-friendly-test",
    )
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_2",
        label="Cohort",
        user=actor,
        correlation_id="ed-shaper-friendly-test",
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    reviewer_pool = body.split('data-shaper-chip-pool="reviewer"')[1].split(
        "</template>"
    )[0]
    reviewee_pool = body.split('data-shaper-chip-pool="reviewee"')[1].split(
        "</template>"
    )[0]
    # Renamed slots render the override.
    assert ">Position<" in reviewer_pool
    assert ">Cohort<" in reviewee_pool
    # Unrenamed slots fall back to the built-in default — the
    # Reviewee Tag 1 / Tag 3 + Reviewer Tag 2 / Tag 3 slots
    # weren't overridden, so ``Tag N`` still renders for them.
    assert ">Tag 2<" in reviewer_pool
    assert ">Tag 3<" in reviewer_pool
    assert ">Tag 1<" in reviewee_pool
    assert ">Tag 3<" in reviewee_pool


def test_data_shaper_instrument_chips_live_on_axis_row(
    client: TestClient, db: Session
) -> None:
    """Per-instrument scope chips sit on the **top axis chip
    row** (right after the ``|`` pipe), not inside the
    per-axis pools. They're session-level filters: visible
    regardless of axis selection, and they use a distinct
    ``data-shaper-instrument-chip`` attribute (vs the per-axis
    ``data-shaper-col-chip`` vocabulary) so the JS can treat
    them as scope filters rather than column-producing chips.

    With no instrument scope chip selected the aggregates
    span every session instrument — matching the "By
    reviewer" / "By reviewee" general-data framing."""
    review_session = _make_session(client, db, code="ed-shaper-pool")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # The card opens with the **scope** chip row (axis chips +
    # instrument scope chips + response-field scope slot)
    # followed by the **content** chip row (per-axis pool of
    # identification + aggregate chips, mounted by the JS into
    # ``data-shaper-relevant-chips``). Both live before the
    # hidden ``<template data-shaper-chip-pool>`` blocks, so
    # slicing up to the first ``data-shaper-chip-pool`` and
    # asserting ordering is sufficient.
    card_slice = body.split('id="extract-data-shaper"')[1].split(
        "data-shaper-chip-pool"
    )[0]
    axis_chip_at = card_slice.index('data-shaper-axis-chip="reviewer"')
    pipe_at = card_slice.index('shaper-axis-pipe')
    instrument_at = card_slice.index('data-shaper-instrument-chip="')
    relevant_slot_at = card_slice.index('data-shaper-relevant-chips')
    # Axis chip ➝ pipe ➝ instrument chip on row 1; the
    # ``data-shaper-relevant-chips`` slot follows on row 2.
    assert axis_chip_at < pipe_at < instrument_at < relevant_slot_at
    # The relevant-chips slot now lives in its own ``<p>``
    # (one row down from the scope chip row).
    assert card_slice.count('class="col-chip-row"') >= 2

    # Each axis pool now carries only two sub-groups —
    # identification + pipe + aggregate. The instrument
    # ``data-shaper-col-chip`` slot retired from both pools.
    for axis in ("reviewer", "reviewee"):
        pool = body.split(f'data-shaper-chip-pool="{axis}"')[1].split(
            "</template>"
        )[0]
        name_at = pool.index(f'data-shaper-col-chip="{axis}:name"')
        pipe_at = pool.index('shaper-axis-pipe')
        count_at = pool.index(f'data-shaper-col-chip="{axis}:count"')
        assert name_at < pipe_at < count_at
        # No instrument-prefixed col chips inside the pool.
        assert f'data-shaper-col-chip="{axis}:instrument-' not in pool


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
    for action in ("save", "edit", "delete", "add", "download"):
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
