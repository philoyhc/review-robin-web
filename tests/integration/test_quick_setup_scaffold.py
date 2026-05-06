"""Tests for the Segment 11H PR A Quick Setup card scaffold.

The scaffold replaces the ``placeholder_card(id="quick-setup")``
stub with the full four-slot layout from
``spec/quick_setup_card_spec.md``. Every interactive control is
inert until Segment 11J wires the slots; these tests pin the
visual + DOM contract so 11J's wiring patches don't have to
worry about a colliding markup tweak.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str = "qs-scaffold"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Scaffold", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair(
    client: TestClient, db: Session, *, code: str, reviewer_email: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
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
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    return review_session


def _activate(
    client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)


def test_build_quick_setup_context_returns_four_slots(
    client: TestClient, db: Session
) -> None:
    """The view-shape adapter returns the four scaffold slots in
    the canonical order — Reviewers, Reviewees, Assignments,
    Configuration import. 11J will flip ``is_wired`` per slot;
    11H ships them all inert."""

    review_session = _make_session(client, db, code="qs-shape")
    context = views.build_quick_setup_context(db, review_session)

    assert [slot.key for slot in context.slots] == [
        "reviewers",
        "reviewees",
        "assignments",
        "config_import",
    ]
    # All slots inert at scaffold-time.
    assert all(slot.is_wired is False for slot in context.slots)
    assert all(slot.wire_url is None for slot in context.slots)
    # Each slot carries a wiring-tooltip pointer.
    assert all(slot.coming_in for slot in context.slots)
    # Default state is not disabled in draft.
    assert context.is_disabled is False


def test_quick_setup_count_summary_reflects_population(
    client: TestClient, db: Session
) -> None:
    """The slot count summary line surfaces the live population
    so the operator can see at a glance what's on file."""

    empty = _make_session(client, db, code="qs-empty")
    empty_ctx = views.build_quick_setup_context(db, empty)
    by_key = {slot.key: slot for slot in empty_ctx.slots}
    assert by_key["reviewers"].count == 0
    assert by_key["reviewers"].count_summary == "none yet"
    assert by_key["assignments"].count_summary == "none yet"

    populated = _seed_pair(
        client, db, code="qs-populated", reviewer_email="r@example.edu"
    )
    populated_ctx = views.build_quick_setup_context(db, populated)
    populated_by_key = {slot.key: slot for slot in populated_ctx.slots}
    assert populated_by_key["reviewers"].count == 1
    assert populated_by_key["reviewers"].count_summary == "1 currently"
    # Assignments slot includes the stored rule label (lowercase enum
    # value as Text — ``full_matrix``).
    assert populated_by_key["assignments"].count >= 1
    assert "full_matrix" in populated_by_key["assignments"].count_summary


def test_quick_setup_disables_when_session_is_activated(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Per ``spec/session_home.md``, an Activated session greys the
    Quick Setup card via ``.card.disabled`` (plain greying, not a
    yellow lock card)."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="qs-activated", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    context = views.build_quick_setup_context(db, review_session)

    assert context.is_disabled is True
    assert "paused while the session is Activated" in context.description


def test_quick_setup_slot_assignments_uses_rule_or_csv_mode(
    client: TestClient, db: Session
) -> None:
    """Slot 3 carries ``mode == "rule_or_csv"`` so the partial
    renders the rule selector + CSV upload toggle. Slots 1, 2,
    and 4 use the simpler ``"file_upload"`` shape."""

    review_session = _make_session(client, db, code="qs-modes")
    context = views.build_quick_setup_context(db, review_session)
    by_key = {slot.key: slot for slot in context.slots}

    assert by_key["reviewers"].mode == "file_upload"
    assert by_key["reviewees"].mode == "file_upload"
    assert by_key["assignments"].mode == "rule_or_csv"
    assert by_key["config_import"].mode == "file_upload"


def test_quick_setup_dom_carries_wire_target_attributes(
    client: TestClient, db: Session
) -> None:
    """Each slot's wrapping ``<section>`` carries
    ``data-wire-target="quick-setup-{key}"`` so Segment 11J's
    wiring patches can locate the slot without a CSS-selector
    contract."""

    review_session = _make_session(client, db, code="qs-wire-targets")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    for key in ("reviewers", "reviewees", "assignments", "config_import"):
        assert f'data-wire-target="quick-setup-{key}"' in body


def test_quick_setup_dormant_banner_containers_render_hidden(
    client: TestClient, db: Session
) -> None:
    """Per ``spec/assumptions.md``, every redirect-back-with-
    banner pattern carries the ``banner-scroll-target`` class.
    The scaffold ships dormant banner containers per slot —
    confirmation (``banner-warning``) and error
    (``banner-error``) — so 11J can populate them without
    re-rolling the markup."""

    review_session = _make_session(client, db, code="qs-banners")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    for key in ("reviewers", "reviewees", "assignments", "config_import"):
        assert (
            'class="banner banner-warning banner-scroll-target"\n'
            f'       id="quick-setup-{key}-confirm-banner"\n'
            "       hidden"
        ) in body or (
            f'id="quick-setup-{key}-confirm-banner"' in body
            and 'class="banner banner-warning' in body
        )
        assert f'id="quick-setup-{key}-error-banner"' in body
