"""Reviewer summary page — column widths inherited from the
operator's Band 2 column-resize state, and the per-reviewee
identity rendering matching the surface (Name + email).

The summary table is read-only but its column widths should
match what the operator dragged on the Instruments page (the
identity / response-field width entries live on
``Instrument.column_widths``). Pre-fix the template just emitted
a plain ``<table>`` with no width info, so wide-text columns
the operator had deliberately stretched on the reviewer surface
collapsed back to the default flex distribution on /summary.

Pins the post-fix contract:
* Without operator-set widths, the table renders without a
  ``<colgroup>`` (preserves the existing auto-layout).
* With operator-set widths, the table renders a ``<colgroup>``
  with one ``<col>`` per column (identity + one per response
  field), only the columns whose widths are set carry a
  ``style="width:Npx"`` attribute, and the table pins
  ``table-layout: fixed`` so the widths actually take effect.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
)
from app.main import app
from app.web.deps import get_current_user

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _seed_session_with_rae_and_one_reviewee(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
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
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    return review_session


def _activate(operator_client: TestClient, review_session: ReviewSession) -> None:
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )


def _submit(
    rae_client: TestClient, review_session: ReviewSession, db: Session
) -> None:
    assignment_ids = [
        a.id
        for a in db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    ]
    data: dict[str, str] = {}
    for aid in assignment_ids:
        data[f"response[{aid}][rating]"] = "5"
        data[f"response[{aid}][comments]"] = "ok"
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data=data,
        follow_redirects=False,
    )
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        follow_redirects=False,
    )


def test_summary_table_no_colgroup_when_widths_unset(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """When ``Instrument.column_widths`` is empty / NULL the
    summary table has no ``<colgroup>`` and no ``table-layout:
    fixed`` — preserves the legacy auto-distributed layout."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="sum-widths-none", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "<colgroup>" not in body
    # ``base.html`` carries a CSS rule ``table.rs-group-table {
    # table-layout: fixed; }``, so the bare substring would
    # always be present. The check is specifically that the
    # summary table's <table> tag doesn't carry the inline
    # ``style="table-layout: fixed;"`` attribute.
    assert 'style="table-layout: fixed;"' not in body


def test_summary_table_emits_col_widths_from_instrument(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """With ``Instrument.column_widths`` populated, the summary
    table renders a ``<colgroup>`` with one ``<col>`` per
    column (identity + each response field). Columns whose
    width is set carry ``style="width:Npx"``; columns whose
    width is unset render as bare ``<col>`` (auto-distribute).
    """
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="sum-widths-set", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    # Set per-column widths on the instrument directly. Mirrors
    # what Band 2's drag-resize handler writes to
    # ``instrument.column_widths``.
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(
                InstrumentResponseField.order, InstrumentResponseField.id
            )
        ).scalars()
    )
    rating_field, comments_field = fields[0], fields[1]
    instrument.column_widths = {
        "identity": 220,
        f"rf_{rating_field.id}": 90,
        f"rf_{comments_field.id}": 400,
    }
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text

    # ``<colgroup>`` is present, with the explicit widths for
    # identity + each response field. The table tag carries
    # ``style="table-layout: fixed;"`` so the widths actually
    # take effect (a layout-auto table would auto-distribute).
    assert "<colgroup>" in body
    assert 'style="table-layout: fixed;"' in body
    assert 'style="width: 220px"' in body  # identity
    assert 'style="width: 90px"' in body   # rating
    assert 'style="width: 400px"' in body  # comments


def test_summary_table_partial_widths_only_styles_set_columns(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Operator dragged one column only — the others
    auto-distribute. The ``<col>`` for an unset column renders
    as a bare ``<col>`` with no ``style="width:..."`` attr, so
    it absorbs the leftover horizontal space."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="sum-widths-partial", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(
                InstrumentResponseField.order, InstrumentResponseField.id
            )
        ).scalars()
    )
    rating_field = fields[0]
    instrument.column_widths = {f"rf_{rating_field.id}": 90}
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    # Identity column lacks an explicit width — it must NOT
    # carry a ``style="width:...px"`` attribute on any of its
    # <col> tags.
    assert "<colgroup>" in body
    assert 'style="width: 90px"' in body
    # The rendered colgroup includes a bare ``<col>`` for
    # identity. Hard to assert precisely without parsing HTML;
    # but the *number* of ``style="width:`` occurrences inside
    # ``<colgroup>`` must equal the number of set widths (1).
    colgroup_start = body.find("<colgroup>")
    colgroup_end = body.find("</colgroup>", colgroup_start)
    assert colgroup_start != -1 and colgroup_end != -1
    colgroup_html = body[colgroup_start : colgroup_end + len("</colgroup>")]
    assert colgroup_html.count('style="width:') == 1


def test_summary_per_reviewee_identity_carries_name_and_email(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Per-reviewee identity cell mirrors the surface:
    ``<strong>Name</strong><br><code>email</code>``."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="sum-identity", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "<strong>Carol</strong>" in body
    assert "<code>carol@example.edu</code>" in body
    # Required field marker — ``rating`` is required, so the
    # header reads "Rating *".
    assert "Rating *" in body


def test_summary_includes_visible_display_field_columns(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """If the operator marked a reviewee tag display field
    visible (alongside Carol's tag value), it renders as a
    column on the summary table — same column order as the
    response surface."""
    from app.db.models import (
        Instrument,
        InstrumentDisplayField,
        Reviewee,
    )

    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="sum-disp", reviewer_email=rae.email
    )
    carol = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == review_session.id
        )
    ).scalar_one()
    carol.tag_1 = "Team Alpha"
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    tag1_df = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .where(InstrumentDisplayField.source_type == "reviewee")
        .where(InstrumentDisplayField.source_field == "tag_1")
    ).scalar_one_or_none()
    if tag1_df is None:
        # Synthesise the row with the friendly label populated;
        # ``ensure_locked_display_fields`` only auto-creates the
        # Name + Email identity rows.
        tag1_df = InstrumentDisplayField(
            instrument_id=instrument.id,
            source_type="reviewee",
            source_field="tag_1",
            label="Tag 1",
            order=99,
            visible=True,
        )
        db.add(tag1_df)
    else:
        tag1_df.visible = True
    db.commit()

    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    # The display column header AND Carol's tag value land
    # on the summary, same as the surface would render.
    assert "Tag 1" in body
    assert "Team Alpha" in body
