"""Candidates' dossiers (segment AD2F rung 5, AD2K; rulings 81, 83):
where Create dossiers is the stored timeline's first item, each entry's
dossier is minted once the exercise is published and on each later add;
otherwise the item is only the form's roster."""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import select

from applydesk import candidates, db, dossiers, exercises, operators, people, stages
from applydesk.models import AuditEvent, Dossier, Exercise, Person
from applydesk.models import Stage as StageRow

pytestmark = pytest.mark.usefixtures("applydesk_db")


def _exercise(*, form: bool, published: bool) -> str:
    """An ordinary exercise whose stored timeline is one stage, with or
    without the form, published or not."""
    session = db.new_session()
    owner = session.scalars(select(Person).where(Person.may_operate)).first()
    assert owner is not None
    made = exercises.make(session, operators.Actor(owner), "Candidates only")
    exercise = session.scalars(select(Exercise).where(Exercise.public_id == made.public_id)).one()
    exercise.process_revision = 1  # saved by Process
    session.add(
        StageRow(
            exercise_id=exercise.id,
            key="s1",
            position=1,
            status="published" if published else "draft",
            holds_form=form,
            holds_candidates=True,
        )
    )
    session.commit()
    public_id = exercise.public_id
    session.close()
    return public_id


def _add(public_id: str, address: str) -> None:
    session = db.new_session()
    person = people.pending(session, address, None)
    candidates.add(session, public_id, person, "search", None)
    session.commit()
    session.close()


def _live(public_id: str) -> list[str]:
    return [d for d, _, _ in dossiers.candidate_rows(public_id)]


def test_no_form_published_mints_on_add_and_shows_on_dossiers() -> None:
    ex = _exercise(form=False, published=True)
    _add(ex, "ann@example.edu")
    _add(ex, "bob@example.edu")
    live = _live(ex)
    assert len(live) == 2 and len(set(live)) == 2
    rows = stages.plan_of(ex).rows
    assert [r.dossier.public_id for r in rows] == live
    assert all(r.application is None and r.dossier.name for r in rows)


def test_create_dossiers_with_a_form_after_it_on_its_stage_still_mints() -> None:
    """Ruling 83 as amended (author, 2026-11-27): a Form after Create
    dossiers writes to the dossiers it made; the item still creates them."""
    ex = _exercise(form=True, published=True)
    _add(ex, "ann@example.edu")
    assert len(_live(ex)) == 1


def test_a_draft_mints_at_publish() -> None:
    ex = _exercise(form=False, published=False)
    _add(ex, "ann@example.edu")
    assert _live(ex) == []
    session = db.new_session()
    exercise = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    for row in session.scalars(select(StageRow).where(StageRow.exercise_id == exercise.id)):
        row.status = "published"
    assert dossiers.sync_candidates(session, exercise, None) == 1
    session.commit()
    session.close()
    assert len(_live(ex)) == 1


def _remove(public_id: str) -> None:
    """Take the exercise's first entry off."""
    session = db.new_session()
    entry = candidates.listing(session, public_id)[0].id
    assert candidates.remove(session, public_id, entry, None)
    session.commit()
    session.close()


def test_removing_retires_and_adding_again_mints_a_new_dossier() -> None:
    """Segment AD2K (ruling 83): adding again is a new entry, so a new
    dossier; the old one stays retired."""
    ex = _exercise(form=False, published=True)
    _add(ex, "ann@example.edu")
    [first] = _live(ex)
    _remove(ex)
    assert _live(ex) == []
    _add(ex, "ann@example.edu")
    [second] = _live(ex)
    assert second != first
    session = db.new_session()
    kinds = list(session.scalars(select(AuditEvent.event_type).order_by(AuditEvent.id)))
    assert kinds.count("dossier.minted") == 2 and kinds.count("dossier.retired") == 1
    assert session.scalars(select(Dossier).where(Dossier.public_id == first)).one().retired_at
    session.close()


def test_one_person_holds_two_dossiers_where_the_exercise_allows() -> None:
    ex = _exercise(form=False, published=True)
    session = db.new_session()
    exercise = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    exercise.dossiers_per_person = 2
    session.commit()
    session.close()
    _add(ex, "ann@example.edu")
    _add(ex, "ann@example.edu")
    _add(ex, "ann@example.edu")  # past the most: refused
    assert len(_live(ex)) == 2


def test_the_dossiers_page_lists_a_candidate_s_dossier() -> None:
    from fastapi.testclient import TestClient

    from applydesk.tests._host import host_with

    ex = _exercise(form=False, published=True)
    _add(ex, "ann@example.edu")
    [dossier] = _live(ex)
    client = TestClient(host_with(("applydesk",))[0], follow_redirects=False)
    page = client.get(f"/applydesk/operator/exercises/{ex}/dossiers")
    assert page.status_code == 200
    assert f"<code>{dossier}</code>" in page.text
    assert '<span class="ap-app">Candidate</span>' in page.text
    assert "ann@example.edu" in page.text


def test_a_publishing_process_save_mints_and_the_grid_draws_every_column() -> None:
    """Cold read: through the real hook, `process_store.save`, and with an
    outcome on the stage, so the grid reads each candidate row's cell."""
    from fastapi.testclient import TestClient

    from applydesk import process_store
    from applydesk.tests._host import host_with

    session = db.new_session()
    owner = session.scalars(select(Person).where(Person.may_operate)).first()
    assert owner is not None
    ex = exercises.make(session, operators.Actor(owner), "Candidates, decided").public_id
    session.commit()
    session.close()
    outcome = stages.Outcome("o1", 1, "Decision", ("Yes", "No"), None, "")
    built = (stages.Stage(1, "Shortlist", None, (outcome,), status="Draft", candidates=True),)
    session = db.new_session()
    process_store.save(session, ex, built, 0, owner)
    session.commit()
    session.close()
    _add(ex, "ann@example.edu")
    assert _live(ex) == []  # a draft mints nothing
    session = db.new_session()
    published = tuple(dataclasses.replace(st, status="Published") for st in built)
    process_store.save(session, ex, published, 1, owner)
    session.commit()
    session.close()
    [dossier] = _live(ex)
    page = TestClient(host_with(("applydesk",))[0]).get(
        f"/applydesk/operator/exercises/{ex}/dossiers"
    )
    assert page.status_code == 200, page.text[-400:]
    assert f"<code>{dossier}</code>" in page.text and 'data-status="Candidate"' in page.text
    # An outcome is decidable for a candidate's dossier (it is enterable).
    assert 'aria-label="Decision for ' + dossier in page.text


def test_a_form_placed_first_later_keeps_the_dossiers_and_mints_no_more() -> None:
    """Ruling 83: Create dossiers populates only as the first item; a
    stage placed before it leaves the dossiers made and mints no more."""
    ex = _exercise(form=False, published=True)
    _add(ex, "ann@example.edu")
    [first] = _live(ex)
    session = db.new_session()
    exercise = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    session.add(StageRow(exercise_id=exercise.id, key="s0", position=0, holds_form=True))
    session.commit()
    session.close()
    _add(ex, "bob@example.edu")  # not the first item now: Bob gets none
    assert _live(ex) == [first]


def test_a_csv_mints_once_for_the_file() -> None:
    ex = _exercise(form=False, published=True)
    session = db.new_session()
    done = candidates.import_csv(session, ex, "Email\na@example.edu\nb@example.edu\n", None)
    session.commit()
    kinds = list(session.scalars(select(AuditEvent.event_type)))
    session.close()
    assert done.added == 2 and len(_live(ex)) == 2
    assert kinds.count("dossier.minted") == 1


def test_extract_offers_a_candidates_only_exercise_s_data() -> None:
    """Codex on #4246: Extract counts a candidate's dossier as it counts a
    submitted application, so its downloads are not disabled."""
    from applydesk import extract, sample_data

    ex = _exercise(form=False, published=True)
    found = sample_data.exercise(ex)
    assert found is not None and extract.of(found).submitted == 0
    _add(ex, "ann@example.edu")
    assert extract.of(found).submitted == 1
    _, rows = extract.alias_key(found)
    assert [r[0] for r in rows] == _live(ex) and rows[0][1] == ""


def test_a_sample_s_saved_timeline_lists_its_candidates_dossiers() -> None:
    """Codex on #4246: a sample exercise saved with Candidates and no form
    lists the minted dossiers after its applications, cells kept."""
    from applydesk import process_store

    sample = "c4xh2ndv6s"
    before = stages.plan_of(sample).rows
    session = db.new_session()
    owner = session.scalars(select(Person).where(Person.may_operate)).first()
    built = (stages.Stage(1, "Shortlist", None, (), status="Published", candidates=True),)
    process_store.save(session, sample, built, process_store.revision(sample), owner)
    session.commit()
    session.close()
    _add(sample, "ann@example.edu")
    [dossier] = _live(sample)
    rows = stages.plan_of(sample).rows
    assert [r.dossier.key for r in rows] == [r.dossier.key for r in before] + [dossier]
    assert rows[-1].application is None
