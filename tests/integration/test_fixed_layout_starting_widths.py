"""Starting widths under a fixed table layout (19T Item 16, entry 1).
``rs-narrow`` is ``width: 1%``, which a fixed-layout table reads as 1% of
the table, so an unsized narrow column started squished to a sliver: the
profile-link column in the Band 2 preview (always fixed), and the
profile, numeric and status columns on the reviewer surface, the
reviewer summary and the reviewee results once any column width is set.
The profile column now starts at its header's width, a numeric column at
its header / digit span, and the status column at a fixed 4ch; an
operator-set width wins."""

from __future__ import annotations

import re
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentDisplayField, InstrumentResponseField, Reviewee
from app.web.views import numeric_column_ch_width, profile_column_ch_width

from .test_reviewer_surface_display_fields import (  # noqa: F401 (fixture)
    _activate,
    _operator_creates_session_with_pair,
    rae,
)


def test_the_width_fits_the_header_and_the_link() -> None:
    assert profile_column_ch_width("Profile") == len("Profile") + 4
    assert profile_column_ch_width("") == len("View") + 3


def _surface_cols(
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
    alice: AuthenticatedUser,
    rae_user: AuthenticatedUser,
    code: str,
    widths: dict,
) -> list[str]:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator, db, code=code,
        reviewer_email="rae@example.edu", reviewee_ident="carol@example.edu",
    )
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()
    reviewee.profile_link = "https://example.edu/carol"
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    profile = InstrumentDisplayField(
        instrument_id=instrument.id, label="", source_type="reviewee",
        source_field="profile_link", order=10, visible=True,
    )
    db.add(profile)
    db.flush()
    instrument.column_widths = {
        key.replace("PROFILE", str(profile.id)): value for key, value in widths.items()
    }
    db.commit()
    _activate(operator, db, review_session)
    body = make_client(rae_user).get(f"/me/sessions/{review_session.id}").text
    colgroup = body.split("<colgroup>")[1].split("</colgroup>")[0]
    return re.findall(r"<col[^>]*>", colgroup)


def test_the_surface_starts_an_unsized_profile_column_at_its_header(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,  # noqa: F811 (fixture)
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    cols = _surface_cols(db, make_client, alice, rae, "prof-width", {"identity": 200})
    assert f'<col style="width: {profile_column_ch_width("Profile")}ch">' in cols
    # The numeric Rating column starts at its header / digit span.
    rating = db.execute(
        select(InstrumentResponseField).where(InstrumentResponseField.field_key == "rating")
    ).scalars().first()
    assert f'<col style="width: {numeric_column_ch_width(rating)}ch">' in cols


def test_the_status_column_takes_a_fixed_width() -> None:
    from pathlib import Path

    templates = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
    surface = (templates / "reviewer" / "review_surface.html").read_text()
    assert '<th scope="col" class="rs-status"><span class="visually-hidden">Status</span></th>' in surface
    assert "th.rs-status { width: 4ch; }" in (templates / "base.html").read_text()


def test_an_operator_set_profile_width_wins(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,  # noqa: F811 (fixture)
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    cols = _surface_cols(db, make_client, alice, rae, "prof-width-set", {"df_PROFILE": 90})
    assert '<col style="width: 90px">' in cols
    assert f'<col style="width: {profile_column_ch_width("Profile")}ch">' not in cols


def test_the_preview_mirrors_it(client: TestClient, db: Session) -> None:
    from .test_instrument_builder_routes import _new_model_with_tags

    review_session, instrument = _new_model_with_tags(client, db, code="prof-width-preview")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    assert (
        "function profileColumnCh(label) { return Math.max(String(label || '').length + 4, 'View'.length + 3); }"
        in flat
    )
    assert "? 'width: ' + profileColumnCh(o.label) + 'ch;' : colStyle(o.width);" in flat
    # An unsized number column starts at the surface's width, in both the
    # per-reviewee and the group preview (19T Item 16).
    assert (
        "return Math.max(String(label || '').length + (required ? 2 : 0) + 4, span + 3);"
        in flat
    )
    assert "return ch ? 'width: ' + ch + 'ch;' : colStyle(r.width);" in flat
    assert "'\" style=\"' + responseColStyle(card, r) + '\">'" in flat
    assert "'\" style=\"' + colStyle(r.width) + '\">'" not in flat
    # A drag starts from the header's width where a browser sizes no
    # <col>, never from the ch value read as px (the fix's read).
    assert (
        "var startWidth = col.offsetWidth || (headCell && headCell.offsetWidth) "
        "|| parseInt(col.style.width, 10) || 100;"
    ) in flat


def test_the_summary_and_the_results_start_it_the_same_way(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Both share the surface's fixed layout once a width is set (the
    rung's spec check)."""
    from .test_reviewee_results_body import (
        _enable_reviewee_after_release_raw,
        _operator_user,
        _seed_and_activate,
        _seed_submitted_responses,
    )

    # The reviewer and reviewee ``_seed_and_activate`` rosters.
    rae_user = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae Reviewer", provider="aad"
    )
    carol = AuthenticatedUser(
        principal_id="carol-oid", email="carol@example.edu", name="Carol Reviewee", provider="aad"
    )
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="prof-width-pages")
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().first()
    for reviewee in db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars():
        reviewee.profile_link = "https://example.edu/p"
    db.add(InstrumentDisplayField(
        instrument_id=instrument.id, label="", source_type="reviewee",
        source_field="profile_link", order=10, visible=True,
    ))
    instrument.column_widths = {"identity": 220}
    db.commit()
    _seed_submitted_responses(db, review_session, comments_value="Solid work.")
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )
    width = f'style="width: {profile_column_ch_width("Profile")}ch"'
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    numeric = f'style="width: {numeric_column_ch_width(rating)}ch"'
    summary = make_client(rae_user).get(f"/me/sessions/{review_session.id}/summary").text
    results = make_client(carol).get(f"/me/sessions/{review_session.id}/results").text
    for name, body in (("summary", summary), ("results", results)):
        assert 'style="table-layout: fixed;"' in body, name
        assert ">Profile</th>" in body, name
        colgroup = body.split("<colgroup>")[1].split("</colgroup>")[0]
        assert width in colgroup, name
        assert numeric in colgroup, name
