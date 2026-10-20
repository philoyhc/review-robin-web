"""Quick Setup names a refused roster file's kinds of problem.

The author, 2026-10-12: the slot's banner said only "Could not import
reviewers. Open the Reviewers Setup page for per-row error details." It
now lists what went wrong, by type and with how many rows have it, but
never which row. The Setup pages' upload cards show the same lines
(``guide/quick_setup_update.md`` Item 3). Each row-level issue the
roster parsers raise carries a row-free ``problem``
(``app/schemas/validation.py``) for this.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession
from app.schemas.validation import Severity, ValidationIssue
from app.services import csv_imports
from app.services import relationships as relationships_service
from app.web.views import roster_problem_details

from ._quick_setup_refusal import refusal


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


def _details(response) -> list[str]:
    """The lines under the refused slot's banner, on the 422 re-render
    (findings O7)."""
    return refusal(response).details


BAD_REVIEWERS = (
    b"ReviewerName,ReviewerEmail,Status\n"
    b"Ann,,active\n"
    b"Bob,,active\n"
    b"Cy,not-an-email,active\n"
    b"Di,di@example.org,maybe\n"
)


def test_a_refused_roster_names_each_kind_of_problem_with_a_count(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-reviewers")
    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/reviewers",
        files={"file": ("r.csv", BAD_REVIEWERS, "text/csv")},
        follow_redirects=False,
    )
    assert _details(response) == [
        "ReviewerEmail is blank (2 rows)",
        "ReviewerEmail is not a valid email address (1 row)",
        "Status is not active or inactive (1 row)",
    ]
    body = response.text
    assert "Could not import reviewers. The file has these problems:" in body
    # It points at no Setup page: a refused file never reaches one
    # (quick_setup_update Item 3).
    assert "shows which rows" not in body
    assert "<li>ReviewerEmail is blank (2 rows)</li>" in body
    # The problem, never the row or the value.
    assert "not-an-email" not in body and "Row 3" not in body


def test_a_file_level_problem_reads_as_itself(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-column")
    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/reviewers",
        files={"file": ("r.csv", b"ReviewerName,Wrong\nAnn,x\n", "text/csv")},
        follow_redirects=False,
    )
    assert _details(response) == [
        "Missing required column: ReviewerEmail"
    ]


def test_the_submit_all_form_carries_the_problems_too(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-submit-all")
    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/submit-all",
        files={"reviewers_file": ("r.csv", BAD_REVIEWERS, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert "ReviewerEmail is blank (2 rows)" in _details(response)


@pytest.mark.parametrize(
    ("kind", "content", "line"),
    [
        (
            "reviewees",
            b"RevieweeName,RevieweeEmail\n,a@example.org\n,b@example.org\n",
            "RevieweeName is blank (2 rows)",
        ),
        (
            "observers",
            b"ObserverEmail,ObserverName,CohortRule\na@example.org,A,{nope\n",
            "CohortRule is not valid JSON (1 row)",
        ),
    ],
)
def test_the_other_roster_slots_name_their_problems(
    client: TestClient, db: Session, kind: str, content: bytes, line: str
) -> None:
    rs = _session(client, db, f"qsp-{kind}")
    rs.observers_enabled = True
    db.commit()
    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/{kind}",
        files={"file": ("x.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert _details(response) == [line]


def test_a_name_another_roster_holds_is_named_without_the_email(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-cross")
    db.add(Reviewee(session_id=rs.id, name="Ann", email_or_identifier="ann@example.org"))
    db.commit()
    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/reviewers",
        files={"file": ("r.csv", b"ReviewerName,ReviewerEmail\nAnnie,ann@example.org\n", "text/csv")},
        follow_redirects=False,
    )
    assert _details(response) == [
        "ReviewerEmail is already used under a different name in another "
        "roster (1 row)"
    ]


def test_the_new_session_page_says_the_file_was_refused_without_its_lines(
    client: TestClient, db: Session
) -> None:
    """Create keeps its redirect, since the session is committed, so the
    file's lines are not carried: a fixed code says which file was
    refused, and uploading it again in Quick Setup shows why (O7)."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "qsp-new", "description": ""},
        files={"reviewers_file": ("r.csv", BAD_REVIEWERS, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    # No slot fragment (19X Item 7): Home's banner script lands it.
    assert location.endswith(
        "?quick_setup_error=reviewers&quick_setup_reason=refused"
    )
    body = client.get(location).text
    assert (
        '<p class="banner-lead">The reviewers file was refused, so none of '
        "the files uploaded with the new session were saved. Upload them "
        "again in Quick Setup to see why.</p>"
    ) in body
    assert "ReviewerEmail is blank" not in body


@pytest.mark.parametrize("reason", ["parse", "lifecycle", "needs_confirm", "x"])
def test_a_link_with_any_other_code_shows_nothing(
    client: TestClient, db: Session, reason: str
) -> None:
    """Only the Create page's ``refused`` code reaches Home by URL; an
    older link's reason, or one a link makes up, shows no banner, and
    ``quick_setup_detail`` puts nothing on the page (findings O7)."""
    rs = _session(client, db, "qsp-old-link-" + reason.replace("_", "-"))
    body = client.get(
        f"/operator/sessions/{rs.public_id}",
        params=[
            ("quick_setup_error", "reviewers"),
            ("quick_setup_reason", reason),
            ("quick_setup_detail", "qsdmark anything"),
        ],
    ).text
    assert 'data-quick-setup-reason="' not in body
    assert "Could not import reviewers" not in body
    assert "qsdmark" not in body


def test_a_refused_code_for_an_unknown_slot_shows_nothing(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-unknown-slot")
    body = client.get(
        f"/operator/sessions/{rs.public_id}"
        "?quick_setup_error=elsewhere&quick_setup_reason=refused"
    ).text
    assert 'data-quick-setup-reason="' not in body
    assert "was refused" not in body


def test_relationships_name_an_unknown_reviewer(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-rel")
    db.add(Reviewer(session_id=rs.id, name="Ann", email="ann@example.org"))
    db.add(Reviewee(session_id=rs.id, name="Bo", email_or_identifier="bo@example.org"))
    db.commit()
    csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"ghost@example.org,bo@example.org\n"
        b"ann@example.org,bo@example.org\n"
        b"ann@example.org,bo@example.org\n"
    )
    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/relationships",
        files={"file": ("rel.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert _details(response) == [
        "ReviewerEmail is not on the Reviewers roster "
        "(import reviewers first) (1 row)",
        "A reviewer–reviewee pair appears on more than one row (1 row)",
    ]


# ── Every row-level issue says what kind it is ───────────────────────


_REVIEWERS = (
    b"ReviewerName,ReviewerEmail,Status,ReviewerTag1\n"
    b",a@example.org,,\n"
    b"B,,,\n"
    b"C,bad,,\n"
    b"D,d@example.org,odd,\n"
    b"E,e@example.org,,x\\,y\n"
    b"F,f@example.org,,\n"
    b"F,f@example.org,,\n"
    b"G,f@example.org,,\n"
    b"H,h@example.org,," + b"t" * 300 + b"\n"
)
_REVIEWEES = (
    b"RevieweeName,RevieweeEmail,Status\n"
    b",a@example.org,\n"
    b"B,,\n"
    b"C,c@example.org,odd\n"
    b"D,d@example.org,\n"
    b"D,d@example.org,\n"
    b"E,d@example.org,\n"
)
_OBSERVERS = (
    b"ObserverEmail,ObserverName,Status,CohortRule\n"
    b",A,,\n"
    b"bad,B,,\n"
    b"c@example.org,C,odd,\n"
    b"d@example.org,D,,\n"
    b"d@example.org,D,,\n"
    b"e@example.org,E,,{not json\n"
    b'f@example.org,F,,"{""combinator"": ""XOR"", ""rules"": []}"\n'
)


@pytest.mark.parametrize(
    ("parse", "content"),
    [
        (csv_imports.parse_reviewer_csv, _REVIEWERS),
        (csv_imports.parse_reviewee_csv, _REVIEWEES),
        (csv_imports.parse_observer_csv, _OBSERVERS),
    ],
)
def test_every_row_issue_a_roster_parser_raises_has_a_problem(
    parse, content: bytes
) -> None:
    issues = [i for i in parse(content).issues if i.row_number is not None]
    assert len(issues) >= 5, [i.message for i in issues]
    assert all(i.problem for i in issues), [
        i.message for i in issues if not i.problem
    ]
    _assert_row_and_value_free(issues)


def test_every_relationship_row_issue_has_a_problem() -> None:
    from types import SimpleNamespace

    reviewers = [SimpleNamespace(id=1, email="a@example.org")]
    reviewees = [SimpleNamespace(id=2, email_or_identifier="b@example.org")]
    content = (
        b"ReviewerEmail,RevieweeEmail,Status\n"
        b",b@example.org,\n"
        b"a@example.org,,\n"
        b"x@example.org,b@example.org,\n"
        b"a@example.org,y@example.org,\n"
        b"a@example.org,b@example.org,odd\n"
        b"a@example.org,b@example.org,\n"
        b"a@example.org,b@example.org,\n"
    )
    result = relationships_service.parse_relationship_csv(
        content, reviewers=reviewers, reviewees=reviewees
    )
    issues = [i for i in result.issues if i.row_number is not None]
    assert len(issues) == 6, [i.message for i in issues]
    assert all(i.problem for i in issues)
    _assert_row_and_value_free(issues)


def _assert_row_and_value_free(issues: list[ValidationIssue]) -> None:
    """No problem names a row or quotes a cell: no ``row``-and-number,
    no quote marks, no address, none of the fixtures' bad values."""
    import re

    for issue in issues:
        text = issue.problem or ""
        assert not re.search(r"\brow \d", text, re.I), text
        assert "'" not in text and "@" not in text, text
        assert not re.search(r"\b(bad|odd|xor)\b", text, re.I), text


def test_problem_details_fall_back_and_cap() -> None:
    def row(problem: str | None, field: str = "X") -> ValidationIssue:
        return ValidationIssue(
            severity=Severity.error, source="s", row_number=1,
            field=field, message="m", problem=problem,
        )

    warning = ValidationIssue(
        severity=Severity.warning, source="s", row_number=1, message="w",
        problem="ignored",
    )
    assert roster_problem_details([row(None, "Tag")]) == ["Tag has a problem (1 row)"]
    assert roster_problem_details([warning]) == []
    many = [row(f"p{n}") for n in range(7)]
    assert roster_problem_details(many) == [
        "p0 (1 row)", "p1 (1 row)", "p2 (1 row)", "p3 (1 row)", "p4 (1 row)",
        "…and 2 more.",
    ]
