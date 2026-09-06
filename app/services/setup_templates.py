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

**These templates are generic, so their headers are bare** — no
``ReviewerTag1.Tutor`` friendly-label suffixes, because there is no
session whose labels could be read. That is not neutral on re-import: a
bare tag header *clears* that slot's label override
(``app.services.field_labels.apply_captured_labels``, mirroring how an
absent tag value re-imports as NULL). Harmless for the fresh session
these templates are for; an operator re-uploading into a session with
renamed tag columns should export that session's roster instead, which
carries the labels. The Guide's "Create and set up a session" card says
so.

The mock rows are cross-consistent: ``relationships.csv`` references the
addresses in ``reviewers.csv`` and ``reviewees.csv``, so the four files
import as one coherent set rather than four unrelated examples.

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
    "SetupTemplate",
    "STARTER_TEMPLATES",
    "STARTER_ZIP_NAME",
    "build_starter_zip",
    "sample_row",
    "template_rows",
]

#: Every address in every template. Already the codebase convention
#: (`guide/segment_19E_operator_onboarding.md` -> Semantics).
EXAMPLE_DOMAIN = "example.edu"

_REVIEWER_EMAIL = f"alex.tutor@{EXAMPLE_DOMAIN}"
_REVIEWEE_EMAIL = f"sam.student@{EXAMPLE_DOMAIN}"


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
    # Reviewers
    "ReviewerName": "Alex Tutor",
    "ReviewerEmail": _REVIEWER_EMAIL,
    "ReviewerTag1": "Group A",
    "ReviewerTag2": "",
    "ReviewerTag3": "",
    # Reviewees
    "RevieweeName": "Sam Student",
    "RevieweeEmail": _REVIEWEE_EMAIL,
    "RevieweeTag1": "Group A",
    "RevieweeTag2": "",
    "RevieweeTag3": "",
    # Relationships — pair context for the reviewer/reviewee above.
    "PairContextTag1": "Autumn term",
    "PairContextTag2": "",
    "PairContextTag3": "",
    # Observers
    "ObserverName": "Jo Observer",
    "ObserverEmail": f"jo.observer@{EXAMPLE_DOMAIN}",
    "ObserverTag1": "",
    "CohortRule": "",
    # Shared across the roster files.
    "PhotoLink": "",
    # Blank re-imports as active; spelled out so the column teaches its
    # own vocabulary rather than looking optional-and-ignorable.
    "Status": "active",
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


def template_rows(template: SetupTemplate) -> list[tuple[str, ...]]:
    """``[header, sample_row]`` — the whole file, two rows."""
    return [template.header, sample_row(template)]


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
