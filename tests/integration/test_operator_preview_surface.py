"""Integration tests for the operator-side full preview of the
reviewer surface (Segment 18Q) at
``GET /operator/sessions/{id}/preview-surface/{page_n}``.

Reuses ``_surface_context`` plumbing (same template the reviewer
hits), but bypasses lifecycle / acceptance gates and rewrites the
action-row Prev/Next URLs back at the operator-side preview route
so the operator can flip between operator-defined pages without
ever leaving preview. Save / Discard / Submit render as inert
disabled buttons in ``preview_mode``; the surface ``<form>`` is
replaced by a ``<div>`` so the action row cannot drive any write.

Distinct from the iframe-based preview card on the Previews hub
(``_operations.py``), which renders a synthetic single-page
composite. The Previews hub links here from its surface card.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session_with_reviewer(
    operator: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_emails: list[str] | None = None,
    reviewee_idents: list[str] | None = None,
    extra_instruments: int = 0,
) -> ReviewSession:
    """Create a session, import a reviewer + reviewee, build the
    Full-Matrix assignment graph. Activation is deliberately
    skipped — the preview route is supposed to work on draft /
    validated sessions too, and we want to cover the bypass-gates
    contract."""
    reviewer_emails = reviewer_emails or ["rae@example.edu"]
    reviewee_idents = reviewee_idents or ["carol@example.edu"]
    operator.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    rev_csv = "ReviewerName,ReviewerEmail\n" + "".join(
        f"R{i},{e}\n" for i, e in enumerate(reviewer_emails)
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", rev_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    rev_csv2 = "RevieweeName,RevieweeEmail\n" + "".join(
        f"Carol{i},{e}\n" for i, e in enumerate(reviewee_idents)
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", rev_csv2.encode(), "text/csv")},
        follow_redirects=False,
    )
    for _ in range(extra_instruments):
        operator.post(
            f"/operator/sessions/{review_session.id}/instruments/add-new-model"
        )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    return review_session


# --------------------------------------------------------------------------- #
# Routing — bare URL redirect, page bounds
# --------------------------------------------------------------------------- #


def test_bare_url_303s_to_page_1(client: TestClient, db: Session) -> None:
    session = _make_session_with_reviewer(client, db, code="prev-s-1")
    response = client.get(
        f"/operator/sessions/{session.id}/preview-surface",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{session.id}/preview-surface/1"
    )


def test_bare_url_preserves_reviewer_email(
    client: TestClient, db: Session
) -> None:
    session = _make_session_with_reviewer(client, db, code="prev-s-2")
    response = client.get(
        f"/operator/sessions/{session.id}/preview-surface"
        "?reviewer_email=rae@example.edu",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/operator/sessions/{session.id}/preview-surface/1"
        "?reviewer_email=rae%40example.edu"
    )


def test_out_of_range_page_returns_404(
    client: TestClient, db: Session
) -> None:
    session = _make_session_with_reviewer(client, db, code="prev-s-3")
    response = client.get(
        f"/operator/sessions/{session.id}/preview-surface/99",
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_session_without_reviewers_303s_to_previews_hub(
    client: TestClient, db: Session
) -> None:
    """Empty roster → no reviewer to preview as → redirect to the
    Previews hub where the empty-state message renders."""
    client.post(
        "/operator/sessions",
        data={"name": "Empty", "code": "prev-s-empty"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "prev-s-empty")
    ).scalar_one()
    response = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{session.id}/previews"
    )


def test_unmatched_reviewer_email_303s_back_to_previews(
    client: TestClient, db: Session
) -> None:
    """A non-empty ``?reviewer_email=`` that doesn't match any
    reviewer falls back to the Previews hub (preserving the bad
    query) so the picker's "No reviewer matched" hint renders —
    rather than silently swapping in the first reviewer."""
    session = _make_session_with_reviewer(client, db, code="prev-s-bad")
    response = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
        "?reviewer_email=ghost@example.edu",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{session.id}/previews"
        "?reviewer_email=ghost%40example.edu"
    )


# --------------------------------------------------------------------------- #
# Rendering — uses the reviewer-surface template, preview banner, no write form
# --------------------------------------------------------------------------- #


def test_renders_reviewer_surface_template_with_preview_banner(
    client: TestClient, db: Session
) -> None:
    """Preview reuses the same template the reviewer hits — proves
    the operator sees exactly what the reviewer will see, modulo
    the inert action row and the preview banner."""
    session = _make_session_with_reviewer(client, db, code="prev-s-render")
    body = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
    ).text
    # Preview banner from review_surface.html's preview_mode branch.
    assert "Preview" in body and "not visible to reviewers" in body
    # Instrument section anchors render — proves _surface_context
    # produced the instrument groups.
    assert 'data-rs-position="1"' in body


def test_no_write_form_in_preview(
    client: TestClient, db: Session
) -> None:
    """``preview_mode=True`` replaces ``<form action=".../save">``
    with a ``<div>`` so the page contains no write-path
    ``<form action>``."""
    session = _make_session_with_reviewer(client, db, code="prev-s-noform")
    body = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
    ).text
    # No reviewer save endpoint as a form action.
    assert f'action="/reviewer/sessions/{session.id}/1/save"' not in body
    # No session-wide submit formaction either.
    assert (
        f'formaction="/reviewer/sessions/{session.id}/submit"' not in body
    )


def test_action_row_renders_save_discard_submit_disabled(
    client: TestClient, db: Session
) -> None:
    """In ``preview_mode`` the action row IS included (so the
    operator sees the form chrome) but Save / Discard / Submit
    render as inert disabled ``<button>`` — no ``data-rs-save`` /
    ``data-rs-discard`` hooks, no ``type="submit"``."""
    session = _make_session_with_reviewer(client, db, code="prev-s-actrow")
    body = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
    ).text
    # The action row container is present (a rendered ``<div
    # class="rs-action-row…``, not just the inline-CSS class
    # definition in ``base.html``).
    assert 'class="rs-action-row' in body
    # Save / Discard / Submit appear as labels…
    assert ">Save</button>" in body
    assert ">Discard</button>" in body
    assert ">Submit</button>" in body
    # The boolean ``data-rs-save`` / ``data-rs-discard`` attributes
    # sit at the end of the attribute list on the live Save button
    # and Discard link, so ``data-rs-save>`` is the precise marker
    # for the non-preview chrome (response cells carry the longer
    # ``data-rs-saved-value`` attribute which would substring-match).
    assert "data-rs-save>" not in body
    assert "data-rs-discard>" not in body


# --------------------------------------------------------------------------- #
# Multi-page nav — prev/next URLs point back at the operator route
# --------------------------------------------------------------------------- #


def _split_into_two_pages(db: Session, session_id: int) -> None:
    """Insert a page break between instrument 1 and instrument 2."""
    from app.services import instruments as instruments_service

    instruments = sorted(
        db.execute(
            select(Instrument).where(Instrument.session_id == session_id)
        ).scalars().all(),
        key=lambda i: (i.order, i.id),
    )
    instruments_service.create_page_break_after(db, instrument=instruments[0])


def test_multi_page_nav_links_point_at_operator_preview(
    client: TestClient, db: Session
) -> None:
    session = _make_session_with_reviewer(
        client, db, code="prev-s-mp", extra_instruments=1
    )
    _split_into_two_pages(db, session.id)

    body1 = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
    ).text
    # Page 1 has no Prev (disabled button), has Next pointing at /2.
    next_href = f'href="/operator/sessions/{session.id}/preview-surface/2"'
    assert next_href in body1
    # Prev/Next URLs point at operator route, not reviewer.
    assert f'href="/reviewer/sessions/{session.id}/2"' not in body1
    # Page counter renders.
    assert "Page 1 of 2" in body1

    body2 = client.get(
        f"/operator/sessions/{session.id}/preview-surface/2"
    ).text
    prev_href = f'href="/operator/sessions/{session.id}/preview-surface/1"'
    assert prev_href in body2
    assert "Page 2 of 2" in body2


def test_prev_next_preserve_reviewer_email_query(
    client: TestClient, db: Session
) -> None:
    """Page nav must preserve ``?reviewer_email=`` so the operator
    stays on the same reviewer's preview when flipping pages."""
    session = _make_session_with_reviewer(
        client, db, code="prev-s-mp-q", extra_instruments=1
    )
    _split_into_two_pages(db, session.id)
    body = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
        "?reviewer_email=rae@example.edu"
    ).text
    expected_next = (
        f"/operator/sessions/{session.id}/preview-surface/2"
        "?reviewer_email=rae%40example.edu"
    )
    assert f'href="{expected_next}"' in body


# --------------------------------------------------------------------------- #
# Bypass gates — works on a draft (un-activated) session
# --------------------------------------------------------------------------- #


def test_preview_works_on_draft_session(
    client: TestClient, db: Session
) -> None:
    """The session created above is never activated — it's still in
    the draft state. The preview must still render the action row
    (Save / Discard / Submit disabled) per the banner's
    "bypasses session-status / deadline / acceptance gates" contract.
    The reviewer's actual surface on a draft session would 200 the
    pre-open page instead."""
    session = _make_session_with_reviewer(client, db, code="prev-s-draft")
    db.refresh(session)
    assert session.status == "draft"
    body = client.get(
        f"/operator/sessions/{session.id}/preview-surface/1"
    ).text
    # Action row rendered (the inert form chrome).
    assert 'class="rs-action-row' in body
    assert ">Save</button>" in body


# --------------------------------------------------------------------------- #
# Previews-hub link
# --------------------------------------------------------------------------- #


def test_previews_hub_links_to_full_preview(
    client: TestClient, db: Session
) -> None:
    """The Previews hub's iframe surface card carries an "Open full
    preview" link that targets the new operator-side preview route
    (with the picker's selected reviewer in the query string)."""
    session = _make_session_with_reviewer(client, db, code="prev-s-link")
    body = client.get(
        f"/operator/sessions/{session.id}/previews"
        "?reviewer_email=rae@example.edu"
    ).text
    expected = (
        f"/operator/sessions/{session.id}/preview-surface/1"
        "?reviewer_email=rae%40example.edu"
    )
    assert f'href="{expected}"' in body


# --------------------------------------------------------------------------- #
# Iframe preview should not gain a phantom action row from the new flag
# --------------------------------------------------------------------------- #


def test_iframe_preview_has_no_action_row(
    client: TestClient, db: Session
) -> None:
    """Regression guard — ``build_preview_context`` (the iframe path)
    sets ``preview_mode=True`` but does NOT set ``preview_mode_full``,
    so the synthetic single-page iframe srcdoc must still suppress
    the action row entirely. Without the dedicated flag the iframe
    would gain three disabled ``Save / Discard / Submit`` buttons."""
    from ._preview_iframe import get_surface_preview_html

    session = _make_session_with_reviewer(client, db, code="prev-s-iframe")
    srcdoc = get_surface_preview_html(
        client, session.id, "rae@example.edu"
    )
    # The iframe srcdoc must NOT carry an action-row container ``<div>``
    # — ``rs-action-row`` shows up as a CSS class definition in
    # ``base.html``'s inline stylesheet whether or not the row renders,
    # so checking for the actual rendered ``class="rs-action-row...``
    # is the right marker.
    assert 'class="rs-action-row' not in srcdoc
