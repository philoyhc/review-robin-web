"""The Setup pages' upload cards report a refused file as Quick Setup does.

``guide/quick_setup_update.md`` Item 3 (author, 2026-10-13): the
Reviewers, Reviewees, Relationships and Observers upload cards list the
kinds of problem with how many rows have each, from the helper Quick
Setup's banner reads, and never the rows. Before this the card listed one
line per row ("Row 2: ``ReviewerEmail`` ReviewerEmail is required"), so a
file with a hundred bad rows printed a hundred lines.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.schemas.validation import Severity, ValidationIssue
from app.web.views import problem_kinds, upload_problems


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _upload(client: TestClient, rs: ReviewSession, kind: str, body: str):
    return client.post(
        f"/operator/sessions/{rs.id}/{kind}/import",
        files={"file": (f"{kind}.csv", body.encode(), "text/csv")},
        follow_redirects=False,
    )


def _banner(html: str) -> str:
    match = re.search(
        r'id="upload-problems-banner" data-upload-problems>(.*?)'
        r'<div class="banner-actions">',
        html,
        re.S,
    )
    assert match, "no upload-problems banner on the page"
    return match.group(1)


@pytest.mark.parametrize(
    ("kind", "body", "message", "lines"),
    [
        (
            "reviewers",
            "ReviewerName,ReviewerEmail,Status\n"
            "Al,al@example.edu,active\nBo,,active\nCy,,active\n"
            "Di,di@example.edu,maybe\n",
            "Could not import reviewers. The file has these problems:",
            [
                "ReviewerEmail is blank (2 rows)",
                "Status is not active or inactive (1 row)",
            ],
        ),
        (
            "reviewees",
            "RevieweeName,RevieweeEmail\nAl,\nBo,\n",
            "Could not import reviewees. The file has these problems:",
            ["RevieweeEmail is blank (2 rows)"],
        ),
        (
            "observers",
            "ObserverName,ObserverEmail\nAl,\n",
            "Could not import observers. The file has these problems:",
            ["ObserverEmail is blank (1 row)"],
        ),
        (
            "relationships",
            "ReviewerEmail,RevieweeEmail\nghost@example.edu,carol@example.edu\n",
            "Could not import relationships. The file has these problems:",
            # One problem per row: the parser stops at the first unknown
            # email on a row.
            [
                "ReviewerEmail is not on the Reviewers roster "
                "(import reviewers first) (1 row)",
            ],
        ),
    ],
)
def test_each_upload_card_lists_kinds_of_problem_with_counts(
    client: TestClient,
    db: Session,
    kind: str,
    body: str,
    message: str,
    lines: list[str],
) -> None:
    rs = _session(client, db, f"up-{kind}")
    # The Relationships and Observers pages answer only while their tab
    # is on.
    rs.relationships_enabled = True
    rs.observers_enabled = True
    db.commit()

    response = _upload(client, rs, kind, body)

    assert response.status_code == 400
    banner = _banner(response.text)
    assert message in banner
    assert re.findall(r"<li>(.*?)</li>", banner) == lines
    # The kind of problem, never the row or the value.
    assert "Row " not in banner and "@" not in banner
    # The card no longer carries Validate's issue list.
    assert '<ul class="issue-list">' not in response.text
    # Spec ui_elements §5a: it scrolls into view, and Cancel returns to
    # the page with the upload card open and no file.
    assert 'class="banner banner-error banner-scroll-target"' in response.text
    assert (
        f'href="/operator/sessions/{rs.id}/{kind}?unlocked=1#upload-csv">Cancel</a>'
    ) in response.text


def test_a_hundred_bad_rows_make_one_line(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "up-hundred")
    body = "ReviewerName,ReviewerEmail\n" + "".join(
        f"R{i},\n" for i in range(100)
    )

    banner = _banner(_upload(client, rs, "reviewers", body).text)

    assert re.findall(r"<li>(.*?)</li>", banner) == [
        "ReviewerEmail is blank (100 rows)"
    ]


def test_a_missing_column_reads_as_itself(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "up-missing")

    banner = _banner(
        _upload(client, rs, "reviewers", "ReviewerName,Email\nAl,a@x.edu\n").text
    )

    assert re.findall(r"<li>(.*?)</li>", banner) == [
        "Missing required column: ReviewerEmail"
    ]


def test_the_replace_confirmation_state_has_no_banner(
    client: TestClient, db: Session
) -> None:
    """A clean file onto a populated roster, without the tick: a 400 with
    nothing to report about the file."""
    rs = _session(client, db, "up-confirm")
    first = _upload(client, rs, "reviewers", "ReviewerName,ReviewerEmail\nAl,al@x.edu\n")
    assert first.status_code == 303

    response = _upload(
        client, rs, "reviewers", "ReviewerName,ReviewerEmail\nBo,bo@x.edu\n"
    )

    assert response.status_code == 400
    assert "data-upload-problems" not in response.text


def test_a_clean_page_has_no_banner(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "up-clean")

    page = client.get(f"/operator/sessions/{rs.id}/reviewers").text

    assert "data-upload-problems" not in page


def test_upload_problems_is_none_without_a_blocking_issue() -> None:
    warning = ValidationIssue(
        severity=Severity.warning,
        source="reviewers",
        row_number=2,
        field="ReviewerTag1",
        message="w",
        problem="ReviewerTag1 is odd",
    )

    assert upload_problems("reviewers", None) is None
    assert upload_problems("reviewers", [warning]) is None
    assert problem_kinds([warning]) == []
