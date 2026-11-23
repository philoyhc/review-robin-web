"""An exercise's form in the database (segment AD2D; rulings 15, 19 and
30; AD-45).

``parse`` checks Form's snapshot card by card, as the page sends it
(``applydeskFormSnapshot``). ``save`` replaces the form with it under the
exercise's lock (`panels_store.lock`, the one Panels and Process take),
guarded by ``exercise.form_revision``. ``load`` builds the pages' shape,
``sample_data.FormCard`` with its key, from the stored rows; None until
Form is first saved, so the pages keep the sample's.

Keys are ``q<n>``, minted here past every key the exercise has held,
retired ones and the sample's included, so a key is never given twice. A
card keeps the key it was sent with when the form it opened held it live;
any other (a new card, a page's placeholder) is given a fresh one. A
removed card is retired (ruling 74), and its key is never revived: a rule
naming it is refused, not re-pointed.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit, db, panels_store, sample_data
from applydesk.models import Exercise, Person
from applydesk.models import FormCard as CardRow
from applydesk.sample_data import FormCard

#: A form's cards, at most, and the widths of its text (Form's own checks
#: since AD1N, the columns' widths since AD2D).
MAX_CARDS = 200
MAX_TITLE = 200
MAX_DESCRIPTION = 4000
_KINDS = ("field", "section", "pagebreak")
_TEXT = {
    "label": 500,
    "help": 2000,
    "min": 40,
    "max": 40,
    "step": 40,
    "options": 2000,
    "ratio_w": 6,
    "ratio_h": 6,
    "pool": 80,
}
_FLAGS = ("exclusive", "required", "shown")


@dataclass(frozen=True)
class Form:
    """A form as the pages read it: its heading and its cards in order."""

    title: str
    description: str
    cards: tuple[FormCard, ...]


class Refused(Exception):
    """A save that cannot be kept, said to the operator; ``key`` names the
    kind of refusal for a caller that tells them apart."""

    def __init__(self, message: str, key: str = "refused") -> None:
        super().__init__(message)
        self.key = key


def _now() -> datetime:
    return datetime.now(UTC)


# --- Load ------------------------------------------------------------------


def _card(row: CardRow) -> FormCard:
    return FormCard(
        kind=row.kind,
        type=row.type,
        label=row.label,
        help=row.help,
        min=row.min,
        max=row.max,
        step=row.step,
        options=row.options,
        exclusive=row.exclusive,
        ratio_w=row.ratio_w,
        ratio_h=row.ratio_h,
        pool=row.pool,
        required=row.required,
        shown=row.shown,
        key=row.key,
    )


def load(session: Session, public_id: str) -> Form | None:
    """The form Form last saved, else None (never saved: the pages keep
    the sample's)."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None or exercise.form_revision < 1:
        return None
    rows = session.scalars(
        select(CardRow)
        .where(CardRow.exercise_id == exercise.id, CardRow.retired_at.is_(None))
        .order_by(CardRow.position)
    )
    return Form(
        exercise.form_title or "",
        exercise.form_description or "",
        tuple(_card(r) for r in rows),
    )


def stored(public_id: str) -> Form | None:
    """The form Form last saved, read in a session of its own (the readers
    in ``sample_data``, which no route hands a session); None if never
    saved."""
    session = db.new_session()
    try:
        return load(session, public_id)
    finally:
        session.close()


def revision(public_id: str) -> int:
    """How many times the exercise's form was saved: Form sends the one it
    opened at, and a save from an older one is refused."""
    session = db.new_session()
    try:
        found = session.scalar(
            select(Exercise.form_revision).where(Exercise.public_id == public_id)
        )
    finally:
        session.close()
    return found or 0


def _live_keys(session: Session, exercise: Exercise) -> set[str]:
    """The keys of the form a page opened: the stored form's, else the
    sample's."""
    stored_form = load(session, exercise.public_id)
    cards = (
        stored_form.cards
        if stored_form is not None
        else sample_data.sample_form(exercise.public_id)
    )
    return {c.key for c in cards if c.key}


def taken_keys(session: Session, exercise: Exercise) -> set[str]:
    """Every card key the exercise has held, retired ones and the sample's
    included: a new key is minted past them."""
    keys = {c.key for c in sample_data.sample_form(exercise.public_id)}
    keys |= set(session.scalars(select(CardRow.key).where(CardRow.exercise_id == exercise.id)))
    return keys


def _fresh(taken: set[str]) -> str:
    n = 1
    while f"q{n}" in taken:
        n += 1
    taken.add(f"q{n}")
    return f"q{n}"


# --- The page's snapshot, checked -------------------------------------------


def parse(sent: Any, pools: Collection[str], renamed: Mapping[str, str]) -> dict[str, Any]:
    """The form as Form's *Save* sends it, checked card by card and kept in
    ``FormCard``'s shape, each card with the key it was sent (blank for
    none); a panel the page made is named by the key ``renamed`` gives it,
    and a question chooses from ``pools`` or one of those."""
    if not isinstance(sent, dict):
        raise Refused("The form is malformed.")
    got = cast(dict[str, Any], sent)
    title, description, cards = got.get("title", ""), got.get("description", ""), got.get("cards")
    if (
        not isinstance(title, str)
        or not isinstance(description, str)
        or not isinstance(cards, list)
    ):
        raise Refused("The form is malformed.")
    if len(title.strip()) > MAX_TITLE:
        raise Refused(f"The form's title is at most {MAX_TITLE} characters.")
    if len(description.strip()) > MAX_DESCRIPTION:
        raise Refused(f"The form's description is at most {MAX_DESCRIPTION:,} characters.")
    if len(cast(list[Any], cards)) > MAX_CARDS:
        raise Refused(f"A form holds at most {MAX_CARDS} cards.")
    types = {k for k, _ in sample_data.CARD_TYPES}
    allowed = set(pools) | set(renamed.values())
    kept: list[dict[str, Any]] = []
    for n, raw in enumerate(cast(list[Any], cards), start=1):
        if not isinstance(raw, dict):
            raise Refused(f"Card {n} is malformed.")
        card = cast(dict[str, Any], raw)
        key = card.get("key", "")
        if not isinstance(key, str) or len(key) > 40:
            raise Refused(f"Card {n} is malformed.")
        kind = card.get("kind")
        # A string first: a list or object would fail ``in`` on a set
        # unhashable, a 500 (findings 2026-11-20 S9).
        if not isinstance(kind, str) or kind not in _KINDS:
            raise Refused(f"Card {n} is of no known kind.")
        if kind != "field":
            label = card.get("label", "")
            if not isinstance(label, str):
                raise Refused(f"Card {n} is malformed.")
            if len(label) > _TEXT["label"]:
                raise Refused(f"Card {n}'s label is too long.")
            kept.append({"kind": kind, "label": label, "key": key})
            continue
        if not isinstance(card.get("type"), str) or card.get("type") not in types:
            raise Refused(f"Card {n}'s type is not one of the choices.")
        out: dict[str, Any] = {"kind": "field", "type": card["type"], "key": key}
        for name, cap in _TEXT.items():
            value = card.get(name, "")
            if not isinstance(value, str) or len(value) > cap:
                raise Refused(f"Card {n}'s {name} is malformed or too long.")
            out[name] = value
        for name in _FLAGS:
            if not isinstance(card.get(name), bool):
                raise Refused(f"Card {n} is malformed.")
            out[name] = card[name]
        out["pool"] = out["pool"] or "institution"
        out["pool"] = renamed.get(out["pool"], out["pool"])
        if out["pool"] not in allowed:
            raise Refused(f"Card {n} chooses from no panel this exercise has.")
        out["ratio_w"] = out["ratio_w"] or "4"
        out["ratio_h"] = out["ratio_h"] or "5"
        kept.append(out)
    return {"title": title.strip(), "description": description.strip(), "cards": kept}


# --- Save ------------------------------------------------------------------


def _keyed(cards: list[dict[str, Any]], live: set[str], taken: set[str]) -> list[dict[str, Any]]:
    """Each card with its key: the one it was sent, if the form the page
    opened held it live and no earlier card took it; else a fresh one (a
    new card, a page's placeholder, a card copied with its key)."""
    used: set[str] = set()
    out: list[dict[str, Any]] = []
    for card in cards:
        key = card.get("key", "")
        if key not in live or key in used:
            key = _fresh(taken)
        used.add(key)
        out.append({**card, "key": key})
    return out


def _write(session: Session, exercise: Exercise, cards: list[dict[str, Any]]) -> dict[str, int]:
    """Make the stored rows say ``cards``, by key; whatever they drop is
    retired."""
    at = _now()
    rows = {
        r.key: r for r in session.scalars(select(CardRow).where(CardRow.exercise_id == exercise.id))
    }
    wanted = {c["key"] for c in cards}
    retired = 0
    for key, row in rows.items():
        if key not in wanted and row.retired_at is None:
            row.retired_at = at
            retired += 1
    for position, card in enumerate(cards):
        row = rows.get(card["key"])
        if row is None:
            row = CardRow(exercise_id=exercise.id, key=card["key"])
            session.add(row)
            rows[card["key"]] = row
        blank = FormCard(card["kind"])
        row.position, row.kind, row.retired_at = position, card["kind"], None
        row.label = card.get("label", "")
        for name in ("type", "help", "min", "max", "step", "options", "ratio_w", "ratio_h", "pool"):
            setattr(row, name, card.get(name, getattr(blank, name)))
        for name in _FLAGS:
            setattr(row, name, card.get(name, getattr(blank, name)))
    session.flush()
    fields = sum(1 for c in cards if c["kind"] == "field")
    return {"cards": len(cards), "fields": fields, "retired": retired}


def save(
    session: Session,
    public_id: str,
    form: dict[str, Any],
    opened: int,
    actor: Person | None,
    *,
    published: Callable[[], bool],
) -> int:
    """Keep ``form`` (``parse``'s) as the exercise's form, if no save came
    between (``opened``, the revision the page loaded) and the stage holding
    it is not ``published``; the new revision. Flushed, not committed: the
    caller's transaction holds the change and its audit. The exercise's
    lock is ``panels_store``'s, so a Panels save cannot retire a panel a
    question names in between; a caller that read the panels first took it
    already."""
    exercise = panels_store.lock(session, public_id)
    if exercise.archived_at is not None:
        raise Refused("Archived: restore it to change it.", key="archived")
    if published():  # read under the lock: a Process save before it is seen
        raise Refused(
            "Not saved: the form is published. Revert its stage on Process to change it.",
            key="published",
        )
    if opened != exercise.form_revision:
        raise Refused(
            "Not saved: Form was saved since this page opened. Reload to see it.", key="stale"
        )
    cards = _keyed(form["cards"], _live_keys(session, exercise), taken_keys(session, exercise))
    counts = _write(session, exercise, cards)
    exercise.form_title = form["title"] or None
    exercise.form_description = form["description"] or None
    exercise.form_revision += 1
    audit.write_event(
        session,
        event_type="exercise.form_saved",
        actor=actor,
        exercise=exercise,
        payload=audit.counts(**counts),
        context={"revision": exercise.form_revision},
    )
    session.flush()
    return exercise.form_revision
