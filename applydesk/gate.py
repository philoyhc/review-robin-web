"""Who reaches Apply Desk's pages (segment AD1, item 2; segment AD2A,
rulings 73 and 75).

- **Operator pages** (`/operator/…`) answer only an operator:
  `require_exercise_operator`, a FastAPI dependency on that router, as
  Review Robin's per-session check (`app/web/deps.py`). The platform
  super-admin reaches everything. Anyone else must be on the allowlist
  (`operators.may_operate`) and, on an exercise's pages, hold a current
  grant on it. Everyone else gets 404, so the pages do not say they exist.
- **The participant's pages** (`/me/…`) and the landing are still the
  placeholders': anyone on a local run, deployed only the super-admin
  (`placeholders_only`), until a later AD2 segment matches applicants.

The viewer is resolved once per request (`people.resolve`, which binds a
pending person at their first sign-in) and the answer kept on
`request.state`, so the check and the page's switcher read one lookup.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select

from applydesk import db, operators, people
from applydesk.models import Exercise
from cordware.identity import current_identity, is_local


@dataclass(frozen=True)
class Viewer:
    """What the gate knows of the signed-in viewer: whether they are the
    platform super-admin, whether they may operate, and the public IDs of
    the exercises they operate (None for the super-admin: every one)."""

    is_super_admin: bool
    may_operate: bool
    operates: frozenset[str] | None


_NOBODY = Viewer(is_super_admin=False, may_operate=False, operates=frozenset())
_STATE = "applydesk_viewer"


def viewer(request: Request) -> Viewer:
    """The viewer, looked up once per request."""
    held = getattr(request.state, _STATE, None)
    if isinstance(held, Viewer):
        return held
    found = _look_up(request)
    setattr(request.state, _STATE, found)
    return found


def _look_up(request: Request) -> Viewer:
    identity = current_identity(request)
    if identity is None:
        return _NOBODY
    if identity.is_super_admin:
        return Viewer(is_super_admin=True, may_operate=True, operates=None)
    if not (identity.tenant_id or "").strip() or not (identity.principal_id or "").strip():
        return _NOBODY  # cannot be bound, so cannot be on the allowlist
    session = db.new_session()
    try:
        person = people.resolve(session, identity)
        session.commit()
        actor = operators.Actor(person)
        if not operators.may_operate(person):
            return _NOBODY
        operates = frozenset(e.public_id for e in operators.operated_exercises(session, actor))
        return Viewer(is_super_admin=False, may_operate=True, operates=operates)
    finally:
        session.close()


def is_operator(request: Request) -> bool:
    """Whether the viewer lands on the Operator Lobby and sees it in the
    switcher (Cordware's lobbies, 2026-11-13): the super-admin, or someone
    on the allowlist, who may make an exercise though they operate none."""
    return viewer(request).may_operate


def operates(request: Request, public_id: str) -> bool:
    found = viewer(request)
    return found.may_operate and (found.operates is None or public_id in found.operates)


def require_exercise_operator(request: Request) -> None:
    """The operator router's check: 404 unless the viewer may operate and,
    on an exercise's pages (an `exercise_id` in the path), operates it."""
    if not is_operator(request):
        raise HTTPException(status_code=404)
    exercise_id = request.path_params.get("exercise_id")
    if isinstance(exercise_id, str) and not operates(request, exercise_id):
        raise HTTPException(status_code=404)


def own_new_exercise(request: Request, public_id: str) -> bool:
    """Make the `exercise` row for a new scratch exercise with the viewer
    its Owner (ruling 73), in one transaction. False, and nothing made, if
    the viewer cannot be bound or may not make one, or the ID is taken."""
    identity = current_identity(request)
    if identity is None:
        return False
    session = db.new_session()
    try:
        person = people.resolve(session, identity)
        actor = operators.Actor(person, is_super_admin=identity.is_super_admin)
        if session.scalar(select(Exercise.id).where(Exercise.public_id == public_id)):
            return False
        operators.create_exercise(session, actor, public_id)
        session.commit()
    except operators.Refused:
        session.rollback()
        return False
    finally:
        session.close()
    setattr(request.state, _STATE, None)  # its grants changed
    return True


def placeholders_only(request: Request) -> None:
    """The participant's pages and the landing, until a later AD2 segment:
    anyone on a local run, deployed only the platform super-admin."""
    if is_local():
        return
    identity = current_identity(request)
    if identity is None or not identity.is_super_admin:
        raise HTTPException(status_code=404)
