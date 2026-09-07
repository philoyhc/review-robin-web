"""Setup CSV templates — Segment 19E rungs 4 and 5.

The value of these templates is that they cannot drift from the
importers. These tests are what makes that true: the headers are checked
against the extracts they are taken from, and every row is checked
against its header. Both sets go through the same checks, because the
demo set is the starter set's generator with different inputs.
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
    EXAMPLE_DOMAIN,
    LABELS,
    SETS,
    TEMPLATES,
    build_zip,
    row_tuple,
    set_by_key,
    template_header,
    template_rows,
    templates_in,
)

ALL_SETS = pytest.mark.parametrize(
    "template_set", SETS, ids=[s.key for s in SETS]
)


def test_every_header_is_the_extracts_own_tuple() -> None:
    """The templates hold the extract's ``HEADER`` by reference, so a
    column added to an extract reaches both sets with no edit here.
    Identity, not equality — a copied tuple would compare equal today and
    silently diverge tomorrow."""
    by_key = {t.key: t for t in TEMPLATES}

    assert by_key["reviewers"].header is REVIEWERS_HEADER
    assert by_key["reviewees"].header is REVIEWEES_HEADER
    assert by_key["relationships"].header is RELATIONSHIPS_HEADER
    assert by_key["observers"].header is OBSERVERS_HEADER


@ALL_SETS
def test_every_row_covers_its_header_exactly(template_set) -> None:
    """Both directions at once: a header column with no cell would raise
    on the request that first served it, and a cell for a column the
    header does not have is dead weight that looks maintained."""
    for template in templates_in(template_set):
        for row in template_set.rows[template.key]:
            assert set(row) == set(template.header), (
                template_set.key,
                template.filename,
            )


@ALL_SETS
def test_every_file_has_a_header_and_at_least_one_row(template_set) -> None:
    for template in templates_in(template_set):
        rows = template_rows(template_set, template)

        assert rows[0] == template_header(template)
        assert len(rows) > 1
        assert all(len(r) == len(template.header) for r in rows[1:])


@ALL_SETS
def test_every_labelled_header_cell_splits_back(template_set) -> None:
    """The suffix grammar is the point of labelling these templates, and
    it is only valid on the nine columns `field_label_csv` treats as
    labelable. Checked through the real `split_header` rather than
    against the module's private set: a suffix on any other column comes
    back unsplit, so this assertion is what would catch it."""
    for template in templates_in(template_set):
        for cell, column in zip(
            template_header(template), template.header, strict=True
        ):
            split_column, label = field_label_csv.split_header(cell)

            assert split_column == column, cell
            assert label == LABELS.get(column), cell


@ALL_SETS
def test_every_address_is_example_edu(template_set) -> None:
    """`guide/archive/segment_19E_operator_onboarding.md` -> Semantics. A real
    domain in a template is a mail-out waiting to happen once sending is
    switched on."""
    for template in templates_in(template_set):
        for row in template_set.rows[template.key]:
            for value in row.values():
                if "@" in value:
                    assert value.endswith(f"@{EXAMPLE_DOMAIN}"), value


@ALL_SETS
def test_the_relationship_rows_reference_the_roster_rows(template_set) -> None:
    """Each set is one coherent scenario, not files that happen to parse
    alone: every pair names people the rosters define. A typo in an
    address here is a row the importer rejects as an unknown reviewer."""
    reviewer_emails = {
        r["ReviewerEmail"] for r in template_set.rows["reviewers"]
    }
    reviewee_emails = {
        r["RevieweeEmail"] for r in template_set.rows["reviewees"]
    }

    for pair in template_set.rows["relationships"]:
        assert pair["ReviewerEmail"] in reviewer_emails, pair
        assert pair["RevieweeEmail"] in reviewee_emails, pair


def test_observer_tags_carry_no_suffix() -> None:
    """Observer tags are outside the labelable set by design, so a
    tutor's role travels as a cell value. A suffix there would survive
    generation, fail to split on import, and be read as an unknown
    column — losing the tag silently."""
    observers = next(t for t in TEMPLATES if t.key == "observers")

    assert "ObserverTag1" not in LABELS
    assert "ObserverTag1" in template_header(observers)
    for template_set in SETS:
        for row in template_set.rows["observers"]:
            assert row["ObserverTag1"] == "Tutor"


def test_a_tag_column_is_left_bare_on_each_roster() -> None:
    """The sets should show both states — labelled and bare — so an
    operator sees that labelling is per column and optional."""
    for key in ("reviewers", "reviewees"):
        template = next(t for t in TEMPLATES if t.key == key)
        header = template_header(template)

        assert any("." in cell for cell in header)
        assert any("." not in cell for cell in header)


def test_a_header_column_with_no_cell_raises() -> None:
    """The failure mode is loud, not a short row."""
    broken = setup_templates.SetupTemplate(
        "broken", "broken.csv", ("ReviewerName", "NotAColumnWeSupply")
    )

    with pytest.raises(KeyError):
        row_tuple(broken, {"ReviewerName": "Alex Student"})


def test_an_unknown_set_key_raises() -> None:
    with pytest.raises(KeyError):
        set_by_key("no-such-set")


@ALL_SETS
def test_the_zip_holds_every_file_and_parses_as_csv(template_set) -> None:
    archive = zipfile.ZipFile(io.BytesIO(build_zip(template_set)))

    assert sorted(archive.namelist()) == sorted(
        t.filename for t in templates_in(template_set)
    )
    for template in templates_in(template_set):
        text = archive.read(template.filename).decode("utf-8")
        parsed = list(csv.reader(io.StringIO(text)))

        assert parsed[0] == list(template_header(template))
        assert len(parsed) == len(template_set.rows[template.key]) + 1


def test_the_demo_set_is_a_symmetrical_cohort() -> None:
    """Peer review, so the two rosters are one cohort seen twice. A demo
    where reviewers and reviewees were disjoint would teach the wrong
    shape — and would make self-review exclusion invisible."""
    demo = set_by_key("demo")

    reviewers = {r["ReviewerEmail"] for r in demo.rows["reviewers"]}
    reviewees = {r["RevieweeEmail"] for r in demo.rows["reviewees"]}

    assert reviewers == reviewees
    assert len(reviewers) == 6


def test_the_demo_set_is_bigger_than_the_starter_set() -> None:
    """The two sets do different jobs — 'edit this' versus 'watch this
    work' — and a demo the same size as the starter would do neither."""
    starter, demo = set_by_key("starter"), set_by_key("demo")

    for key in ("reviewers", "reviewees", "relationships", "observers"):
        assert len(demo.rows[key]) > len(starter.rows[key]), key


def test_no_demo_pair_is_a_self_review() -> None:
    """Self-review is a session-level toggle, not something a roster
    encodes. A self-pair in the relationships file would suggest it is."""
    demo = set_by_key("demo")

    for pair in demo.rows["relationships"]:
        assert pair["ReviewerEmail"] != pair["RevieweeEmail"], pair
