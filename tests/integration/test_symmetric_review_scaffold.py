"""Segment 20B rung 1: the symmetric-review scaffold.

Every control is inert: nothing posts a ``symmetric_review`` field, and
the pages behave as before without ``?symmetric_preview=``. With it, the
mode-on states render so the author can judge them: the greyed Reviewees
slot, the read-only Reviewees page, and the Reviewees tab unmarked
(``plain``) or marked (``marked``). Rung 2 replaces the preview with the
stored setting and deletes these preview assertions.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Sym", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def test_the_new_session_checkbox_is_inert_and_box_first(client: TestClient) -> None:
    body = client.get("/operator/sessions/new").text
    card = body[body.find('id="user-interface-settings"'):]
    box = card.find("data-symmetric-review")
    assert box != -1
    assert box < card.find("Symmetric review\n"), "the checkbox comes first (20C Item 2)"
    tag = card[card.rfind("<input", 0, box):card.find(">", box)]
    assert "name=" not in tag and "disabled" in tag
    assert 'name="symmetric_review"' not in body


def test_without_the_preview_nothing_changes(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-off")
    base = f"/operator/sessions/{review_session.public_id}"
    for path in ("/operator/sessions/new", base, f"{base}/reviewees"):
        body = client.get(path).text
        assert "data-symmetric-mirrored" not in body
        assert "data-symmetric-mark" not in body
    reviewees = client.get(f"{base}/reviewees").text
    assert 'id="roster-unlock-btn"' in reviewees


def test_the_preview_greys_the_reviewees_slot(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-slot")
    for path in (
        "/operator/sessions/new?symmetric_preview=plain",
        f"/operator/sessions/{review_session.public_id}?symmetric_preview=plain",
    ):
        body = client.get(path).text
        slot = body[body.find('id="quick-setup-reviewees"'):]
        slot = slot[: slot.find("</section>")]
        assert "data-symmetric-mirrored" in slot
        assert 'name="reviewees_file"' not in slot
        reviewers = body[body.find('id="quick-setup-reviewers"'):]
        assert 'name="reviewers_file"' in reviewers[: reviewers.find("</section>")]


def test_the_preview_makes_the_reviewees_page_read_only(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-page")
    base = f"/operator/sessions/{review_session.public_id}"
    body = client.get(f"{base}/reviewees?symmetric_preview=plain").text
    assert "data-symmetric-mirrored" in body
    assert f'href="{base}/reviewers"' in body
    for gone in (
        'id="roster-unlock-btn"',
        'id="roster-unlock-panel"',
        'id="reviewee-self-fields"',
        'id="upload-csv"',
        'id="reviewees-bulk-form"',
    ):
        assert gone not in body, gone


def test_the_tab_is_plain_or_marked(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-tab")
    path = f"/operator/sessions/{review_session.public_id}/reviewees"
    assert "data-symmetric-mark" not in client.get(f"{path}?symmetric_preview=plain").text
    assert "data-symmetric-mark" in client.get(f"{path}?symmetric_preview=marked").text
    assert "data-symmetric-mark" not in client.get(f"{path}?symmetric_preview=other").text


def test_the_home_toggle_is_inert(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-home")
    body = client.get(f"/operator/sessions/{review_session.public_id}?editing=1").text
    group = body[body.find('id="config-symmetric-review"'):]
    group = group[: group.find("</div>\n        </div>")]
    assert "Symmetric review" in group
    assert "name=" not in group.split("data-edit-only", 1)[1]
