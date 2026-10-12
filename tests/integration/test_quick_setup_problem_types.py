"""Quick Setup names a refused roster file's kinds of problem.

The author, 2026-10-12: the slot's banner said only "Could not import
reviewers. Open the Reviewers Setup page for per-row error details." It
now lists what went wrong, by type and with how many rows have it, but
never which row: that is the Setup page's job. Each row-level issue the
roster parsers raise carries a row-free ``problem``
(``app/schemas/validation.py``) for this.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession
from app.schemas.validation import Severity, ValidationIssue
from app.services import csv_imports
from app.services import relationships as relationships_service
from app.web.views import roster_problem_details


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


def _details(location: str) -> list[str]:
    return parse_qs(urlsplit(location).query).get("quick_setup_detail", [])


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
        f"/operator/sessions/{rs.id}/quick-setup/reviewers",
        files={"file": ("r.csv", BAD_REVIEWERS, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert _details(location) == [
        "ReviewerEmail is blank (2 rows)",
        "ReviewerEmail is not a valid email address (1 row)",
        "Status is not active or inactive (1 row)",
    ]
    body = client.get(location).text
    assert (
        "Could not import reviewers. The file has these problems; the "
        "Reviewers Setup page shows which rows:"
    ) in body
    assert "<li>ReviewerEmail is blank (2 rows)</li>" in body
    # The problem, never the row or the value.
    assert "not-an-email" not in body and "Row 3" not in body


def test_a_file_level_problem_reads_as_itself(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-column")
    response = client.post(
        f"/operator/sessions/{rs.id}/quick-setup/reviewers",
        files={"file": ("r.csv", b"ReviewerName,Wrong\nAnn,x\n", "text/csv")},
        follow_redirects=False,
    )
    assert _details(response.headers["location"]) == [
        "Missing required column: ReviewerEmail"
    ]


def test_the_submit_all_form_carries_the_problems_too(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-submit-all")
    response = client.post(
        f"/operator/sessions/{rs.id}/quick-setup/submit-all",
        files={"reviewers_file": ("r.csv", BAD_REVIEWERS, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "ReviewerEmail is blank (2 rows)" in _details(
        response.headers["location"]
    )


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
        f"/operator/sessions/{rs.id}/quick-setup/{kind}",
        files={"file": ("x.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert _details(response.headers["location"]) == [line]


def test_a_name_another_roster_holds_is_named_without_the_email(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-cross")
    db.add(Reviewee(session_id=rs.id, name="Ann", email_or_identifier="ann@example.org"))
    db.commit()
    response = client.post(
        f"/operator/sessions/{rs.id}/quick-setup/reviewers",
        files={"file": ("r.csv", b"ReviewerName,ReviewerEmail\nAnnie,ann@example.org\n", "text/csv")},
        follow_redirects=False,
    )
    assert _details(response.headers["location"]) == [
        "ReviewerEmail is already used under a different name in another "
        "roster (1 row)"
    ]


def test_the_new_session_page_carries_the_problems_too(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "qsp-new", "description": ""},
        files={"reviewers_file": ("r.csv", BAD_REVIEWERS, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "ReviewerEmail is blank (2 rows)" in _details(
        response.headers["location"]
    )


def test_a_link_with_no_lines_keeps_the_old_sentence(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "qsp-old-link")
    body = client.get(
        f"/operator/sessions/{rs.id}"
        "?quick_setup_error=reviewers&quick_setup_reason=parse"
    ).text
    assert (
        "Could not import reviewers. Open the Reviewers Setup page for "
        "per-row error details."
    ) in body


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
        f"/operator/sessions/{rs.id}/quick-setup/relationships",
        files={"file": ("rel.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert _details(response.headers["location"]) == [
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
