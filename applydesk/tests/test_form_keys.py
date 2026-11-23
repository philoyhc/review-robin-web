"""Questions by key (segment AD2D rung 5; AD-45, AD-62): a rule's form
condition names its question's key, so it follows a rename; a rule naming
a label (the sample's, or one stored before keys) reads as the key the
label maps to and is saved so; a rule naming a question the form drops is
refused; answers and Extract read by key, Extract's header the label."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, replace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import db, extract, form_store, process_store, sample_data, stages
from applydesk.models import Exercise

MODEL = "wa9juxbc2t"
LABEL = "Currently an RA?"


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _key() -> str:
    return next(c.key for c in sample_data.sample_form(MODEL) if c.label == LABEL)


def _form_conds(plan: stages.Plan) -> list[tuple[str, str, str, str]]:
    return [
        c
        for col in plan.columns
        if col.rule is not None
        for when, _ in col.rule.branches
        for c in when
        if c[0] == "form"
    ]


def _save_form(session: Session, cards: list[sample_data.FormCard]) -> None:
    opened = session.scalar(select(Exercise.form_revision).where(Exercise.public_id == MODEL))
    form = form_store.parse(
        {"title": "", "description": "", "cards": [asdict(c) for c in cards]},
        sample_data.people_pools(MODEL),
        {},
    )
    form_store.save(session, MODEL, form, opened or 0, None, published=lambda: False)
    session.commit()


def test_the_sample_s_label_reads_as_its_question_s_key() -> None:
    plan = stages.plan_of(MODEL)
    assert {c[1] for c in _form_conds(plan)} == {_key()}
    questions = sample_data.list_questions(MODEL)
    assert questions[_key()].label == LABEL and "Yes" in questions[_key()].options
    o1 = next(c for c in plan.columns if c.key == "o1")
    assert f"{LABEL} is Yes" in stages.rule_text(plan, o1)


def test_a_rename_keeps_the_rule_and_the_answers(session: Session) -> None:
    key = _key()
    before = sample_data.answers(MODEL, sample_data.applications_of(MODEL)[0])
    cards = [
        replace(c, label="Are you an RA now?") if c.key == key else c
        for c in sample_data.sample_form(MODEL)
    ]
    _save_form(session, cards)
    plan = stages.plan_of(MODEL)
    assert {c[1] for c in _form_conds(plan)} == {key}
    o1 = next(c for c in plan.columns if c.key == "o1")
    assert "Are you an RA now? is Yes" in stages.rule_text(plan, o1)
    assert stages.rule_problems(plan, o1, sample_data.list_questions(MODEL)) == ()
    after = sample_data.answers(MODEL, sample_data.applications_of(MODEL)[0])
    assert after[key] == before[key]  # the sample knows who is an RA, not chance
    # Extract's column is headed by the new label and read by key.
    e = sample_data.exercise(MODEL)
    assert e is not None
    header, rows = extract.applications(e)
    at = header.index("Are you an RA now?")
    assert LABEL not in header and rows and rows[0][at] in ("Yes", "No")


def test_a_rule_stored_by_label_is_saved_by_key(session: Session) -> None:
    built = stages.plan_of(MODEL).stages

    def by_label(c: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
        return (c[0], LABEL, c[2], c[3]) if c[0] == "form" else c

    labelled = tuple(
        replace(
            st,
            columns=tuple(
                replace(
                    col,
                    rule=stages.Rule(
                        tuple(by_label(c) for c in col.rule.when),
                        col.rule.then,
                        col.rule.otherwise,
                        col.rule.more,
                    )
                    if col.rule
                    else None,
                )
                for col in st.columns
            ),
        )
        for st in built
    )
    process_store.save(session, MODEL, labelled, 0, None)
    session.commit()
    stored = process_store.stored_stages(MODEL)
    assert stored is not None
    raw = _form_conds(stages.Plan(stored, ()))
    assert raw and {c[1] for c in raw} == {_key()}


def test_a_rule_naming_a_dropped_question_is_refused(session: Session) -> None:
    key = _key()
    _save_form(session, [c for c in sample_data.sample_form(MODEL) if c.key != key])
    plan = stages.plan_of(MODEL)
    o1 = next(c for c in plan.columns if c.key == "o1")
    problems = stages.rule_problems(plan, o1, sample_data.list_questions(MODEL))
    assert "reads a question the form no longer asks as a choose-one List question" in problems
    assert "(removed) is Yes" in stages.rule_text(plan, o1)
    with pytest.raises(process_store.Refused, match="no longer asks") as why:
        process_store.save(session, MODEL, plan.stages, 0, None)
    assert why.value.key == "rule_target"


GRANT = "r6tm4kq9wz"  # its form asks for a preferred evaluator, a nominated source


def _save_grant(session: Session, cards: list[sample_data.FormCard], **kw: object) -> None:
    opened = session.scalar(select(Exercise.form_revision).where(Exercise.public_id == GRANT))
    form = form_store.parse(
        {"title": "", "description": "", "cards": [asdict(c) for c in cards]},
        sample_data.people_pools(GRANT),
        {},
    )
    form_store.save(session, GRANT, form, opened or 0, None, published=lambda: False, **kw)  # pyright: ignore[reportArgumentType]  -- in_use, when given
    session.commit()


def _people_key() -> str:
    return next(c.key for c in sample_data.sample_form(GRANT) if c.type == "people")


def test_a_rename_keeps_nominees_and_seeded_answers(session: Session) -> None:
    key = _people_key()
    apps = sample_data.applications_of(GRANT)
    before = [sample_data.nominees(GRANT, a, key) for a in apps]
    answers = [sample_data.answers(GRANT, a) for a in apps]
    assert any(before)
    # A label stored before keys reads as the same question.
    assert [sample_data.nominees(GRANT, a, "Preferred evaluator") for a in apps] == before
    cards = [replace(c, label=f"{c.label} (renamed)") for c in sample_data.sample_form(GRANT)]
    _save_grant(session, cards)
    assert [sample_data.nominees(GRANT, a, key) for a in apps] == before
    assert [sample_data.nominees(GRANT, a, "Preferred evaluator") for a in apps] == before
    assert [sample_data.answers(GRANT, a) for a in apps] == answers
    # A nominated source stored by label reads as the question's key.
    gate = stages.Gate(
        "g9", 9, "Read", "RRW", sources=(stages.Source("nominated", "Preferred evaluator", 1, 1),)
    )
    keyed = stages.form_keyed((stages.Stage(1, "", None, columns=(gate,)),), GRANT)
    assert [s.ref for s in keyed[0].columns[0].sources] == [key]  # pyright: ignore[reportAttributeAccessIssue]  -- a Gate
    assert stages.form_reads(stages.Plan(keyed, ())) == (frozenset(), frozenset({key}))


def test_form_refuses_to_drop_a_question_the_process_reads(session: Session) -> None:
    people = _people_key()
    reads = lambda: (frozenset[str](), frozenset({people}))  # noqa: E731
    cards = [c for c in sample_data.sample_form(GRANT) if c.key != people]
    with pytest.raises(form_store.Refused, match="nominated source") as why:
        _save_grant(session, cards, in_use=reads)
    assert why.value.key == "in_use"
    session.rollback()
    # Made another type, it is refused too; a rename is not.
    retyped = [
        replace(c, type="string") if c.key == people else c for c in sample_data.sample_form(GRANT)
    ]
    with pytest.raises(form_store.Refused, match="nominated source"):
        _save_grant(session, retyped, in_use=reads)
    session.rollback()
    renamed = [
        replace(c, label="Who?") if c.key == people else c for c in sample_data.sample_form(GRANT)
    ]
    _save_grant(session, renamed, in_use=reads)


def test_a_rule_s_question_may_not_be_dropped_on_form(session: Session) -> None:
    reads = lambda: stages.form_reads(stages.plan_of(MODEL))  # noqa: E731
    cards = [c for c in sample_data.sample_form(MODEL) if c.key != _key()]
    opened = session.scalar(select(Exercise.form_revision).where(Exercise.public_id == MODEL))
    form = form_store.parse(
        {"title": "", "description": "", "cards": [asdict(c) for c in cards]},
        sample_data.people_pools(MODEL),
        {},
    )
    with pytest.raises(form_store.Refused, match="a rule on Process"):
        form_store.save(
            session, MODEL, form, opened or 0, None, published=lambda: False, in_use=reads
        )
