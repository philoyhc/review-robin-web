"""Setup CSV templates — Segment 19E rungs 4 and 5.

Two downloadable sets of roster CSVs, both generic and both served from
surfaces that render **before a session exists** — the Guide and the
lobby first-run card — so nothing here takes a ``ReviewSession``.

- **starter** (rung 4): one row per file. The format, to edit.
- **demo** (rung 5): a populated tutorial cohort. Uploaded through Quick
  Setup it builds a session that reaches ``validated`` with no
  configuration, which is asserted end-to-end in
  ``tests/integration/test_setup_template_download.py``.

Neither set carries a ``settings.csv``. It is not an omission: a new
session is seeded with a default instrument (``ensure_default_instrument``)
whose new-model rule defaults to Full Matrix, so rosters alone reach
``validated``. A settings file would also be the one artefact here that
could not be derived — it is a ``field,value,data_type`` dump of a whole
live session rather than a row-shaped roster.

**Headers are derived, never authored.** Each template's header is the
``HEADER`` tuple of the extract that already serialises that file, held
by reference, so a column added to a roster extract appears in both sets
on the next request. The importer's own contract tests pin those tuples
against the parsers, which makes them the right thing to copy.

**The headers carry worked friendly labels**, as ``ReviewerTag1.Tutor`` /
``ReviewerTag2.Group`` and ``PairContextTag1.Interest Group``. Generic
templates have no session to read overrides from, so these are examples —
but the suffix grammar is the one thing about roster CSVs an operator
cannot guess, and a template that demonstrates it teaches more than one
that avoids it. Tag 3 stays bare, so the sets show labelling as per
column and optional.

The consequence is live: on import a labelled header **sets** that slot's
override (``field_labels.apply_captured_labels``), so uploading a
template unedited renames the session's tag columns. The same mechanism
in reverse is why a bare tag header clears an override. The Guide states
both directions.

Only the nine columns in ``field_label_csv``'s labelable set may carry a
suffix. Observer tags are deliberately outside it, so ``ObserverTag1``
stays bare and a tutor's role travels as the cell *value*; a suffix there
would not split on import and the whole cell would be read as an unknown
column name. :func:`template_header` is asserted against ``split_header``
in the tests, which is the public check for exactly that.

**Both sets are one scenario, scaled.** Students peer-reviewing each
other inside a tutorial group: the starter set is one pair with their
tutor observing, the demo set is two groups of three with both tutors
observing. Every roster row is a person who appears as both reviewer and
reviewee in the demo set — the review is symmetrical, and a set where
reviewers and reviewees were disjoint would teach the wrong shape.

Plan: ``guide/segment_19E_operator_onboarding.md`` PR ladder rungs 4–5.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping
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
    "SETS",
    "SetupTemplate",
    "TEMPLATES",
    "TemplateSet",
    "build_zip",
    "row_tuple",
    "set_by_key",
    "template_header",
    "template_rows",
]

#: Every address in every template. Already the codebase convention
#: (`guide/segment_19E_operator_onboarding.md` -> Semantics).
EXAMPLE_DOMAIN = "example.edu"


def _email(name: str) -> str:
    """``"Alex Student"`` -> ``"alex.student@example.edu"``.

    Derived rather than written out per row so a name and its address
    cannot drift apart across the four files — which is exactly what
    would break the relationships file's references.
    """
    return f"{name.lower().replace(' ', '.')}@{EXAMPLE_DOMAIN}"


# The cohort both sets draw from. Surnames are the person's role, which
# reads as heavy-handed in prose and is the right call here: an operator
# skimming a demo roster should never wonder whether a row is real.
_TUTOR_TW01 = "Catharine Tutor"
_TUTOR_TW02 = "Daniel Tutor"
_TW01 = ("Alex Student", "Sam Student", "Nina Student")
_TW02 = ("Omar Student", "Priya Student", "Wei Student")


@dataclass(frozen=True)
class SetupTemplate:
    """One file that can appear in a set.

    ``header`` is the extract's own ``HEADER`` tuple, held by reference
    rather than copied — this dataclass never restates a column name.
    """

    key: str
    filename: str
    header: tuple[str, ...]


@dataclass(frozen=True)
class TemplateSet:
    """One downloadable zip: which files, and the rows in each.

    ``rows`` maps a template key to that file's body rows, each a
    column-name -> cell mapping. A file with no entry is left out of the
    set entirely, so a set can carry a subset of :data:`TEMPLATES`.
    """

    key: str
    zip_name: str
    rows: Mapping[str, tuple[Mapping[str, str], ...]]


#: Reading order matches Quick Setup's slot order: rosters first, then
#: the relationships that join them, then the optional observers.
TEMPLATES: tuple[SetupTemplate, ...] = (
    SetupTemplate("reviewers", "reviewers.csv", REVIEWERS_HEADER),
    SetupTemplate("reviewees", "reviewees.csv", REVIEWEES_HEADER),
    SetupTemplate("relationships", "relationships.csv", RELATIONSHIPS_HEADER),
    SetupTemplate("observers", "observers.csv", OBSERVERS_HEADER),
)

#: Friendly labels the templates demonstrate, as ``<Column>.<label>``
#: header suffixes. Only columns in ``field_label_csv``'s labelable set
#: may appear here — a suffix on any other column would not split on
#: import and the cell would read as an unknown column name. The tests
#: assert that through the public ``split_header`` rather than trusting
#: this mapping.
LABELS: dict[str, str] = {
    "ReviewerTag1": "Tutor",
    "ReviewerTag2": "Group",
    "RevieweeTag1": "Tutor",
    "RevieweeTag2": "Group",
    "PairContextTag1": "Interest Group",
}


def _student_row(prefix: str, name: str, tutor: str, group: str) -> dict[str, str]:
    """One roster row. ``prefix`` is ``Reviewer`` or ``Reviewee`` — the
    two headers are identical but for that stem, so one builder serves
    both and a divergence between the files becomes impossible."""
    return {
        f"{prefix}Name": name,
        f"{prefix}Email": _email(name),
        f"{prefix}Tag1": tutor,
        f"{prefix}Tag2": group,
        f"{prefix}Tag3": "",
        "PhotoLink": "",
        "Status": "active",
    }


def _observer_row(name: str, group: str) -> dict[str, str]:
    return {
        "ObserverName": name,
        # Observer tags are outside the labelable set, so the role
        # travels as a value rather than a header suffix.
        "ObserverEmail": _email(name),
        "ObserverTag1": "Tutor",
        "Status": "active",
        "CohortRule": "",
    }


def _pair_row(reviewer: str, reviewee: str, interest: str) -> dict[str, str]:
    return {
        "ReviewerEmail": _email(reviewer),
        "RevieweeEmail": _email(reviewee),
        "PairContextTag1": interest,
        "PairContextTag2": "",
        "PairContextTag3": "",
        "Status": "active",
    }


def _peer_pairs(
    group: tuple[str, ...], interest: str
) -> tuple[dict[str, str], ...]:
    """Every ordered within-group pair, excluding self-review.

    Generated rather than written out: a hand-listed set of pairs across
    two groups is where a typo would hide, and a wrong address here is a
    row the importer rejects as an unknown reviewer.
    """
    return tuple(
        _pair_row(reviewer, reviewee, interest)
        for reviewer in group
        for reviewee in group
        if reviewer != reviewee
    )


#: **starter** — one row per file: the format, to edit.
_STARTER = TemplateSet(
    key="starter",
    zip_name="review-robin-setup-templates.zip",
    rows={
        "reviewers": (_student_row("Reviewer", _TW01[0], _TUTOR_TW01, "TW01"),),
        "reviewees": (_student_row("Reviewee", _TW01[1], _TUTOR_TW01, "TW01"),),
        "relationships": (
            _pair_row(_TW01[0], _TW01[1], "Chess club 2026"),
        ),
        "observers": (_observer_row(_TUTOR_TW01, "TW01"),),
    },
)

#: **demo** — two tutorial groups of three, every student both reviewer
#: and reviewee, both tutors observing. Sized so the surfaces a
#: one-pair session cannot demonstrate — the Assignments page, the
#: Responses grid, observer collation — all have something in them.
_DEMO = TemplateSet(
    key="demo",
    zip_name="review-robin-demo-session.zip",
    rows={
        "reviewers": tuple(
            _student_row("Reviewer", name, tutor, group)
            for group, tutor, members in (
                ("TW01", _TUTOR_TW01, _TW01),
                ("TW02", _TUTOR_TW02, _TW02),
            )
            for name in members
        ),
        # The same six people. Symmetrical peer review is the whole
        # scenario, so the two rosters are one cohort seen twice rather
        # than two populations.
        "reviewees": tuple(
            _student_row("Reviewee", name, tutor, group)
            for group, tutor, members in (
                ("TW01", _TUTOR_TW01, _TW01),
                ("TW02", _TUTOR_TW02, _TW02),
            )
            for name in members
        ),
        # Context only where there is any: TW01 shares an interest
        # group, TW02 does not. A set where every row carried context
        # would suggest the column is required.
        "relationships": (
            *_peer_pairs(_TW01, "Chess club 2026"),
            *_peer_pairs(_TW02, ""),
        ),
        "observers": (
            _observer_row(_TUTOR_TW01, "TW01"),
            _observer_row(_TUTOR_TW02, "TW02"),
        ),
    },
)

SETS: tuple[TemplateSet, ...] = (_STARTER, _DEMO)


def set_by_key(key: str) -> TemplateSet:
    """The set named ``key``. Raises ``KeyError`` for an unknown name."""
    for template_set in SETS:
        if template_set.key == key:
            return template_set
    raise KeyError(key)


def templates_in(template_set: TemplateSet) -> tuple[SetupTemplate, ...]:
    """The files ``template_set`` carries, in :data:`TEMPLATES` order."""
    return tuple(t for t in TEMPLATES if t.key in template_set.rows)


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


def row_tuple(
    template: SetupTemplate, row: Mapping[str, str]
) -> tuple[str, ...]:
    """One row's cells in header order.

    Raises ``KeyError`` for a header column the row does not supply — a
    loud failure on the request that first hits it, rather than a short
    row the operator would have to debug. The unit tests catch it long
    before that.
    """
    return tuple(row[column] for column in template.header)


def template_rows(
    template_set: TemplateSet, template: SetupTemplate
) -> list[tuple[str, ...]]:
    """``[header, *body]`` — the whole file."""
    return [
        template_header(template),
        *(row_tuple(template, row) for row in template_set.rows[template.key]),
    ]


def build_zip(template_set: TemplateSet) -> bytes:
    """``template_set``'s files as one in-memory zip.

    One artefact per set rather than a link per file: the surfaces that
    offer them are prose — a Guide card and a compact lobby card — and a
    link per file would crowd both.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for template in templates_in(template_set):
            csv_bytes = b"".join(
                stream_csv(template_rows(template_set, template))
            )
            archive.writestr(template.filename, csv_bytes)
    return buffer.getvalue()
