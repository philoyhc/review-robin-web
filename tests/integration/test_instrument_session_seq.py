"""``Instrument.session_seq`` — the per-session instrument number.

19Q Item 6 rung 1. The operator-facing number was ``Instrument.id``, a
workspace-wide autoincrement, so a session holding two instruments
could label them ``Instrument_1`` and ``Instrument_7`` (author's
screenshot, 2026-09-19). This column is per-session, assigned once at
creation, and never updated.

Nothing here reads a label or a tint yet — those are rungs 2 and 3.
What this pins is the number's three properties: per-session, creation
order, and immovable.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.schemas.sessions import SessionCreate
from app.services import session_clone, sessions
from app.services.instruments import _instrument_crud as crud

from ._invitation_states import _create_session as _client_session


def _session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = db.execute(select(User).where(User.email == "seq-op@example.edu")).scalar()
    if op is None:
        op = User(email="seq-op@example.edu", display_name="Op")
        db.add(op)
        db.flush()
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name=code.title(), code=code)
    )
    return review_session, op


def _seqs(db: Session, session_id: int) -> list[int]:
    return list(
        db.execute(
            select(Instrument.session_seq)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.id)
        ).scalars()
    )


def test_each_session_numbers_from_one(db: Session) -> None:
    """The defect, directly. Two sessions' instruments interleave in
    ``id`` because the PK is workspace-wide; their ``session_seq`` does
    not, because it is not."""
    first, op = _session(db, "seq-a")
    second, _ = _session(db, "seq-b")

    crud.create_instrument(db, review_session=first, actor=op)
    crud.create_instrument(db, review_session=second, actor=op)
    crud.create_instrument(db, review_session=first, actor=op)
    db.flush()

    assert _seqs(db, first.id) == [1, 2, 3]
    assert _seqs(db, second.id) == [1, 2]

    # The premise: without it the assertions above would pass on a
    # column that had simply copied a contiguous id run.
    ids = list(
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == first.id)
            .order_by(Instrument.id)
        ).scalars()
    )
    assert ids != [1, 2, 3], "ids happened to be contiguous — test is vacuous"


def test_delete_neither_renumbers_nor_frees_the_number(db: Session) -> None:
    """Gaps are the contract (author, 2026-09-19): a handle that closes
    up after a delete is a handle that moved."""
    review_session, op = _session(db, "seq-del")
    for _ in range(3):
        crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 2, 3, 4]  # 1 is the seeded default

    second = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.session_seq == 2)
    ).scalar_one()
    crud.delete_instrument(db, instrument=second, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 3, 4]

    crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 3, 4, 5], "2 was reused"


def test_reorder_does_not_touch_the_number(db: Session) -> None:
    """The whole reason it is not ``Instrument.order``: drag-and-drop
    ships, and the number must not move under it."""
    review_session, op = _session(db, "seq-reorder")
    for _ in range(2):
        crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    rows = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        ).scalars()
    )
    before = [r.session_seq for r in rows]

    from app.services import instruments as instruments_service

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[r.id for r in reversed(rows)],
        actor=op,
    )
    db.flush()

    for row in rows:
        db.refresh(row)
    assert [r.session_seq for r in rows] == before
    # The control: the reorder really did happen.
    assert [r.order for r in rows] != sorted(r.order for r in rows)


def test_replicate_takes_a_fresh_number(db: Session) -> None:
    review_session, op = _session(db, "seq-rep")
    source = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()

    crud.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    db.flush()
    assert _seqs(db, review_session.id) == [1, 2]


def test_clone_preserves_the_source_sequence(db: Session) -> None:
    """Author's ruling, 2026-09-19: a source reading 1, 3, 2 down the
    page clones to 1, 3, 2, not 1, 2, 3.

    ``session_clone`` copies every mapped column, so this needs no code
    — which is exactly why it needs a test.
    """
    source, op = _session(db, "seq-clone")
    for _ in range(2):
        crud.create_instrument(db, review_session=source, actor=op)
    db.flush()
    middle = db.execute(
        select(Instrument)
        .where(Instrument.session_id == source.id)
        .where(Instrument.session_seq == 2)
    ).scalar_one()
    crud.delete_instrument(db, instrument=middle, actor=op)
    db.commit()
    assert _seqs(db, source.id) == [1, 3]

    clone = session_clone.clone_session(db, source=source, user=op, mode="all")
    db.flush()
    assert _seqs(db, clone.id) == [1, 3], "clone renumbered"


def test_the_migration_backfill_ranks_by_creation_order_per_session() -> None:
    """The backfill statement itself, run against real rows.

    The suite builds its schema from ORM metadata, so the migration
    never executes here — this is the only place its SQL is exercised.
    """
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "_seq_migration",
        pathlib.Path(__file__).resolve().parents[2]
        / "alembic/versions/b7d4f2a9c153_instruments_session_seq.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _BACKFILL = module._BACKFILL

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE instruments ("
                "  id INTEGER PRIMARY KEY,"
                "  session_id INTEGER NOT NULL,"
                "  session_seq INTEGER"
                ")"
            )
        )
        # Interleaved ids across two sessions, with gaps — what a
        # workspace-wide autoincrement actually produces.
        conn.execute(
            sa.text(
                "INSERT INTO instruments (id, session_id) VALUES "
                "(3, 1), (7, 1), (8, 2), (12, 1), (40, 2)"
            )
        )
        conn.execute(_BACKFILL)
        rows = conn.execute(
            sa.text(
                "SELECT id, session_id, session_seq FROM instruments ORDER BY id"
            )
        ).all()

    assert rows == [(3, 1, 1), (7, 1, 2), (8, 2, 1), (12, 1, 3), (40, 2, 2)]


# --------------------------------------------------------------------------- #
# Rung 2 — the label, in all three places it is spelled
# --------------------------------------------------------------------------- #


def test_the_fallback_label_is_per_session(db: Session) -> None:
    """The defect the author screenshotted: two instruments in one
    session titled ``Instrument_1`` and ``Instrument_7``."""
    from app.services.instruments import _instrument_label

    first, op = _session(db, "lbl-a")
    second, _ = _session(db, "lbl-b")
    crud.create_instrument(db, review_session=second, actor=op)
    crud.create_instrument(db, review_session=first, actor=op)
    db.flush()

    labels = [
        _instrument_label(inst)
        for inst in db.execute(
            select(Instrument)
            .where(Instrument.session_id == first.id)
            .order_by(Instrument.id)
        ).scalars()
    ]
    assert labels == ["Instrument_1", "Instrument_2"]


def test_a_short_label_still_wins(db: Session) -> None:
    """The fallback is a fallback. Rung 2 changed what it falls back
    *to*, not when it fires."""
    from app.services.instruments import _instrument_label

    review_session, op = _session(db, "lbl-short")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.short_label = "Peer feedback"
    db.flush()
    assert _instrument_label(instrument) == "Peer feedback"


def test_the_card_title_and_the_delete_confirm_show_the_same_handle(
    client: TestClient, db: Session
) -> None:
    """Both render sites, from one implementation.

    Before rung 2 the title inlined its own copy of the rule and the
    confirmation used ``Instrument #{loop.index}`` — the display
    position, with a ``#`` the operator-identifier policy reserves for
    reviewer-facing headings. They could not disagree by accident
    because they never agreed by design.
    """
    review_session = _client_session(client, db, "lbl-render")
    op = db.execute(select(User)).scalars().first()
    crud.ensure_default_instrument(db, review_session)
    crud.create_instrument(db, review_session=review_session, actor=op)
    db.commit()

    response = client.get(f"/operator/sessions/{review_session.id}/instruments")
    assert response.status_code == 200, response.text[:400]
    body = response.text

    start = body.index('<summary class="instrument-card-summary">')
    summary = body[start : body.index("</summary>", start)]
    assert "Instrument_1" in summary

    confirm_start = body.index("Yes, delete <strong>")
    confirm = body[confirm_start : confirm_start + 200]
    assert "Instrument_1" in confirm
    assert "Instrument #" not in body, "the reserved # prefix is back"


def test_the_delete_confirm_names_a_renamed_instrument(
    client: TestClient, db: Session
) -> None:
    """The third defect in that one string: it ignored ``short_label``,
    so an operator who named the instrument was asked to confirm
    deleting a name nobody chose."""
    review_session = _client_session(client, db, "lbl-named")
    crud.ensure_default_instrument(db, review_session)
    db.flush()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.short_label = "Peer feedback"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    confirm_start = body.index("Yes, delete <strong>")
    confirm = body[confirm_start : confirm_start + 200]
    assert "Peer feedback" in confirm
    assert "Instrument_" not in confirm


def test_no_template_spells_the_fallback_itself() -> None:
    """The definition-of-done line that would have caught rung 2's
    surprise: the rule had two implementations, and the surface the
    author looks at used the one that is not the service.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "app/web/templates"
    # Jinja comments are stripped first: this guard is about what a
    # template *renders*, and a check that tripped on prose explaining
    # the defect would be a check that discourages explaining it.
    comment = re.compile(r"\{#.*?#\}", re.S)
    offenders = [
        f"{path.relative_to(root)}:{n}"
        for path in root.rglob("*.html")
        for n, line in enumerate(comment.sub("", path.read_text()).split("\n"), 1)
        # Both quote styles — Jinja takes either, and this template
        # uses single quotes elsewhere (`:422`) — plus the ``%`` form.
        if re.search(
            r'''["']Instrument_["']\s*~|["']Instrument_%s["']|'''
            r'''Instrument_\{\{|Instrument #\{\{''',
            line,
        )
    ]
    assert offenders == [], offenders


# --------------------------------------------------------------------------- #
# Rung 3 — the card tint
# --------------------------------------------------------------------------- #


def _rendered_tints(body: str) -> list[int]:
    """The tint number of each instrument card, in render order.

    ``base.html`` declares the tokens as ``--surface-tint-N:`` and only a
    card's inline ``background`` *uses* one as ``var(--surface-tint-N)``,
    so this matches cards and nothing else.
    """
    import re

    return [int(n) for n in re.findall(r"var\(--surface-tint-(\d)\)", body)]


def test_the_tint_follows_the_number_on_the_card(
    client: TestClient, db: Session
) -> None:
    """Keyed on ``session_seq``, so the tint runs 1, 2, 3 down the page
    whatever the ids are — and means the number the title shows.

    Before rung 3 it was ``(instrument.id - 1) % 6``: a workspace-wide
    autoincrement, so ids 47, 48, 51 rendered tints 5, 6, 3.
    """
    review_session = _client_session(client, db, "tint-a")
    other = _client_session(client, db, "tint-b")
    op = db.execute(select(User)).scalars().first()
    crud.ensure_default_instrument(db, review_session)
    crud.ensure_default_instrument(db, other)
    # Interleaved, so the first session's ids are not contiguous.
    crud.create_instrument(db, review_session=other, actor=op)
    crud.create_instrument(db, review_session=review_session, actor=op)
    crud.create_instrument(db, review_session=other, actor=op)
    crud.create_instrument(db, review_session=review_session, actor=op)
    db.commit()

    ids = list(
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        ).scalars()
    )
    assert ids != list(range(ids[0], ids[0] + len(ids))), (
        "ids came out contiguous — the test would pass on the old keying too"
    )

    response = client.get(f"/operator/sessions/{review_session.id}/instruments")
    assert response.status_code == 200
    assert _rendered_tints(response.text) == [1, 2, 3]


def test_the_tint_does_not_move_when_the_operator_reorders(
    client: TestClient, db: Session
) -> None:
    """The property the display-position alternative could not give:
    dragging a card changes where it sits, not what colour it is."""
    from app.services import instruments as instruments_service

    review_session = _client_session(client, db, "tint-reorder")
    op = db.execute(select(User)).scalars().first()
    crud.ensure_default_instrument(db, review_session)
    crud.create_instrument(db, review_session=review_session, actor=op)
    db.commit()

    rows = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[r.id for r in reversed(rows)],
        actor=op,
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Render order is display order, so the tints arrive reversed —
    # each card kept its own colour rather than inheriting the slot's.
    assert _rendered_tints(body) == [2, 1]


def test_the_palette_wraps_past_six(client: TestClient, db: Session) -> None:
    """Six tints and an unbounded ordinal: instrument 7 shares
    instrument 1's colour, which is the documented cost of a palette
    rather than a key."""
    review_session = _client_session(client, db, "tint-wrap")
    op = db.execute(select(User)).scalars().first()
    crud.ensure_default_instrument(db, review_session)
    for _ in range(6):
        crud.create_instrument(db, review_session=review_session, actor=op)
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert _rendered_tints(body) == [1, 2, 3, 4, 5, 6, 1]


# --------------------------------------------------------------------------- #
# What the item's cumulative cold read found
# --------------------------------------------------------------------------- #


def test_a_trailing_delete_hands_the_number_back(db: Session) -> None:
    """The one case where the handle is not stable, pinned as it is.

    `max + 1` makes an interior delete safe and a trailing one not:
    delete the newest of 1, 2, 3 and the next created is 3 again. The
    sibling test above pins the interior case and passed while this
    one was unwritten, which is how the model docstring came to claim
    the sequence "never reuses a number".

    Recorded rather than fixed: a monotonic sequence needs a
    high-water mark the column does not keep, and adding one is the
    author's call (19Q Item 6, open question 1).
    """
    review_session, op = _session(db, "seq-trail")
    for _ in range(2):
        crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 2, 3]

    newest = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.session_seq == 3)
    ).scalar_one()
    crud.delete_instrument(db, instrument=newest, actor=op)
    db.flush()

    crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 2, 3], (
        "a trailing delete no longer hands the number back — if this is "
        "now monotonic, the model docstring and 19Q Item 6 need updating "
        "to say so"
    )


def test_the_sql_label_and_the_python_label_agree(db: Session) -> None:
    """The gate `_instrument_label_sql`'s docstring claimed to have.

    The Assignments page sorts by the SQL form and renders the Python
    one. They drifted at rung 2 — the SQL stayed on `id` — so the
    server ordered by a string the page no longer displayed, and with
    ids 9 and 47 the string collation inverts the visible order.
    """
    from sqlalchemy import select as sa_select

    from app.services.assignments._coverage import _instrument_label_sql
    from app.services.instruments import _instrument_label

    first, op = _session(db, "sqllbl-a")
    second, _ = _session(db, "sqllbl-b")
    crud.create_instrument(db, review_session=second, actor=op)
    crud.create_instrument(db, review_session=first, actor=op)
    db.flush()
    named = db.execute(
        select(Instrument).where(Instrument.session_id == first.id)
    ).scalars().first()
    named.short_label = "Peer feedback"
    db.flush()

    rows = db.execute(
        sa_select(Instrument, _instrument_label_sql(Instrument))
        .where(Instrument.session_id == first.id)
        .order_by(Instrument.id)
    ).all()
    assert rows, "no instruments — the comparison would be vacuous"
    for instrument, sql_label in rows:
        assert sql_label == _instrument_label(instrument)
    # And the fallback really is exercised, not just the short_label arm.
    assert any(lbl.startswith("Instrument_") for _, lbl in rows)
