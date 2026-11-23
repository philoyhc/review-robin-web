"""Who reaches Apply Desk's pages (segment AD1, item 2; segment AD2A,
rulings 73 and 75).

- **Operator pages** (`/operator/…`) answer only an operator:
  `require_exercise_operator`, a FastAPI dependency on that router, as
  Review Robin's per-session check (`app/web/deps.py`). The platform
  super-admin or someone on the allowlist (`operators.may_operate`) reaches
  the Lobby; on an exercise's pages each must hold a current grant on it,
  the super-admin included: they adopt the rest from Admin (segment AD2M).
  Everyone else gets 404, so the pages do not say they exist.
- **The Admin pages** (`/admin/…`) answer the super-admin and Admins
  (`require_admin`).
- **The participant's pages** (`/me/…`) and the landing are still the
  placeholders': anyone on a local run, deployed only the super-admin
  (`placeholders_only`), until a later AD2 segment matches applicants.

The viewer is resolved once per request (`people.resolve`, which binds a
pending person at their first sign-in) and the answer kept on
`request.state`, so the check and the page's switcher read one lookup.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from applydesk import db, exercises, operators, people
from cordware.identity import current_identity, is_local


@dataclass(frozen=True)
class Viewer:
    """What the gate knows of the signed-in viewer: whether they are the
    platform super-admin, whether they may operate, and the public IDs of
    the exercises they own or operate (the super-admin's too: they adopt
    the rest, segment AD2M)."""

    is_super_admin: bool
    may_operate: bool
    operates: frozenset[str]
    is_admin: bool = False  # an Admin (segment AD2M): reaches the Admin pages
    owns: frozenset[str] = frozenset()  # of `operates`, those they own (AD2O)


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
    bindable = (identity.tenant_id or "").strip() and (identity.principal_id or "").strip()
    if identity.is_super_admin and not bindable:
        # The super-admin, unbound: the Admin pages and the Lobby, but no
        # exercise, since adopting one needs a person (segment AD2M).
        return Viewer(is_super_admin=True, may_operate=True, operates=frozenset())
    if not bindable:
        return _NOBODY  # cannot be bound, so cannot be on the allowlist
    session = db.new_session()
    try:
        person = people.resolve(session, identity)
        session.commit()
        if identity.is_super_admin:
            # Every exercise they reach, they own or operate: they adopt
            # the rest from Admin (segment AD2M).
            mine = operators.operated_exercises(
                session, operators.Actor(person, is_super_admin=True)
            )
            return Viewer(
                is_super_admin=True,
                may_operate=True,
                operates=frozenset(e.public_id for e in mine),
                owns=operators.owned_ids(session, person),
            )
        actor = operators.Actor(person)
        if not operators.may_operate(person):
            return _NOBODY
        operates = frozenset(e.public_id for e in operators.operated_exercises(session, actor))
        return Viewer(
            is_super_admin=False,
            may_operate=True,
            operates=operates,
            is_admin=operators.is_admin(person),
            owns=operators.owned_ids(session, person),
        )
    finally:
        session.close()


def is_operator(request: Request) -> bool:
    """Whether the viewer lands on the Operator Lobby and sees it in the
    switcher (Cordware's lobbies, 2026-11-13): the super-admin, or someone
    on the allowlist, who may make an exercise though they operate none."""
    return viewer(request).may_operate


def operates(request: Request, public_id: str) -> bool:
    found = viewer(request)
    return found.may_operate and public_id in found.operates


def owns(request: Request, public_id: str) -> bool:
    """Whether the viewer owns the exercise (segment AD2O)."""
    return public_id in viewer(request).owns


def require_exercise_operator(request: Request) -> None:
    """The operator router's check: 404 unless the viewer may operate and,
    on an exercise's pages (an `exercise_id` in the path), operates it."""
    if not is_operator(request):
        raise HTTPException(status_code=404)
    exercise_id = request.path_params.get("exercise_id")
    if isinstance(exercise_id, str) and not operates(request, exercise_id):
        raise HTTPException(status_code=404)
    # An archived exercise is read-only until restored (the author,
    # 2026-11-22; as Review Robin's archived sessions): its pages open,
    # but nothing posted to them changes it.
    if (
        isinstance(exercise_id, str)
        and request.method not in ("GET", "HEAD")
        and exercises.is_archived(exercise_id)
    ):
        raise HTTPException(
            status_code=409, detail="Archived: restore it from the Archive to change it."
        )


def forget_viewer(request: Request) -> None:
    """Drop the viewer looked up for this request: their grants changed."""
    setattr(request.state, _STATE, None)


def is_admin(request: Request) -> bool:
    """Whether the viewer reaches the Admin pages: the super-admin or an
    Admin (segment AD2M)."""
    found = viewer(request)
    return found.is_super_admin or found.is_admin


def require_admin(request: Request) -> None:
    """The Admin pages' check (ruling 75, segment AD2M): the super-admin or
    an Admin; 404 for everyone else, an operator included."""
    if not is_admin(request):
        raise HTTPException(status_code=404)


def landing(request: Request) -> None:
    """`/` and `/operator`: an operator (the super-admin, or someone on the
    operator list) lands on the Operator Lobby, deployed too; anyone else
    is held to the placeholders' gate until a later AD2 segment
    (spec-writer at the AD2A close)."""
    if is_operator(request):
        return
    placeholders_only(request)


def reaches_placeholders(request: Request) -> bool:
    """Whether the viewer reaches the participant's pages: anyone on a
    local run, deployed only the platform super-admin. The pages that link
    there (the switcher's User Lobby, a dossier's *View as evaluators see
    it*) offer the link only when it answers (the author's ruling at the
    AD2A close: hide the links, keep the gate)."""
    if is_local():
        return True
    identity = current_identity(request)
    return identity is not None and identity.is_super_admin


def placeholders_only(request: Request) -> None:
    """The participant's pages, until a later AD2 segment:
    `reaches_placeholders`, else 404."""
    if not reaches_placeholders(request):
        raise HTTPException(status_code=404)


def same_site(request: Request) -> None:
    """Every post comes from Apply Desk's own pages (AD-126): a browser
    naming another site in ``Sec-Fetch-Site`` is refused; one that sends
    no such header (Safari before 16.4) must name this origin in
    ``Origin``, else in ``Referer``, or the post is refused too. The host
    sets the request's scheme and host to the public origin (segment 21E),
    so the request's own URL is the origin to match."""
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        if site not in ("same-origin", "none"):
            raise HTTPException(status_code=403)
        return
    here = f"{request.url.scheme}://{request.url.netloc}"
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        referer = request.headers.get("referer", "")
        parts = urlsplit(referer)
        origin = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""
    if origin != here:
        raise HTTPException(status_code=403)
