"""The mock exercise the proof of concept sends: a scholarship with six
applications and three reviewers, plus the signed-in operator.

Synthetic throughout: the reviewers' `example.edu` addresses resolve to no
one, which is what the proof of concept should show on production. Each
application ID is a reviewee's opaque key (`RevieweeEmail`), so one
applicant could hold two applications (interop spec §13.3 item 1), and
`ProfileLink` holds a placeholder for the ApplyDesk page a reviewer would
read the application on (`.invalid` never resolves).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

EXERCISE = "Mock Scholarship 2027"
PROFILE_ROOT = "https://applydesk.invalid/review/"


@dataclass(frozen=True)
class Reviewer:
    name: str
    email: str
    panel: str


@dataclass(frozen=True)
class Application:
    id: str
    applicant: str
    faculty: str

    @property
    def profile_link(self) -> str:
        return PROFILE_ROOT + self.id


REVIEWERS: tuple[Reviewer, ...] = (
    Reviewer("Ada Reviewer", "ada.reviewer@example.edu", "Panel A"),
    Reviewer("Ben Reviewer", "ben.reviewer@example.edu", "Panel A"),
    Reviewer("Cai Reviewer", "cai.reviewer@example.edu", "Panel B"),
)

APPLICATIONS: tuple[Application, ...] = (
    Application("SCH27-0001", "Dana Applicant", "Science"),
    Application("SCH27-0002", "Eli Applicant", "Engineering"),
    Application("SCH27-0003", "Fay Applicant", "Arts"),
    Application("SCH27-0004", "Gus Applicant", "Science"),
    Application("SCH27-0005", "Hana Applicant", "Business"),
    Application("SCH27-0006", "Ivo Applicant", "Engineering"),
)


def reviewers(operator_name: str, operator_email: str) -> tuple[Reviewer, ...]:
    """The three synthetic reviewers and the signed-in operator, so the
    session has at least one reviewer who can sign in."""
    return (*REVIEWERS, Reviewer(operator_name, operator_email, "Operator"))


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def reviewers_csv(people: tuple[Reviewer, ...]) -> str:
    return _csv(
        ["ReviewerName", "ReviewerEmail", "ReviewerTag1"],
        [[p.name, p.email, p.panel] for p in people],
    )


def reviewees_csv() -> str:
    return _csv(
        ["RevieweeName", "RevieweeEmail", "RevieweeTag1", "ProfileLink"],
        [[a.applicant, a.id, a.faculty, a.profile_link] for a in APPLICATIONS],
    )


def bundle(people: tuple[Reviewer, ...]) -> dict[str, object]:
    """The handoff bundle without its per-click parts: the page's script
    adds a fresh ``transfer_id`` and a session code (`spec/handoffs.md`)."""
    return {
        "protocol": "cordware.csv-handoff",
        "protocol_version": 1,
        "operation": "reviewrobin.create_draft_session",
        "source_app": "utilities",
        "session_suggestion": {"name": EXERCISE},
        "files": {"reviewers": reviewers_csv(people), "reviewees": reviewees_csv()},
    }
