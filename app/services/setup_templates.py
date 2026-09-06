"""Generic setup CSV templates — Segment 19E rung 4.

Four roster templates an operator downloads **before a session exists**,
fills in a spreadsheet, and uploads through Quick Setup. They are served
from the Guide and the lobby first-run card, both of which render with no
session in hand, so nothing here takes a ``ReviewSession``.

**Headers are derived, never authored.** Each template's header is the
``HEADER`` tuple of the extract that already serialises that file, so a
column added to a roster extract appears in the template on the next
request. The importer's own contract tests pin those tuples against the
parsers, which makes them the right thing to copy.

The one authored part is the sample row, and it is authored *per column*:
:data:`SAMPLES` maps a header column to one mock cell, and
:func:`sample_row` looks up every column in the header. A new column with
no sample raises rather than silently emitting a short row, and
``tests/unit/test_setup_templates.py`` asserts the mapping covers every
header exactly.

**The headers carry worked friendly labels**, as
``ReviewerTag1.Tutor`` / ``ReviewerTag2.Group`` and
``PairContextTag1.Interest Group``. Generic templates have no session to
read overrides from, so these are *examples* — but the suffix grammar is
the one thing about roster CSVs an operator cannot guess, and a template
that demonstrates it teaches more than one that avoids it.

The consequence is live, not cosmetic: on import a labelled header
**sets** that slot's override (``field_labels.apply_captured_labels``),
so uploading a template unedited renames the session's tag columns to
``Tutor`` / ``Group`` / ``Interest Group``. That is the intended lesson —
the operator edits the labels to their own vocabulary along with the
rows. The same mechanism in reverse is why a *bare* tag header clears an
override, which is what the Guide card warns about for an operator
re-uploading into a session that already has renames.

Only the nine columns in ``field_label_csv``'s labelable set may carry a
suffix. Observer tags are deliberately outside it, so
``ObserverTag1`` stays bare and Catharine's role travels as the cell
*value*; a suffix there would not split on import and the whole cell
would be read as an unknown column name. :func:`template_header` is
asserted against ``split_header`` in the tests, which is the public check
for exactly that.

The mock rows are a single coherent scenario — **students peer-reviewing
each other within one tutorial group**. ``relationships.csv`` references
the addresses in ``reviewers.csv`` and ``reviewees.csv``, both students
share a tutor and group, and the tutor is the observer, so the four files
import as one working example rather than four unrelated ones.

Plan: ``guide/segment_19E_operator_onboarding.md`` PR ladder rung 4.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from app.services.extracts import stream_csv
from app.services.extracts.observers_extract import HEADER as OBSERVERS_HEADER
from app.services.extracts.relationships_extract import (
    HEADER as RELATIONSHIPS_HEADER,
)
from app.services.extracts.reviewees_extract import HEADER as REVIEWEES_HEADER
from app.services.extracts.reviewers_extract import HEADER as REVIEWERS_HEADER

__all__ = [
    "EXAMPLE_DOMAIN",
    "LABELS",
    "SAMPLES",
    "SetupTemplate",
    "STARTER_TEMPLATES",
    "STARTER_ZIP_NAME",
    "build_starter_zip",
    "sample_row",
    "template_header",
    "template_rows",
]

#: Every address in every template. Already the codebase convention
#: (`guide/segment_19E_operator_onboarding.md` -> Semantics).
EXAMPLE_DOMAIN = "example.edu"

_REVIEWER_EMAIL = f"alex.student@{EXAMPLE_DOMAIN}"
_REVIEWEE_EMAIL = f"sam.student@{EXAMPLE_DOMAIN}"
_OBSERVER_EMAIL = f"catharine.tutor@{EXAMPLE_DOMAIN}"

#: The scenario every sample cell belongs to: two students in tutorial
#: group TW01 peer-reviewing each other, with their tutor observing.
#: Symmetrical by design — both roster rows are students, so an operator
#: reading the set sees that the same person can be reviewer and reviewee.
_TUTOR_NAME = "Catharine Tutor"
_GROUP = "TW01"


@dataclass(frozen=True)
class SetupTemplate:
    """One downloadable template file.

    ``header`` is the extract's own ``HEADER`` tuple, held by reference
    rather than copied — this dataclass never restates a column name.
    """

    key: str
    filename: str
    header: tuple[str, ...]


#: One mock cell per column, across every template. Keyed by column name
#: rather than by file: the roster extracts share column names
#: (``Status``, ``PhotoLink``) and should share their sample, so a single
#: flat mapping is the honest shape. ``ReviewerEmail`` / ``RevieweeEmail``
#: appear in both a roster file and ``relationships.csv``, which is what
#: keeps the four files referring to the same two people.
SAMPLES: dict[str, str] = {
    # Reviewers — a student.
    "ReviewerName": "Alex Student",
    "ReviewerEmail": _REVIEWER_EMAIL,
    "ReviewerTag1": _TUTOR_NAME,
    "ReviewerTag2": _GROUP,
    "ReviewerTag3": "",
    # Reviewees — a second student in the same group, so the pair is a
    # peer review rather than a supervisor reviewing a supervisee.
    "RevieweeName": "Sam Student",
    "RevieweeEmail": _REVIEWEE_EMAIL,
    "RevieweeTag1": _TUTOR_NAME,
    "RevieweeTag2": _GROUP,
    "RevieweeTag3": "",
    # Relationships — what these two students share, beyond the group.
    "PairContextTag1": "Chess club 2026",
    "PairContextTag2": "",
    "PairContextTag3": "",
    # Observers — the tutor, watching the group she teaches. Her role
    # travels as the tag *value*: observer tags are outside the
    # labelable set, so there is no header suffix to carry it.
    "ObserverName": _TUTOR_NAME,
    "ObserverEmail": _OBSERVER_EMAIL,
    "ObserverTag1": "Tutor",
    "CohortRule": "",
    # Shared across the roster files.
    "PhotoLink": "",
    # Blank re-imports as active; spelled out so the column teaches its
    # own vocabulary rather than looking optional-and-ignorable.
    "Status": "active",
}


#: Friendly labels the templates demonstrate, as ``<Column>.<label>``
#: header suffixes. Only columns in ``field_label_csv``'s labelable set
#: may appear here — a suffix on any other column would not split on
#: import and the cell would read as an unknown column name. The tests
#: assert that through the public ``split_header`` rather than trusting
#: this mapping.
#:
#: Tag 3 is left bare on both rosters on purpose: the set should show
#: both states, so an operator sees that labelling is per column and
#: optional.
LABELS: dict[str, str] = {
    "ReviewerTag1": "Tutor",
    "ReviewerTag2": "Group",
    "RevieweeTag1": "Tutor",
    "RevieweeTag2": "Group",
    "PairContextTag1": "Interest Group",
}


#: Reading order matches Quick Setup's slot order: rosters first, then
#: the relationships that join them, then the optional observers.
STARTER_TEMPLATES: tuple[SetupTemplate, ...] = (
    SetupTemplate("reviewers", "reviewers.csv", REVIEWERS_HEADER),
    SetupTemplate("reviewees", "reviewees.csv", REVIEWEES_HEADER),
    SetupTemplate("relationships", "relationships.csv", RELATIONSHIPS_HEADER),
    SetupTemplate("observers", "observers.csv", OBSERVERS_HEADER),
)

STARTER_ZIP_NAME = "review-robin-setup-templates.zip"


def sample_row(template: SetupTemplate) -> tuple[str, ...]:
    """The single mock row for ``template``, in header order.

    Raises ``KeyError`` for a header column with no entry in
    :data:`SAMPLES` — a loud failure on the request that first hits it,
    rather than a short row the operator would have to debug. The unit
    test catches it long before that.
    """
    return tuple(SAMPLES[column] for column in template.header)


def template_header(template: SetupTemplate) -> tuple[str, ...]:
    """``template``'s header row, with :data:`LABELS` suffixes attached.

    Mirrors ``field_label_csv.labeled_header``'s ``f"{column}.{label}"``
    join, but reads its labels from a constant instead of a session's
    overrides — these templates are generic and have no session.
    """
    return tuple(
        f"{column}.{LABELS[column]}" if column in LABELS else column
        for column in template.header
    )


def template_rows(template: SetupTemplate) -> list[tuple[str, ...]]:
    """``[header, sample_row]`` — the whole file, two rows."""
    return [template_header(template), sample_row(template)]


def build_starter_zip() -> bytes:
    """The four starter templates as one in-memory zip.

    One artefact rather than four links: the two surfaces that offer it
    (the Guide card and the lobby first-run card) are prose, and four
    download links each would crowd both.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for template in STARTER_TEMPLATES:
            csv_bytes = b"".join(stream_csv(template_rows(template)))
            archive.writestr(template.filename, csv_bytes)
    return buffer.getvalue()
