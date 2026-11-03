"""The Upload card's renew-and-upload state (segment 20G rung 2, the
scaffold): `operator/partials/_directory_renew.html`. No route sets
`directory_renew` yet, so every roster page renders without it; the
partial itself renders its copy, an inert button and a Dismiss that ends
the hold."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ._invitation_states import _create_session


def _render(**context: object) -> str:
    from starlette.requests import Request

    from app.web.routes_operator._shared import _templates

    request = Request({"type": "http", "path": "/", "root_path": "/reviewrobin", "headers": []})
    template = _templates.env.get_template("operator/partials/_directory_renew.html")
    return template.render(request=request, **context)


def test_nothing_renders_without_the_flag() -> None:
    assert _render(directory_renew=False, directory_renew_dismiss_url="/x").strip() == ""


def test_the_state_says_nothing_was_saved_and_offers_an_inert_renew() -> None:
    html = _render(
        directory_renew=True,
        directory_renew_dismiss_url="/operator/sessions/abc/reviewers/import/dismiss",
    )
    assert "data-directory-renew" in html and "banner-scroll-target" in html
    assert "Nothing was saved" in html and "sign-in to the directory had" in html
    assert "Renew sign-in and upload" in html
    start = html.rindex("<button", 0, html.index("data-directory-renew-upload"))
    button = html[start : html.index(">", start)]
    assert 'type="button"' in button and "disabled" in button
    assert 'formaction="/reviewrobin/operator/sessions/abc/reviewers/import/dismiss"' in html
    assert "form=" not in html


def test_outside_its_form_the_buttons_name_it() -> None:
    html = _render(
        directory_renew=True,
        directory_renew_form="quick-setup-submit-all-form",
        directory_renew_dismiss_url="/operator/sessions/abc/quick-setup/dismiss",
    )
    assert html.count('form="quick-setup-submit-all-form"') == 2


def test_no_roster_page_shows_it_yet(client: TestClient, db: Session) -> None:
    session = _create_session(client, db, code="renew-scaffold")
    for kind in ("reviewers", "reviewees", "observers"):
        page = client.get(f"/operator/sessions/{session.public_id}/{kind}?unlocked=1").text
        assert "data-directory-renew" not in page, kind
    assert "data-directory-renew" not in client.get(f"/operator/sessions/{session.public_id}").text
