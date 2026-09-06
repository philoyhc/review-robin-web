"""Generic setup CSV templates — Segment 19E rung 4.

The value of these templates is that they cannot drift from the
importers. These tests are what makes that true: the headers are checked
against the extracts they are taken from, and the sample mapping is
checked against the headers.
"""

from __future__ import annotations

import csv
import io
import zipfile

import pytest

from app.services import field_label_csv, setup_templates
from app.services.extracts.observers_extract import HEADER as OBSERVERS_HEADER
from app.services.extracts.relationships_extract import (
    HEADER as RELATIONSHIPS_HEADER,
)
from app.services.extracts.reviewees_extract import HEADER as REVIEWEES_HEADER
from app.services.extracts.reviewers_extract import HEADER as REVIEWERS_HEADER
from app.services.setup_templates import (
    LABELS,
    SAMPLES,
    STARTER_TEMPLATES,
    build_starter_zip,
    sample_row,
    template_header,
    template_rows,
)


def test_every_header_is_the_extracts_own_tuple() -> None:
    """The templates hold the extract's ``HEADER`` by reference, so a
    column added to an extract reaches the template with no edit here.
    Identity, not equality — a copied tuple would compare equal today and
    silently diverge tomorrow."""
    by_key = {t.key: t for t in STARTER_TEMPLATES}

    assert by_key["reviewers"].header is REVIEWERS_HEADER
    assert by_key["reviewees"].header is REVIEWEES_HEADER
    assert by_key["relationships"].header is RELATIONSHIPS_HEADER
    assert by_key["observers"].header is OBSERVERS_HEADER


def test_every_header_column_has_a_sample() -> None:
    """A column with no sample would raise on the request that first
    served it. This is where that gets caught instead."""
    for template in STARTER_TEMPLATES:
        for column in template.header:
            assert column in SAMPLES, f"{template.filename}: {column}"


def test_the_sample_mapping_has_no_columns_the_headers_do_not_use() -> None:
    """The other direction: a sample left behind after a column was
    renamed or dropped from an extract is dead weight that looks
    maintained."""
    used = {column for t in STARTER_TEMPLATES for column in t.header}

    assert set(SAMPLES) == used


def test_each_file_is_a_header_and_exactly_one_row() -> None:
    """'One mock row per file' — the starter set teaches the format; the
    demo set (rung 5) is what carries volume."""
    for template in STARTER_TEMPLATES:
        rows = template_rows(template)

        assert len(rows) == 2
        assert rows[0] == template_header(template)
        assert len(rows[1]) == len(template.header)


def test_the_relationship_row_references_the_roster_rows() -> None:
    """The four files import as one coherent set, not four unrelated
    examples: the relationship pairs the reviewer and reviewee the other
    two files define. An operator who uploads the set unedited gets a
    working one-pair session."""
    by_key = {t.key: t for t in STARTER_TEMPLATES}

    def cell(key: str, column: str) -> str:
        template = by_key[key]
        return sample_row(template)[template.header.index(column)]

    assert cell("relationships", "ReviewerEmail") == cell(
        "reviewers", "ReviewerEmail"
    )
    assert cell("relationships", "RevieweeEmail") == cell(
        "reviewees", "RevieweeEmail"
    )


def test_every_address_is_example_edu() -> None:
    """`guide/segment_19E_operator_onboarding.md` -> Semantics. A real
    domain in a template is a mail-out waiting to happen."""
    for value in SAMPLES.values():
        if "@" in value:
            assert value.endswith(f"@{setup_templates.EXAMPLE_DOMAIN}"), value


def test_every_labelled_header_cell_splits_back_to_its_column_and_label() -> None:
    """The suffix grammar is the point of labelling these templates, and
    it is only valid on the nine columns `field_label_csv` treats as
    labelable. Checked through the real `split_header` rather than
    against the module's private set: a suffix on any other column comes
    back unsplit, so this assertion is what would catch it."""
    for template in STARTER_TEMPLATES:
        for cell, column in zip(
            template_header(template), template.header, strict=True
        ):
            split_column, label = field_label_csv.split_header(cell)

            assert split_column == column, cell
            assert label == LABELS.get(column), cell


def test_observer_tags_carry_no_suffix() -> None:
    """Observer tags are outside the labelable set by design, so the
    tutor's role travels as a cell value. A suffix there would survive
    generation, fail to split on import, and be read as an unknown
    column — losing the tag silently."""
    observers = next(t for t in STARTER_TEMPLATES if t.key == "observers")

    assert "ObserverTag1" not in LABELS
    assert "ObserverTag1" in template_header(observers)
    assert SAMPLES["ObserverTag1"] == "Tutor"


def test_a_tag_column_is_left_bare_on_each_roster() -> None:
    """The set should show both states — labelled and bare — so an
    operator sees that labelling is per column and optional."""
    for key in ("reviewers", "reviewees"):
        template = next(t for t in STARTER_TEMPLATES if t.key == key)

        assert any("." in cell for cell in template_header(template))
        assert any("." not in cell for cell in template_header(template))


def test_a_header_column_with_no_sample_raises() -> None:
    """The failure mode is loud, not a short row."""
    broken = setup_templates.SetupTemplate(
        "broken", "broken.csv", ("ReviewerName", "NotAColumnWeSample")
    )

    with pytest.raises(KeyError):
        sample_row(broken)


def test_the_zip_holds_every_template_and_parses_as_csv() -> None:
    archive = zipfile.ZipFile(io.BytesIO(build_starter_zip()))

    assert sorted(archive.namelist()) == sorted(
        t.filename for t in STARTER_TEMPLATES
    )
    for template in STARTER_TEMPLATES:
        text = archive.read(template.filename).decode("utf-8")
        parsed = list(csv.reader(io.StringIO(text)))

        assert parsed[0] == list(template_header(template))
        assert len(parsed) == 2
