"""RRW's pages under the `/reviewrobin` mount emit no unprefixed URL.

Segment 21B (`guide/archive/segment_21B_url_sweep.md`): the static rules in
`tests/unit/test_url_leaks.py` say every emission goes through the
helpers; this renders real pages under the mount and checks what they
emit (`tests/_mounted.py`'s `leaks()`). The B7 crawl visits every GET
route RRW registers; the tests before it pin particular emissions (the
chrome's `return_to`, the redirect targets).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from _mounted import MOUNT, leaks
from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import (
    Assignment,
    DataShape,
    EmailOutbox,
    Instrument,
    InstrumentResponseField,
    InstrumentViewPolicy,
    Invitation,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)

from ._answer_form import answer_form


@pytest.fixture
def session_id(mounted_client: TestClient, db: Session) -> str:
    mounted_client.post(
        f"{MOUNT}/operator/sessions",
        data={"name": "Crawl", "code": "crawl"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "crawl")
    ).scalar_one()
    # The optional Setup pages render only with their toggles on.
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.flush()
    return review_session.public_id


@pytest.fixture
def sys_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


def _user(name: str) -> AuthenticatedUser:
    """alice operates (and, with ``sys_admin``, administers); rae reviews,
    olive observes and carol is reviewed in the seeded session."""
    if name == "alice":
        return AuthenticatedUser(
            principal_id="alice-oid", email="alice@example.edu", name="Alice Example", provider="aad"
        )
    return AuthenticatedUser(
        principal_id=f"{name}-oid", email=f"{name}@example.edu", name=name.title(), provider="aad"
    )


def _activated_session(client: TestClient, db: Session) -> str:
    """A session alice operates and rae reviews, activated, through the mount."""
    sid = _draft_session(client, db)
    _activate(client, db, sid)
    return sid


def _draft_session(client: TestClient, db: Session) -> str:
    """The same session in draft: rosters in, ready to activate."""
    from ._full_matrix import mark_band1_touched_on_all_instruments, pin_full_matrix_on_all_instruments

    base = f"{MOUNT}/operator/sessions"
    client.post(base, data={"name": "Live", "code": "live"}, follow_redirects=False)
    review_session = db.execute(select(ReviewSession).where(ReviewSession.code == "live")).scalar_one()
    sid = review_session.public_id
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"),
    ):
        client.post(
            f"{base}/{sid}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    mark_band1_touched_on_all_instruments(db, review_session.id)
    return sid


def _activate(client: TestClient, db: Session, sid: str) -> None:
    for step in ("prepare", "activate"):
        client.post(f"{MOUNT}/operator/sessions/{sid}/workflow/{step}", follow_redirects=False)
    review_session = db.execute(select(ReviewSession).where(ReviewSession.public_id == sid)).scalar_one()
    db.refresh(review_session)
    assert review_session.status == "ready", review_session.status  # activated: open to reviewers


# --- B2: the chrome ---


@pytest.mark.parametrize("path", ["/operator/no-such-page", "/me/no-such-page"])
def test_the_error_page_emits_only_prefixed_urls(mounted_client: TestClient, path: str) -> None:
    response = mounted_client.get(f"{MOUNT}{path}")
    assert response.status_code == 404
    assert leaks(response) == []


@pytest.mark.usefixtures("sys_admin")
def test_the_operator_chrome_emits_only_prefixed_urls(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sessions")
    assert response.status_code == 200
    assert leaks(response, within="chrome-user") == []
    # Settings, Admin, Guide and About each carry the page's app-relative
    # path as their return_to.
    for target in ("operator/settings", "operator/sys-admin", "guide", "about"):
        assert f'href="{MOUNT}/{target}?return_to=/operator/sessions"' in response.text


def test_the_session_nav_and_breadcrumbs_emit_only_prefixed_urls(
    mounted_client: TestClient, session_id: str
) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sessions/{session_id}/reviewers")
    assert response.status_code == 200
    for region in ("session-nav-grid", "breadcrumb"):
        assert leaks(response, within=region) == [], region


@pytest.mark.usefixtures("sys_admin")
def test_the_sys_admin_nav_emits_only_prefixed_urls(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert leaks(response, within="sys-admin-nav") == []


def test_the_participant_top_bar_emits_only_prefixed_urls(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/me")
    assert response.status_code == 200
    assert leaks(response, within="chrome-user") == []


def test_the_chrome_hides_its_own_page_under_the_mount(mounted_client: TestClient) -> None:
    """``is_here`` compares the app-relative path, so the Guide link is
    hidden on the Guide page under the mount, as at ``/``."""
    response = mounted_client.get(f"{MOUNT}/guide")
    assert response.status_code == 200
    assert f'href="{MOUNT}/guide?' not in response.text
    assert f'href="{MOUNT}/about?return_to=/guide"' in response.text


# --- B5: redirects ---


@pytest.fixture
def active_session_id(mounted_client: TestClient, db: Session) -> str:
    return _activated_session(mounted_client, db)


@pytest.fixture
def rae_client(make_mounted_client: Callable[[AuthenticatedUser], TestClient]) -> TestClient:
    return make_mounted_client(_user("rae"))


def test_the_root_redirects_land_under_the_mount(mounted_client: TestClient) -> None:
    for path in ("/", "/operator"):
        response = mounted_client.get(f"{MOUNT}{path}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == f"{MOUNT}/operator/sessions"


def test_a_post_redirect_lands_under_the_mount(mounted_client: TestClient) -> None:
    response = mounted_client.post(
        f"{MOUNT}/operator/sessions", data={"name": "R", "code": "redir"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"{MOUNT}/operator/sessions/")
    assert leaks(response) == []


@pytest.mark.parametrize("path", ["/me/sessions/{sid}", "/me/sessions/{sid}/summary"])
def test_a_reviewer_redirect_lands_under_the_mount(
    active_session_id: str, rae_client: TestClient, path: str
) -> None:
    response = rae_client.get(f"{MOUNT}{path.format(sid=active_session_id)}", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith(f"{MOUNT}/me")
    assert leaks(response) == []


# --- B7: every GET route ---
#
# One seeded session, visited in four phases: draft; activated; rae
# submitted, which opens the summary; and closed with responses
# released, which opens carol's results and olive's row download. Each
# route names the phase, the user and the status it answers with, so a
# page that turns into a 404 cannot pass as crawled. The operator's
# session pages are read in draft, live and released, because each state
# renders forms the others do not (the unlocked roster and instrument
# editors in draft; Archive and Stop release once closed).

_DRAFT, _LIVE, _SUBMITTED, _RELEASED = "draft", "live", "submitted", "released"
_PHASES = (_DRAFT, _LIVE, _SUBMITTED, _RELEASED)


@dataclass(frozen=True)
class Visit:
    who: str
    status: int
    phase: str = _LIVE


_PAGE = (Visit("alice", 200),)
_EVERY_STATE = tuple(Visit("alice", 200, phase) for phase in (_DRAFT, _LIVE, _RELEASED))
_SESSION = "/operator/sessions/{session_id}"
_EXPORTS = (
    "audit_log.csv",
    "bundle.zip",
    "by_instrument_bundle.zip",
    "data_shapes_bundle.zip",
    "observers.csv",
    "participant_tokens.csv",
    "relationships.csv",
    "responses.csv",
    "responses_bundle.zip",
    "reviewee_metadata.csv",
    "reviewees.csv",
    "reviewer_metadata.csv",
    "reviewers.csv",
    "settings.csv",
)

ROUTES: dict[str, tuple[Visit, ...]] = {
    "/": (Visit("alice", 302),),
    "/operator": (Visit("alice", 302),),
    "/operator/": (Visit("alice", 302),),
    "/about": _PAGE,
    "/auth/me": _PAGE,
    "/auth/me/debug": _PAGE,
    "/guide": _PAGE,
    "/health": _PAGE,
    "/templates/demo.zip": _PAGE,
    "/templates/full.zip": _PAGE,
    "/templates/starter.zip": _PAGE,
    # FastAPI's own pages, on by default.
    "/docs": _PAGE,
    "/docs/oauth2-redirect": _PAGE,
    "/redoc": _PAGE,
    "/openapi.json": _PAGE,
    # The participant surfaces.
    "/me": (Visit("alice", 200), Visit("rae", 200), Visit("olive", 200), Visit("carol", 200, _RELEASED)),
    "/me/invite/{token}": (Visit("rae", 303),),
    "/me/sessions/{session_id}": (Visit("rae", 303),),
    "/me/sessions/{session_id}/{page_n}": (Visit("rae", 200), Visit("rae", 200, _SUBMITTED)),
    "/me/sessions/{session_id}/{page_n}/save": (Visit("rae", 303),),
    "/me/sessions/{session_id}/clear": (Visit("rae", 303),),
    "/me/sessions/{session_id}/submit": (Visit("rae", 303),),
    "/me/sessions/{session_id}/recall": (Visit("rae", 303),),
    "/me/sessions/{session_id}/summary": (Visit("rae", 303), Visit("rae", 200, _SUBMITTED)),
    "/me/sessions/{session_id}/summary.csv": (Visit("rae", 200, _SUBMITTED),),
    "/me/sessions/{session_id}/collation": (Visit("olive", 200), Visit("olive", 200, _RELEASED)),
    "/me/sessions/{session_id}/collation/instruments/{instrument_seq}.csv": (
        Visit("olive", 200, _RELEASED),
    ),
    "/me/sessions/{session_id}/results": (Visit("carol", 200, _RELEASED),),
    # The operator surfaces.
    "/operator/sessions": _PAGE,
    "/operator/sessions/archived": _PAGE,
    "/operator/sessions/new": _PAGE,
    "/operator/sessions/rehydrate": _PAGE,
    # Its token names the dropped rows a rehydrate commit stashes; the
    # crawl runs no rehydrate, so it answers the error page, whose chrome
    # is still read. The body it would answer is a CSV.
    "/operator/sessions/rehydrate/dropped.csv": (Visit("alice", 404),),
    _SESSION: _EVERY_STATE,
    f"{_SESSION}/edit": (Visit("alice", 308),),
    f"{_SESSION}/reviewers": _EVERY_STATE,
    f"{_SESSION}/directory-search": _PAGE,
    f"{_SESSION}/reviewees": _EVERY_STATE,
    f"{_SESSION}/relationships": _EVERY_STATE,
    f"{_SESSION}/observers": _EVERY_STATE,
    f"{_SESSION}/instruments": _EVERY_STATE,
    f"{_SESSION}/instruments/{{instrument_id}}": (Visit("alice", 303),),
    f"{_SESSION}/setup-invite": _EVERY_STATE,
    f"{_SESSION}/assignments": _EVERY_STATE,
    f"{_SESSION}/validate": _EVERY_STATE,
    f"{_SESSION}/preview": (Visit("alice", 308),),
    f"{_SESSION}/previews": (Visit("alice", 308),),
    f"{_SESSION}/preview-surface": (Visit("alice", 303),),
    f"{_SESSION}/preview-surface/{{page_n}}": _EVERY_STATE,
    f"{_SESSION}/invitations": _EVERY_STATE,
    f"{_SESSION}/invitations/reviewers/{{reviewer_id}}": _PAGE,
    f"{_SESSION}/invitations/{{invitation_id}}/detail": (Visit("alice", 308),),
    f"{_SESSION}/monitoring": (Visit("alice", 308),),
    f"{_SESSION}/responses": _EVERY_STATE,
    f"{_SESSION}/responses/{{reviewee_id}}/detail": _EVERY_STATE,
    f"{_SESSION}/extract-data": _EVERY_STATE,
    f"{_SESSION}/extract-data/shapes/{{shape_id}}/download.csv": _PAGE,
    **{f"{_SESSION}/export/{name}": _PAGE for name in _EXPORTS},
    "/operator/settings": _PAGE,
    "/operator/sys-admin": (Visit("alice", 303),),
    "/operator/sys-admin/sessions": _PAGE,
    "/operator/sys-admin/sessions/{session_id}/audit-log": _PAGE,
    "/operator/sys-admin/sessions/{session_id}/outbox": _PAGE,
    "/operator/sys-admin/users": _PAGE,
    "/operator/sys-admin/users/search-options": _PAGE,
    "/operator/sys-admin/users/directory-search": _PAGE,
}


def _get_paths(routes: list[object], prefix: str = "") -> set[str]:
    """Every GET path registered under ``routes``, schema or not. FastAPI
    nests an included router behind its include context, prefix and all."""
    found: set[str] = set()
    for route in routes:
        context = getattr(route, "include_context", None)
        if context is not None:
            found |= _get_paths(context.included_router.routes, prefix + context.prefix)
        elif "GET" in (getattr(route, "methods", None) or ()):
            found.add(prefix + route.path)
    return found


def test_every_get_route_is_crawled() -> None:
    """A new GET route fails here until the crawl visits it, whether or not
    the schema lists it. Built fresh, not the suite's cached instance: a
    test may add a route to that one."""
    from app.main import create_app

    app = create_app()
    registered = _get_paths(app.routes)
    # The walk reads FastAPI internals; if they move, it must not shrink.
    assert {path for path, ops in app.openapi()["paths"].items() if "get" in ops} <= registered
    assert set(ROUTES) == registered
    assert all(ROUTES.values()), "a route with no visit is not crawled"
    pinned_at_404 = {route for route, visits in ROUTES.items() if any(v.status == 404 for v in visits)}
    assert pinned_at_404 == {"/operator/sessions/rehydrate/dropped.csv"}


def _seed_draft(client: TestClient, db: Session) -> tuple[ReviewSession, dict[str, str]]:
    """The draft session, and a value for every path parameter it has yet."""
    sid = _draft_session(client, db)
    review_session = db.execute(select(ReviewSession).where(ReviewSession.public_id == sid)).scalar_one()
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.add(Observer(session_id=review_session.id, email="olive@example.edu", display_name="Olive"))
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Crawl",
            axis="reviewer",
            column_chip_slots=json.dumps(["reviewer:name"]),
        )
    )
    db.commit()
    instrument = _first(db, Instrument, review_session)
    return review_session, {
        "session_id": sid,
        "page_n": "1",
        "instrument_seq": str(instrument.session_seq),
        "instrument_id": str(instrument.id),
        "reviewer_id": str(_first(db, Reviewer, review_session).id),
        "reviewee_id": str(_first(db, Reviewee, review_session).id),
        "shape_id": str(_first(db, DataShape, review_session).id),
    }


def _first(db: Session, model: type, review_session: ReviewSession) -> object:
    return db.execute(select(model).where(model.session_id == review_session.id)).scalars().first()


def _go_live(client: TestClient, db: Session, review_session: ReviewSession, params: dict[str, str]) -> None:
    """Activate, and send rae's invitation for its token."""
    _activate(client, db, review_session.public_id)
    invitation = _first(db, Invitation, review_session)
    client.post(f"{MOUNT}/operator/sessions/{review_session.public_id}/invitations/{invitation.id}/send")
    outbox = db.execute(select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)).scalar_one()
    token = re.search(r"/me/invite/([\w-]+)", outbox.body)
    assert token is not None, outbox.body
    params.update(invitation_id=str(invitation.id), token=token.group(1))
def _submit(client: TestClient, db: Session, review_session: ReviewSession) -> None:
    """rae answers every field on page 1 and submits."""
    assignments = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    fields = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id.in_({a.instrument_id for a in assignments})
        )
    ).scalars().all()
    data = {
        f"response[{a.id}][{f.field_key}]": "1"
        for a in assignments
        for f in fields
        if f.instrument_id == a.instrument_id
    }
    response = client.post(
        f"{MOUNT}/me/sessions/{review_session.public_id}/submit",
        data=answer_form(db, data, page_n=1),
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/summary"), response.headers["location"]


def _release(
    db: Session, review_session: ReviewSession, grant: Callable[..., Instrument]
) -> None:
    """Close the session with responses released: carol holds a grant,
    and olive may download the first instrument's rows, her cohort rule
    taking in rae's."""
    from app.services.visibility_policies import MODE_LABELS

    grant(review_session)
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id, Instrument.session_seq == 1
        )
    ).scalar_one()
    db.execute(select(Reviewer).where(Reviewer.session_id == review_session.id)).scalar_one().tag_1 = "crawl"
    db.execute(select(Observer).where(Observer.session_id == review_session.id)).scalar_one().cohort_rule = {
        "combinator": "AND",
        "rules": [{"field": "reviewer.tag1", "op": "IS", "operand_tag": "", "operand_value": "crawl"}],
    }
    granularity, identification = MODE_LABELS["raw"]
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="observer",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    db.commit()


@pytest.mark.usefixtures("sys_admin")
def test_every_get_route_under_the_mount_emits_only_prefixed_urls(
    db: Session,
    mounted_client: TestClient,
    make_mounted_client: Callable[[AuthenticatedUser], TestClient],
    grant_reviewee_visibility: Callable[..., Instrument],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rehydrate_enabled", True)
    review_session, params = _seed_draft(mounted_client, db)
    failures: list[str] = []
    for phase in _PHASES:
        if phase == _LIVE:
            _go_live(make_mounted_client(_user("alice")), db, review_session, params)
        if phase == _SUBMITTED:
            _submit(make_mounted_client(_user("rae")), db, review_session)
        if phase == _RELEASED:
            _release(db, review_session, grant_reviewee_visibility)
        for route, visits in ROUTES.items():
            for visit in visits:
                if visit.phase != phase:
                    continue
                client = make_mounted_client(_user(visit.who))
                response = client.get(MOUNT + route.format(**params), follow_redirects=False)
                found = leaks(response)
                if response.status_code != visit.status or found:
                    failures.append(f"{phase} {visit.who} {route}: {response.status_code} {found}")
    assert not failures, "\n".join(failures)
