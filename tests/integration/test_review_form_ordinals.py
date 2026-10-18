"""19V Item 2: the review form names answers by the row's ordinal on the
page, never by assignment ID, and refuses a post made against a page
whose rows changed since it rendered
(``guide/segment_19V_public_id_revamp.md``)."""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Response, ReviewSession

from ._answer_form import answer_form
from ._display_field_helpers import _activate, _generate_full_matrix

_ANSWER_NAME = re.compile(r'name="response\[([0-9]+)\]\[([^\]]+)\]"')
_DIGEST = re.compile(r'name="page_digest" value="([0-9a-f]+)"')


def _session_alice_reviews(
    db: Session, client: TestClient, *, code: str = "ordinals"
) -> ReviewSession:
    """Alice runs the session and reviews three reviewees on one page."""
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"),
        (
            "reviewees",
            b"RevieweeName,RevieweeEmail\n"
            b"Carol,carol@example.edu\nDan,dan@example.edu\nEve,eve@example.edu\n",
        ),
    ):
        response = client.post(
            f"/operator/sessions/{session.public_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
    _generate_full_matrix(client, db, session.id)
    _activate(client, db, session.id)
    db.refresh(session)
    return session


def _assignments(db: Session, session: ReviewSession) -> list[Assignment]:
    return list(
        db.execute(
            select(Assignment)
            .where(Assignment.session_id == session.id)
            .order_by(Assignment.id)
        ).scalars()
    )


def _rating(db: Session, assignment: Assignment) -> str | None:
    db.expire_all()
    for row in db.execute(
        select(Response).where(Response.assignment_id == assignment.id)
    ).scalars():
        if row.response_field.field_key == "rating":
            return row.value
    return None


def test_answers_are_named_by_ordinal_not_assignment_id(
    db: Session, client: TestClient
) -> None:
    # Another session's assignments first, so this page's IDs are not 1-3.
    _session_alice_reviews(db, client, code="ordinals-other")
    session = _session_alice_reviews(db, client)
    assert min(a.id for a in _assignments(db, session)) > 3

    html = client.get(f"/me/sessions/{session.public_id}/1").text

    assert {int(n) for n, _key in _ANSWER_NAME.findall(html)} == {1, 2, 3}
    assert _DIGEST.search(html)


def test_a_column_sort_leaves_the_ordinals_on_the_same_rows(
    db: Session, client: TestClient
) -> None:
    """A sort reorders the rows; each row keeps its ordinal, because the
    ordinal follows assignment-ID order, not display order."""
    session = _session_alice_reviews(db, client)
    instrument_id = _assignments(db, session)[0].instrument_id

    def names_by_reviewee(cookie_dir: str | None) -> tuple[list[str], dict[str, str]]:
        if cookie_dir:
            client.cookies.set(
                f"rrw-sort-rs-{session.public_id}-{instrument_id}",
                quote(json.dumps([{"key": "reviewee.name", "dir": cookie_dir}])),
            )
        html = client.get(f"/me/sessions/{session.public_id}/1").text
        client.cookies.clear()
        found: dict[str, str] = {}
        for name in ("Carol", "Dan", "Eve"):
            row = html[html.index(f">{name}<") :]
            found[name] = _ANSWER_NAME.search(row).group(1)
        order = sorted(found, key=lambda name: html.index(f">{name}<"))
        return order, found

    (order, unsorted), (sorted_order, descending) = (
        names_by_reviewee(None),
        names_by_reviewee("desc"),
    )
    assert sorted_order == ["Eve", "Dan", "Carol"] != order
    assert unsorted == descending


def test_a_save_lands_on_the_row_its_ordinal_names(
    db: Session, client: TestClient
) -> None:
    session = _session_alice_reviews(db, client)
    first, second, third = _assignments(db, session)

    response = client.post(
        f"/me/sessions/{session.public_id}/1/save",
        data=answer_form(db, {f"response[{second.id}][rating]": "4"}),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert _rating(db, second) == "4"
    assert _rating(db, first) is None
    assert _rating(db, third) is None


def test_an_ordinal_the_page_does_not_have_is_ignored(
    db: Session, client: TestClient
) -> None:
    session = _session_alice_reviews(db, client)
    page = client.get(f"/me/sessions/{session.public_id}/1").text
    digest = _DIGEST.search(page).group(1)

    response = client.post(
        f"/me/sessions/{session.public_id}/1/save",
        data={"response[4][rating]": "5", "page_digest": digest},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert all(_rating(db, a) is None for a in _assignments(db, session))


def test_a_post_against_a_changed_page_is_refused_and_saves_nothing(
    db: Session, client: TestClient
) -> None:
    """Between render and post a row leaves the page, so ordinal 2 would
    now name the third row. The post is refused rather than mapped."""
    session = _session_alice_reviews(db, client)
    first, second, third = _assignments(db, session)
    stale = answer_form(db, {f"response[{second.id}][rating]": "4"})
    first.include = False
    db.commit()

    response = client.post(
        f"/me/sessions/{session.public_id}/1/save", data=stale, follow_redirects=False
    )

    assert response.status_code == 409
    assert "This page changed after you opened it" in response.text
    # The typed value comes back to copy, naming no row.
    assert ">4<" in response.text
    assert _rating(db, second) is None
    assert _rating(db, third) is None


def test_answers_without_a_digest_are_refused(
    db: Session, client: TestClient
) -> None:
    session = _session_alice_reviews(db, client)
    second = _assignments(db, session)[1]

    for path in (
        f"/me/sessions/{session.public_id}/1/save",
        f"/me/sessions/{session.public_id}/submit?page=1",
    ):
        response = client.post(
            path, data={"response[2][rating]": "4"}, follow_redirects=False
        )
        assert response.status_code == 409, path
    assert _rating(db, second) is None


def test_a_refused_stale_form_lists_its_answers_bare(
    db: Session, client: TestClient
) -> None:
    """Past the deadline a Save is refused (403) and its typed answers come
    back to copy. A form whose page changed since it rendered lists them
    bare, not under the rows its ordinals name now."""
    from datetime import datetime, timedelta, timezone

    session = _session_alice_reviews(db, client)
    first, second, _third = _assignments(db, session)
    stale = answer_form(db, {f"response[{second.id}][rating]": "4"})
    first.include = False
    session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    response = client.post(
        f"/me/sessions/{session.public_id}/1/save", data=stale, follow_redirects=False
    )

    assert response.status_code == 403
    listed = response.text[response.text.index("data-rs-unsaved") :]
    listed = listed[: listed.index("</ul>")]
    assert ">4<" in listed or "4</" in listed
    # Ordinal 2 now names Eve; the stale form meant Dan. Neither is named.
    assert "Dan" not in listed and "Eve" not in listed
