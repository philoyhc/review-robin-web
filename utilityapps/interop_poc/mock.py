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


# No roster tags (author, 2026-11-16): a linked session assigns by its
# relationships, whose tag carries the evaluator's source (the panel).
def reviewers_csv(people: tuple[Reviewer, ...]) -> str:
    return _csv(["ReviewerName", "ReviewerEmail"], [[p.name, p.email] for p in people])


def reviewees_csv(applications: tuple[Application, ...] = APPLICATIONS) -> str:
    return _csv(
        ["RevieweeName", "RevieweeEmail", "ProfileLink"],
        [[a.applicant, a.id, a.profile_link] for a in applications],
    )


def relationships_csv(
    people: tuple[Reviewer, ...], applications: tuple[Application, ...] = APPLICATIONS
) -> str:
    """Every reviewer with every application, the pair tagged with the
    reviewer's panel: the relationship the fixed rule assigns by
    (``pair_context.tag1 IS FILLED``, segment 23F rung 7a)."""
    return _csv(
        ["ReviewerEmail", "RevieweeEmail", f"PairContextTag1.{PAIR_LABEL}"],
        [[p.email, a.id, p.panel] for p in people for a in applications],
    )


#: The relationship tag's friendly label (author, 2026-11-16), set by the
#: header's ``.Label`` suffix (`spec/csv_contracts.md`).
PAIR_LABEL = "Apply-Desk-Link"

#: The timezone the mock sends (author, 2026-11-16: a zone unlike the
#: host's, so a test shows the setting arrived).
TIMEZONE = "Asia/Singapore"


#: The review's instrument (segment 23D), in Review Robin's Settings CSV
#: (`spec/csv_contracts.md` §3.3): a 1-5 score keyed ``score`` and a comment
#: keyed ``comment``, the keys `results.csv` reports answers under, and
#: its assignment-rule links set, so the draft arrives set up. No release
#: date: the draft releases nothing until its operator does.
INSTRUMENT = "Gate 1: Panel review"
#: The gate's description, which the instrument's description follows.
GATE_DESCRIPTION = "Score each application and say why, for the panel's shortlist."
#: The review window, in the mock's timezone.
START = "2027-01-11T09:00:00+08:00"
END = "2027-01-25T17:00:00+08:00"
#: The re-send's changes: a later End, a renamed gate and fuller help.
RESEND_END = "2027-01-29T17:00:00+08:00"
RESEND_INSTRUMENT = "Gate 1: Panel review (extended)"
#: The tags every Apply Desk session carries (author, 2026-11-16): the
#: application and the year its exercise starts.
TAGS = ("applydesk", START[:4])

_FIELDS = (
    ("score", "Score", "1-to-5int", "Integer", ("1", "5", "1"), "1 is weak, 5 is outstanding."),
    ("comment", "Comment", "text", "String", None, "A sentence or two the panel can read."),
)


def _session_rows(description: str, end: str, tags: tuple[str, ...]) -> list[list[str]]:
    """Every session field a linked application owns
    (``LinkedProfile.owned_settings``), filled."""
    rows = [
        ["session.description", description, "string"],
        ["session.help_contact", "interop-poc@example.edu", "string"],
        ["session.display_timezone", TIMEZONE, "string"],
        ["session.scheduled_activate_at", START, "datetime"],
        ["session.deadline", end, "datetime"],
    ]
    rows += [[f"session_tags[{n}].tag", tag, "string"] for n, tag in enumerate(tags, start=1)]
    return rows


def _instrument_rows(name: str, help_suffix: str = "") -> list[list[str]]:
    """The gate's instrument: its name and description, and its response
    fields with their help text, in the application's order."""
    rows = [
        ["instruments[1].name", name, "string"],
        ["instruments[1].description", GATE_DESCRIPTION, "string"],
    ]
    for n, (key, label, response_type, data_type, bounds, help_text) in enumerate(_FIELDS, start=1):
        at = f"instruments[1].response_fields[{n}]"
        rows += [
            [f"{at}.field_key", key, "string"],
            [f"{at}.label", label, "string"],
            [f"{at}.response_type", response_type, "string"],
            [f"{at}.data_type", data_type, "string"],
            [f"{at}.visible", "true", "boolean"],
            [f"{at}.help_text", help_text + help_suffix, "string"],
            [f"{at}.help_text_visible", "true", "boolean"],
        ]
        if bounds:
            rows += [[f"{at}.{k}", v, "decimal"] for k, v in zip(("min", "max", "step"), bounds)]
    return rows


def settings_csv() -> str:
    """The create's Settings CSV: every session field and instrument part
    the application owns (author, 2026-11-16: the proof of concept
    populates all of them), so the draft arrives filled."""
    rows = _session_rows("Mock scholarship applications, panel review.", END, TAGS)
    return _csv(["field", "value", "data_type"], rows + _instrument_rows(INSTRUMENT))


def bundle(people: tuple[Reviewer, ...]) -> dict[str, object]:
    """The handoff bundle without its per-click parts: the page's script
    adds a fresh ``transfer_id`` and a session code (`spec/handoffs.md`)."""
    return {
        "protocol": "cordware.csv-handoff",
        "protocol_version": 1,
        "operation": "reviewrobin.create_draft_session",
        "source_app": "utilities",
        "session_suggestion": {"name": EXERCISE},
        "files": {
            "reviewers": reviewers_csv(people),
            "reviewees": reviewees_csv(),
            "relationships": relationships_csv(people),
            "settings": settings_csv(),
        },
    }


#: What a re-send changes (segment 23F rung 4): the draft as Apply Desk
#: would update it after Send. One reviewer and one application are
#: dropped, and the session settings Apply Desk owns are re-sent.
RESEND_DROPS_REVIEWER = "cai.reviewer@example.edu"
RESEND_DROPS_APPLICATION = "SCH27-0006"


def resend_settings_csv() -> str:
    """The owned rows again, changed as an update would change them: the
    description, a later End, the gate renamed and the help text fuller;
    the tags stay Apply Desk's two."""
    rows = _session_rows("Updated by a re-send from Utilities", RESEND_END, TAGS)
    return _csv(
        ["field", "value", "data_type"],
        rows + _instrument_rows(RESEND_INSTRUMENT, " (Updated by a re-send.)"),
    )


def resend_bundle(people: tuple[Reviewer, ...]) -> dict[str, object]:
    """The re-send bundle without its per-click ``transfer_id``: the page's
    script posts it to the update route named by the creating transfer
    (`spec/handoffs.md` §6a)."""
    kept = tuple(p for p in people if p.email != RESEND_DROPS_REVIEWER)
    applications = tuple(a for a in APPLICATIONS if a.id != RESEND_DROPS_APPLICATION)
    return {
        "protocol": "cordware.csv-handoff",
        "protocol_version": 1,
        "operation": "reviewrobin.update_draft_session",
        "source_app": "utilities",
        "files": {
            "reviewers": reviewers_csv(kept),
            "reviewees": reviewees_csv(applications),
            "relationships": relationships_csv(kept, applications),
            "settings": resend_settings_csv(),
        },
    }
