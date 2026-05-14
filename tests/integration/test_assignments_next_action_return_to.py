"""Coverage for the Next Action card forms on the Assignments page
redirecting back to Assignments rather than Session Home.

The duplicated Next Action card uses the ``_REVERT_RETURN_TO``
allowlist on the ``/revert`` route (existing) and a matching
``return_to`` form field on the ``/activate`` route (added with
this slice). The Validate Setup link points at
``/assignments?validated=1`` rather than the Session Home URL; the
Activate-with-warnings detour carries ``?return_to=assignments``
through to the Validate-page banner.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, SessionRuleSet
from app.services import session_lifecycle as lifecycle


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"RT-{code}", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair_plus_pinned(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
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
    rule_set = db.query(SessionRuleSet).filter(
        SessionRuleSet.session_id == review_session.id,
        SessionRuleSet.name == "Full Matrix",
    ).first()
    instrument = db.query(Instrument).filter(
        Instrument.session_id == review_session.id
    ).first()
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()
    db.refresh(review_session)
    return review_session


# --------------------------------------------------------------------------- #
# Validate Setup link points at /assignments?validated=1
# --------------------------------------------------------------------------- #


def test_workflow_card_renders_two_column_grid(
    client: TestClient, db: Session
) -> None:
    """The Workflow card on the Assignments page wraps its existing
    body + stepper row in a ``.next-action-grid`` two-column layout,
    with an empty ``<aside class="next-action-status">`` as the right
    column. PR 2 fills the aside with state-conditional content; this
    test pins the structural markup so the layout can't silently
    regress."""
    review_session = _seed_pair_plus_pinned(client, db, code="rt-grid")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'class="next-action-grid"' in body
    assert 'class="next-action-main"' in body
    assert 'class="next-action-status"' in body
    assert 'id="next-action-status"' in body
    # The body and stepper-buttons divs still render inside the
    # left-column ``next-action-main`` wrapper.
    assert 'class="next-action-body"' in body
    assert 'class="next-action-buttons"' in body
    # The grid wrapper sits inside the card, after the H2.
    card_open = body.find('id="next-action"')
    grid_open = body.find('class="next-action-grid"')
    assert card_open != -1 and grid_open != -1 and grid_open > card_open
    # The right-column aside renders after the left-column main.
    main_open = body.find('class="next-action-main"')
    status_open = body.find('class="next-action-status"')
    assert main_open != -1 and status_open != -1 and status_open > main_open


def test_validate_setup_link_targets_assignments_page(
    client: TestClient, db: Session
) -> None:
    """Draft session past setup-empty → Next Action card's Validate
    Setup button on Assignments page anchors at
    ``/assignments?validated=1`` (not ``/?validated=1`` which is
    Session Home)."""
    review_session = _seed_pair_plus_pinned(client, db, code="rt-validate")
    # Generate so the session leaves the ``is_setup_empty`` state —
    # otherwise the Next Action card body has no action buttons.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/assignments?validated=1"'
        in body
    )
    # Stale Session Home target must not appear.
    assert (
        f'href="/operator/sessions/{review_session.id}?validated=1"'
        not in body
    )


def test_validated_query_param_promotes_draft_to_validated_on_assignments(
    client: TestClient, db: Session
) -> None:
    """``?validated=1`` on the Assignments URL runs validation,
    flips ``draft → validated`` when clean, and renders the Next
    Action card with the inline readiness summary."""
    review_session = _seed_pair_plus_pinned(
        client, db, code="rt-validate-flip"
    )
    # Generate first so there's at least one assignment row.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "draft"
    response = client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    assert response.status_code == 200
    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)


# --------------------------------------------------------------------------- #
# Activate form carries return_to hidden field
# --------------------------------------------------------------------------- #


def test_activate_form_includes_return_to_assignments(
    client: TestClient, db: Session
) -> None:
    """Validated session with no warnings → Next Action card's
    Activate form on Assignments page carries
    ``<input type="hidden" name="return_to" value="assignments">`` so the
    /activate route redirects back here, not to Session Home."""
    review_session = _seed_pair_plus_pinned(client, db, code="rt-activate-rt")
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # The activate form on the Next Action card carries the hidden
    # return_to=assignments token.
    import re
    activate_form = re.search(
        r'(<form[^>]*id="next-action-activate-form"[^>]*>.*?</form>)',
        body,
        re.DOTALL,
    )
    assert activate_form is not None
    assert 'name="return_to"' in activate_form.group(1)
    assert 'value="assignments"' in activate_form.group(1)


def test_activate_post_with_return_to_redirects_to_assignments(
    client: TestClient, db: Session
) -> None:
    """POST /activate with ``return_to=assignments`` lands the
    operator back on the Assignments page rather than Session Home."""
    review_session = _seed_pair_plus_pinned(
        client, db, code="rt-activate-post"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"return_to": "assignments"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )


def test_activate_post_without_return_to_redirects_to_session_home(
    client: TestClient, db: Session
) -> None:
    """No ``return_to`` field → /activate preserves its legacy
    behaviour and lands on Session Home."""
    review_session = _seed_pair_plus_pinned(
        client, db, code="rt-activate-home"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}"
    )


# --------------------------------------------------------------------------- #
# Revert / Pause forms carry return_to
# --------------------------------------------------------------------------- #


def test_revert_form_on_assignments_carries_return_to(
    client: TestClient, db: Session
) -> None:
    """Validated session → Revert to draft form on Assignments
    carries ``return_to=assignments`` so revert lands back here."""
    review_session = _seed_pair_plus_pinned(client, db, code="rt-revert")
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    import re
    revert_form = re.search(
        r'(<form[^>]*id="next-action-revert-form"[^>]*>.*?</form>)',
        body,
        re.DOTALL,
    )
    assert revert_form is not None
    assert 'name="return_to"' in revert_form.group(1)
    assert 'value="assignments"' in revert_form.group(1)


def test_pause_form_on_assignments_carries_return_to(
    client: TestClient, db: Session
) -> None:
    """Ready session → Pause form on Assignments carries
    ``return_to=assignments``."""
    review_session = _seed_pair_plus_pinned(client, db, code="rt-pause")
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    import re
    pause_form = re.search(
        r'(<form[^>]*id="next-action-pause-form"[^>]*>.*?</form>)',
        body,
        re.DOTALL,
    )
    assert pause_form is not None
    assert 'name="return_to"' in pause_form.group(1)
    assert 'value="assignments"' in pause_form.group(1)


# --------------------------------------------------------------------------- #
# Activate-with-warnings detour to Validate carries return_to
# --------------------------------------------------------------------------- #


def test_activate_warnings_detour_link_carries_return_to(
    client: TestClient, db: Session
) -> None:
    """When the Next Action card on Assignments routes Activate
    through ``/validate?activate=1`` (warnings present), the link
    appends ``return_to=assignments`` so the eventual /activate
    POST from the Validate banner lands back on Assignments."""
    # Set up a validated session with warnings: generate, validate,
    # then deactivate all rows to introduce ``no_included_pairs`` +
    # ``zero_included`` warnings.
    review_session = _seed_pair_plus_pinned(
        client, db, code="rt-activate-warn"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_validated(review_session)
    # Deactivate to introduce warnings.
    from app.db.models import Assignment

    db.query(Assignment).filter(
        Assignment.session_id == review_session.id
    ).update({Assignment.include: False})
    db.flush()
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # The Activate button is an anchor to the warnings detour, with
    # return_to appended. HTML escapes the ``&`` as ``&amp;`` so
    # match the rendered form rather than the raw URL.
    assert (
        f'href="/operator/sessions/{review_session.id}/validate?activate=1'
        f'&amp;return_to=assignments"'
        in body
    )


def test_validate_warnings_banner_acknowledge_form_carries_return_to(
    client: TestClient, db: Session
) -> None:
    """Visiting ``/validate?activate=1&return_to=assignments`` on a
    validated session with warnings renders the Acknowledge-and-
    Activate banner with the return_to hidden input attached."""
    review_session = _seed_pair_plus_pinned(
        client, db, code="rt-validate-banner"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    client.get(
        f"/operator/sessions/{review_session.id}?validated=1",
        follow_redirects=False,
    )
    from app.db.models import Assignment

    db.query(Assignment).filter(
        Assignment.session_id == review_session.id
    ).update({Assignment.include: False})
    db.flush()
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/validate?activate=1&return_to=assignments"
    ).text
    assert 'name="return_to"' in body
    assert 'value="assignments"' in body


# --------------------------------------------------------------------------- #
# Session Home unchanged
# --------------------------------------------------------------------------- #


def test_session_home_omits_next_action_card(
    client: TestClient, db: Session
) -> None:
    """Session Home no longer renders the Workflow card at all —
    the card lives on the Operations-row pages only (regression
    guard against accidentally re-adding the include)."""
    review_session = _seed_pair_plus_pinned(client, db, code="rt-home")
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/generate",
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert 'id="next-action"' not in body
    assert 'id="next-action-activate-form"' not in body
    assert 'id="next-action-pause-form"' not in body
    assert 'id="next-action-revert-form"' not in body
    assert 'id="next-action-generate-form"' not in body
