"""The ``W`` overlay rides on States 4 / 5 / 6 — it does not replace them.

``spec/workflow_card.md`` modelled ``4W`` as a state in the cascade,
tested *before* invitation state, which made it mutually exclusive with
States 5 and 6.  The template has never worked that way: it branches on
invitation state to choose the body and then appends the warning
help-line independently, and ``send_invites_visible`` reads invitation
state alone.  Author's ruling, 19O Item 7 entry 14 (2026-09-19): the
spec was wrong, ``W`` is an overlay, and ``5W`` / ``6W`` are real.

Nothing pinned any of that — ``needs_acknowledge`` and ``4W`` appeared
nowhere under ``tests/`` — so the model could drift again in silence.
These cases pin it by effect, each against a no-warning control, so a
cascade that started suppressing the invitation body would go red.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
# Relative, per the `._display_field_helpers` convention in this
# package: `tests/` has no `__init__.py`, so `tests.integration` is
# importable only when the repo root happens to be on `sys.path`.
# `python -m pytest` puts it there and the `pytest` console script does
# not — which is how an absolute import passed here and failed on
# `ci-postgres`.
from .test_invitations import _create_session, _populate

STATE_4_BODY = "there are no invitations"
STATE_5_BODY = "Invitations are ready to send"
STATE_6_BODY = "Invitations are marked sent"
OVERLAY_HELP = "review on Validate before activating"


def _prepared_session(
    client: TestClient, db: Session, code: str, *, warning: bool
) -> ReviewSession:
    """Validated, with one invitation generated.

    ``warning=True`` adds a reviewee under a non-email identifier, which
    raises the W8 ``reviewees.unreachable_for_results`` soft warning.
    W8 is non-blocking, so Prepare still validates clean enough to
    create the invitation — which is the whole point: the overlay and
    the invitation state are independent.
    """
    session = _create_session(client, db, code)
    _populate(client, db, session.id, reviewer_email="rae@example.edu")
    if warning:
        response = client.post(
            f"/operator/sessions/{session.id}/reviewees/create",
            data={
                "name": "Anon",
                "email_or_identifier": "anon-2026",
                "profile_link": "",
                "tag_1": "",
                "tag_2": "",
                "tag_3": "",
                "status": "active",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
    response = client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(session)
    return session


def _home(client: TestClient, session_id: int) -> str:
    response = client.get(f"/operator/sessions/{session_id}")
    assert response.status_code == 200
    return response.text


def _button_row(body: str) -> str:
    """The single button row at the bottom of the card's left column."""
    start = body.find("next-action-buttons next-action-buttons-row")
    assert start != -1, "button row not found"
    end = body.find("</div>", body.find("</div>", start) + 1)
    return body[start:end]


def test_the_overlay_adds_its_help_line_to_state_5_rather_than_replacing_it(
    client: TestClient, db: Session
) -> None:
    """`5W` is State 5 plus the help-line, not State 4."""
    session = _prepared_session(client, db, "w-over-5", warning=True)
    body = _home(client, session.id)
    assert STATE_5_BODY in body
    assert OVERLAY_HELP in body
    assert STATE_4_BODY not in body


def test_without_a_warning_the_same_session_renders_state_5_alone(
    client: TestClient, db: Session
) -> None:
    """The control. Without it the case above proves nothing: a page
    that never had a warning would satisfy two of its three asserts."""
    session = _prepared_session(client, db, "w-ctrl-5", warning=False)
    body = _home(client, session.id)
    assert STATE_5_BODY in body
    assert OVERLAY_HELP not in body


def test_the_overlay_reaches_state_6_too(
    client: TestClient, db: Session
) -> None:
    """`6W`, which the old cascade also said could not exist."""
    session = _prepared_session(client, db, "w-over-6", warning=True)
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    body = _home(client, session.id)
    assert STATE_6_BODY in body
    assert OVERLAY_HELP in body
    assert STATE_5_BODY not in body


def test_the_overlay_changes_no_button_visibility(
    client: TestClient, db: Session
) -> None:
    """Four slots either way — Revert, Prepare, Send invites, Activate.

    ``send_invites_visible`` reads invitation state alone, so the
    overlay cannot take a button away. The spec's `4W` column claimed
    three and was silent about this case.
    """
    warned = _button_row(
        _home(client, _prepared_session(client, db, "w-btn-a", warning=True).id)
    )
    plain = _button_row(
        _home(client, _prepared_session(client, db, "w-btn-b", warning=False).id)
    )
    for row in (warned, plain):
        assert row.count("Revert<br>to draft") == 1
        assert row.count("Prepare<br>session") == 1
        assert row.count("Send<br>invites") == 1
        assert row.count("Activate<br>session") == 1


def test_the_overlay_turns_activate_into_the_warnings_detour(
    client: TestClient, db: Session
) -> None:
    """The overlay's third effect, also independent of invitations:
    Activate becomes an `<a>` to `/validate?activate=1` instead of a
    form submit."""
    warned_id = _prepared_session(client, db, "w-detour-a", warning=True).id
    plain_id = _prepared_session(client, db, "w-detour-b", warning=False).id

    warned = _button_row(_home(client, warned_id))
    assert f"/operator/sessions/{warned_id}/validate?activate=1" in warned
    assert "next-action-activate-session-form" not in warned

    plain = _button_row(_home(client, plain_id))
    assert f"/operator/sessions/{plain_id}/validate?activate=1" not in plain
    assert "next-action-activate-session-form" in plain


def test_the_session_really_is_validated_with_an_invitation(
    client: TestClient, db: Session
) -> None:
    """Anti-vacuity: the fixture's premise, asserted rather than assumed.

    If Prepare ever stopped creating the invitation, every case above
    would still pass its `not in` asserts while testing State 4.
    """
    from app.db.models import Invitation

    session = _prepared_session(client, db, "w-premise", warning=True)
    assert session.status == "validated"
    invitations = (
        db.execute(
            select(Invitation).where(Invitation.session_id == session.id)
        )
        .scalars()
        .all()
    )
    assert len(invitations) == 1
