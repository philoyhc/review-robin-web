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
    instrument_seq = _assignments(db, session)[0].instrument.session_seq

    def names_by_reviewee(cookie_dir: str | None) -> tuple[list[str], dict[str, str]]:
        if cookie_dir:
            client.cookies.set(
                f"rrw-sort-rs-{session.public_id}-{instrument_seq}",
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


def test_a_group_page_posts_back_the_ordinals_it_rendered(
    db: Session, make_client
) -> None:
    """A group instrument renders one row for its members, so the page's
    ordinals have a gap (1 and 3 render; 2 is the group's other member).
    Posting the rendered names back lands each answer on its row, the
    group's on every member."""
    from app.auth.identity import AuthenticatedUser
    from app.db.models import Reviewee, Reviewer, SessionOperator, User
    from app.services import instruments as instruments_service

    op = User(email="op@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    session = ReviewSession(name="G", code="ordinals-group", created_by_user_id=op.id)
    db.add(session)
    db.flush()
    db.add(SessionOperator(session_id=session.id, user_id=op.id, role="owner"))
    group = instruments_service.create_instrument(
        db,
        review_session=session,
        actor=op,
        group_kind=instruments_service.GROUP_KIND_SENTINEL,
    )
    solo = instruments_service.create_instrument(db, review_session=session, actor=op)
    reviewer = Reviewer(session_id=session.id, name="Rae", email="rae@example.edu")
    carol, dan = (
        Reviewee(session_id=session.id, name=n, email_or_identifier=f"{n.lower()}@example.edu")
        for n in ("Carol", "Dan")
    )
    db.add_all([reviewer, carol, dan])
    db.flush()
    in_group = [
        Assignment(session_id=session.id, reviewer_id=reviewer.id, reviewee_id=r.id, instrument_id=group.id)
        for r in (carol, dan)
    ]
    db.add_all(in_group)
    db.flush()
    alone = Assignment(session_id=session.id, reviewer_id=reviewer.id, reviewee_id=carol.id, instrument_id=solo.id)
    db.add(alone)
    session.status = "ready"
    db.commit()
    rae = make_client(
        AuthenticatedUser(principal_id="rae", email="rae@example.edu", name="Rae", provider="aad")
    )

    html = rae.get(f"/me/sessions/{session.public_id}/1").text
    rendered = {(int(n), key) for n, key in _ANSWER_NAME.findall(html)}
    assert {n for n, _key in rendered} == {1, 3}
    form = {f"response[{n}][rating]": str(n) for n, key in rendered if key == "rating"}
    form["page_digest"] = _DIGEST.search(html).group(1)

    response = rae.post(
        f"/me/sessions/{session.public_id}/1/save", data=form, follow_redirects=False
    )

    assert response.status_code == 303, response.text
    assert [_rating(db, a) for a in in_group] == ["1", "1"]
    assert _rating(db, alone) == "3"


def test_the_digest_is_keyed_by_a_secret_the_page_never_shows(
    db: Session, client: TestClient
) -> None:
    """The digest covers the page's assignment IDs, so its key must be a
    secret: the session's ``form_key``, which no page renders. Without it
    nobody can test guesses of the IDs, or their count, against the
    digest."""
    from types import SimpleNamespace

    from app.services.responses import page_digest

    session = _session_alice_reviews(db, client)
    html = client.get(f"/me/sessions/{session.public_id}/1").text

    assert len(session.form_key) == 64
    assert session.form_key not in html
    rows = [SimpleNamespace(id=7), SimpleNamespace(id=9)]
    other_key = SimpleNamespace(form_key="0" * 64)
    assert page_digest(session, rows) != page_digest(other_key, rows)
    assert page_digest(session, rows) != page_digest(session, rows[:1])


def test_a_digest_that_is_not_hex_is_a_mismatch_not_an_error(
    db: Session, client: TestClient
) -> None:
    session = _session_alice_reviews(db, client)

    for digest in ("é" * 32, "", "zz", "0" * 64):
        response = client.post(
            f"/me/sessions/{session.public_id}/1/save",
            data={"response[1][rating]": "4", "page_digest": digest},
            follow_redirects=False,
        )
        assert response.status_code == 409, digest


def test_the_service_still_drops_an_excluded_or_foreign_assignment(
    db: Session, client: TestClient
) -> None:
    """The route can no longer post another row's answer, but the write
    service must still refuse one, for the window between reading the
    page and saving under the lock: an excluded or foreign assignment is
    written nowhere, the reviewer's own row still saves. (It is dropped
    twice over, before validation and again at the write, so this pins
    the outcome rather than either filter.)"""
    from app.db.models import Reviewer, User
    from app.schemas.responses import ResponseUpsert
    from app.services import responses as responses_service

    other = _session_alice_reviews(db, client, code="ordinals-foreign")
    session = _session_alice_reviews(db, client)
    excluded, kept, _third = _assignments(db, session)
    foreign = _assignments(db, other)[0]
    excluded.include = False
    db.commit()
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    user = db.execute(select(User).where(User.email == "alice@example.edu")).scalar_one()

    responses_service.save_draft(
        db,
        review_session=session,
        reviewer=reviewer,
        user=user,
        upserts=[
            ResponseUpsert(assignment_id=a.id, field_key="rating", value="5")
            for a in (excluded, kept, foreign)
        ],
        correlation_id="t",
    )

    assert _rating(db, kept) == "5"
    assert _rating(db, excluded) is None
    assert _rating(db, foreign) is None
