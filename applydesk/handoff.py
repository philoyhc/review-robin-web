"""The bundle a gate is sent to Review Robin with (segment AD1M; ruling
24; `spec/handoffs.md` §4): reviewers, reviewees, relationships and a
Settings CSV, built from the gate's pairs and its card on Process. Pure
functions over the sample; AD6 posts these same files.

- **Reviewers**: each paired evaluator by name and email; no tags.
- **Reviewees**: each dossier entered at the gate, keyed by its
  application ID, its ``ProfileLink`` the dossier's page. A blind
  exercise or a confidential gate (rulings 42, 43) sends the Dossier ID as
  the key and the name redacted.
- **Relationships**: each pair, tagged with its evaluator's source
  (``PairContextTag1.Apply-Desk-Link``), never holding a comma.
- **Settings**: the gate's description, the exercise's help contact and
  timezone, the gate's window, the ``applydesk`` tag, and one instrument
  holding the gate's response fields (``stages.fields_of``: a sample gate
  listing none reads one per result, as Process shows it). Never observers, release,
  branching, rules or layouts.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from applydesk import sample_data, stages

PROTOCOL = "cordware.csv-handoff"
SOURCE_APP = "applydesk"
#: The relationship tag's friendly label (author, 2026-11-16), as the
#: Utilities proof of concept sends it.
PAIR_LABEL = "Apply-Desk-Link"
#: Every Apply Desk session's tag (author, 2026-11-16).
TAG = "applydesk"
#: What a confidential reviewee is called (23F, ruling 43).
REDACTED = "Name redacted"
#: The files, in the order the card lists them.
KINDS = ("reviewers", "reviewees", "relationships", "settings")
#: Review Robin's ``data_type`` per Apply Desk field type.
_DATA_TYPES = {"integer": "Integer", "decimal": "Decimal", "list": "List", "string": "String"}


@dataclass(frozen=True)
class Bundle:
    """A gate's four files, CSV text by kind, and its session's suggested
    name and code (ruling 56)."""

    name: str
    code: str
    files: dict[str, str]
    #: How many response fields its instrument holds (``stages.fields_of``).
    fields: int = 0

    def digest(self) -> str:
        """What *Changed since sent* compares: the files and the names."""
        body = json.dumps([self.name, self.code, self.files], sort_keys=True)
        return hashlib.sha256(body.encode()).hexdigest()[:16]

    def rows(self, kind: str) -> int:
        """How many rows a file holds, its header aside."""
        return len(list(csv.reader(io.StringIO(self.files[kind])))) - 1

    def envelope(self) -> dict[str, object]:
        """The create's JSON without its per-click ``transfer_id``."""
        return {
            "protocol": PROTOCOL,
            "protocol_version": 1,
            "operation": "reviewrobin.create_draft_session",
            "source_app": SOURCE_APP,
            "session_suggestion": {"name": self.name, "code": self.code},
            "files": dict(self.files),
        }


def session_name(exercise: sample_data.Exercise, gate: stages.Gate) -> str:
    """Ruling 56: *exercise name — gate label*, at most 255 characters."""
    return f"{exercise.name} — {gate.label or f'Gate {gate.number}'}"[:255]


def session_code(exercise: sample_data.Exercise, gate: stages.Gate) -> str:
    """Ruling 56: *public ID*``-g``*n*."""
    return f"{exercise.public_id}-g{gate.number}"


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def confidential(exercise: sample_data.Exercise, gate: stages.Gate) -> bool:
    """Whether the gate hides who each candidate is (rulings 42, 43)."""
    return exercise.blind or gate.confidential


def reviewee_key(app: sample_data.Application, hidden: bool) -> str:
    """A reviewee's ``RevieweeEmail``: the application ID, or on a
    confidential gate the Dossier ID (ruling 43)."""
    return app.dossier_id if hidden else app.public_id


def reviewers_csv(pairs: tuple[stages.Pair, ...]) -> str:
    """Each paired evaluator once, in the pairs' order; no tags (a linked
    session assigns by its relationships)."""
    seen: dict[str, str] = {}
    for p in pairs:
        if p.email and p.email.casefold() not in seen:
            seen[p.email.casefold()] = p.name
    by_email = {p.email.casefold(): p.email for p in pairs if p.email}
    return _csv(
        ["ReviewerName", "ReviewerEmail"],
        [[name, by_email[key]] for key, name in seen.items()],
    )


def reviewees_csv(
    rows: tuple[stages.Assignment, ...],
    hidden: bool,
    profile_link: Callable[[sample_data.Application], str],
) -> str:
    """Each dossier entered at the gate, its page as ``ProfileLink``."""
    return _csv(
        ["RevieweeName", "RevieweeEmail", "ProfileLink"],
        [
            [
                REDACTED if hidden else a.application.applicant,
                reviewee_key(a.application, hidden),
                profile_link(a.application),
            ]
            for a in rows
        ],
    )


def relationships_csv(pairs: tuple[stages.Pair, ...], hidden: bool) -> str:
    """Each pair, tagged with its evaluator's source; a tag holds no
    comma (`spec/csv_contracts.md` §1, *Tag commas*)."""
    return _csv(
        ["ReviewerEmail", "RevieweeEmail", f"PairContextTag1.{PAIR_LABEL}"],
        [
            [p.email, reviewee_key(p.of.application, hidden), p.source.replace(",", "")]
            for p in pairs
            if p.email
        ],
    )


def _when(at: datetime, zone: str) -> str:
    """An ISO date-time with its offset, in the exercise's timezone."""
    return (at if at.tzinfo else at.replace(tzinfo=ZoneInfo(zone))).isoformat()


def settings_csv(exercise: sample_data.Exercise, gate: stages.Gate) -> str:
    """The session's settings and the gate's instrument, in Review
    Robin's Settings CSV (`spec/csv_contracts.md` §3.3)."""
    zone = sample_data.timezone(exercise)
    rows = [
        ["session.description", gate.description, "string"],
        ["session.help_contact", sample_data.help_contact(exercise), "string"],
        ["session.display_timezone", zone, "string"],
    ]
    plan = stages.plan_of(exercise.public_id)
    stage = next((s for s in plan.stages if gate in s.columns), None)
    when = stages.window(stage, gate) if stage else None
    if when is not None and when.valid:
        rows += [
            ["session.scheduled_activate_at", _when(when.start, zone), "datetime"],
            ["session.deadline", _when(when.end, zone), "datetime"],
        ]
    rows += [
        ["session_tags[1].tag", TAG, "string"],
        ["instruments[1].name", gate.label or f"Gate {gate.number}", "string"],
        ["instruments[1].description", gate.description, "string"],
    ]
    for m, f in enumerate(stages.fields_of(gate), start=1):
        at = f"instruments[1].response_fields[{m}]"
        rows += [
            [f"{at}.field_key", f.key, "string"],
            [f"{at}.label", f.label, "string"],
            [f"{at}.response_type", f.field.type, "string"],
            [f"{at}.data_type", _DATA_TYPES.get(f.field.type, "String"), "string"],
            [f"{at}.visible", "true", "boolean"],
            [f"{at}.required", "true" if f.required else "false", "boolean"],
            [f"{at}.help_text", f.help, "string"],
            [f"{at}.help_text_visible", "true", "boolean"],
        ]
        if f.field.type == "list":
            rows.append([f"{at}.list_csv", f.field.options, "string"])
        else:
            rows += [
                [f"{at}.{k}", v, "decimal"]
                for k, v in (("min", f.field.min), ("max", f.field.max), ("step", f.field.step))
                if v
            ]
    return _csv(["field", "value", "data_type"], rows)


def bundle(
    exercise: sample_data.Exercise,
    gate: stages.Gate,
    profile_link: Callable[[sample_data.Application], str],
) -> Bundle:
    """The gate's bundle as its pairs and card stand in the sample."""
    rows, _ = stages.assignments(exercise.public_id, gate)
    pairs = stages.pairs_of(rows)
    hidden = confidential(exercise, gate)
    return Bundle(
        name=session_name(exercise, gate),
        code=session_code(exercise, gate),
        files={
            "reviewers": reviewers_csv(pairs),
            "reviewees": reviewees_csv(rows, hidden, profile_link),
            "relationships": relationships_csv(pairs, hidden),
            "settings": settings_csv(exercise, gate),
        },
        fields=len(stages.fields_of(gate)),
    )
