"""The profile-link column's starting width under a fixed table layout
(the author, 2026-09-29): its ``rs-narrow`` hint is ``width: 1%``, which
a fixed-layout table reads as 1% of the table, so an unsized column
started squished to a sliver in the Band 2 preview (always fixed) and
on the reviewer surface once any column width is set. It now starts
wide enough for its header; an operator-set width wins."""

from __future__ import annotations

import re
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentDisplayField, Reviewee
from app.web.views import profile_column_ch_width

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


def test_an_operator_set_profile_width_wins(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,  # noqa: F811 (fixture)
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    cols = _surface_cols(db, make_client, alice, rae, "prof-width-set", {"df_PROFILE": 90})
    assert '<col style="width: 90px">' in cols
    assert not any(c.endswith('ch">') for c in cols)


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
