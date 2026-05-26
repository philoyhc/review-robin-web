"""Band 1 persistence service for new-model instruments.

The new-model instrument card surfaces three Links in Band 1:

- **Link 1 — Pool of reviewers.** A list of rules over ``reviewer.*``
  / ``pair_context.*`` tag predicates.
- **Link 2 — Pool of those reviewed.** A list of rules over
  ``reviewee.*`` / ``pair_context.*`` tag predicates, including
  cross-side ``same_as`` / ``different_from`` operators that take a
  reviewer-side tag as operand.
- **Link 3 — Unit of review.** Individual vs Grouped + boundary
  tags. Link 3 is wired separately in
  :func:`app.services.instruments.set_unit_of_review` (it writes
  ``instruments.group_kind``); this module only handles Links 1 + 2.

Storage maps cleanly onto the existing rule engine + per-instrument
``session_rule_sets`` row:

- Each Link's rules become a ``COMPOSITE`` rule with the Link's
  ``AND`` / ``OR`` combinator, holding ``MATCH`` rules — one per
  filter row the operator authored.
- The two Composites are wrapped under the SessionRuleSet's outer
  ``ALL_OF`` combinator so Link 1 ∩ Link 2 semantics fall out for
  free (each Composite is on its own side of the predicate).
- A Link in "All" mode (no filtering) contributes no Composite —
  the empty rule list means the full matrix.

Hydration: :func:`decode_band1_state` reads the stored rules_json
back into the same shape the UI submits.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, object_session

from app.db.models import Instrument, SessionRuleSet, User
from app.services import audit
from app.services import session_lifecycle as lifecycle
from app.services.instruments._state import _instrument_label


# UI operator label → engine predicate operator.
_UI_TO_ENGINE_OP: dict[str, str] = {
    "IS": "equals",
    "IS NOT": "not_equals",
    "IS THE SAME AS": "same_as",
    "IS DIFFERENT FROM": "different_from",
}
_ENGINE_TO_UI_OP: dict[str, str] = {v: k for k, v in _UI_TO_ENGINE_OP.items()}
_TAG_OPERAND_OPS: frozenset[str] = frozenset({"same_as", "different_from"})


class Band1ParseError(ValueError):
    """Raised when a Band 1 form payload is malformed (mismatched
    array lengths, unknown operator, etc.)."""


def set_band1_assignment_rules(
    db: Session,
    *,
    instrument: Instrument,
    link1_mode: str,
    link1_combinator: str,
    link1_rules: list[dict[str, str]],
    link2_mode: str,
    link2_combinator: str,
    link2_rules: list[dict[str, str]],
    actor: User,
    touched_links: set[str] | None = None,
) -> Instrument:
    """Persist Band 1's two Link rule lists onto the instrument's
    pinned :class:`SessionRuleSet`. Materialises a fresh per-instrument
    row on first save; updates in place on subsequent saves.

    ``link1_mode`` / ``link2_mode`` is ``"all"`` or ``"filter"``. In
    ``"all"`` mode the Link contributes no rules regardless of the
    rule list contents. ``"filter"`` mode with an empty rule list
    folds back to ``"all"`` on storage (no Composite is emitted).

    Each rule dict has shape::

        {
            "field": "reviewer.tag1",
            "op": "IS" | "IS NOT" | "IS THE SAME AS" | "IS DIFFERENT FROM",
            "operand_value": "Lead",      # used when op is IS / IS NOT
            "operand_tag": "reviewee.tag1",  # used when op is IS THE SAME AS / IS DIFFERENT FROM
        }
    """
    rules_json = _build_rules_json(
        link1_mode=link1_mode,
        link1_combinator=link1_combinator,
        link1_rules=link1_rules,
        link2_mode=link2_mode,
        link2_combinator=link2_combinator,
        link2_rules=link2_rules,
    )

    _mark_touched_links(instrument, touched_links, {"link1", "link2"})

    rule_set = (
        db.get(SessionRuleSet, instrument.rule_set_id)
        if instrument.rule_set_id is not None
        else None
    )

    if rule_set is None:
        if not rules_json:
            return instrument
        rule_set = _create_band1_rule_set(
            db, instrument=instrument, rules_json=rules_json
        )
        instrument.rule_set_id = rule_set.id
        db.flush()
        lifecycle.invalidate_if_validated(
            db,
            review_session=instrument.session,
            user=actor,
            reason="instrument_band1_rules_updated",
        )
        audit.write_event(
            db,
            event_type="session_rule_set.created",
            summary=(
                f"Materialised Band 1 RuleSet for new-model instrument "
                f"{_instrument_label(instrument)}"
            ),
            actor_user_id=actor.id,
            session=instrument.session,
            payload=audit.snapshot(
                {
                    "id": rule_set.id,
                    "name": rule_set.name,
                    "combinator": rule_set.combinator,
                    "rule_count": len(rule_set.rules_json or []),
                }
            ),
            refs={
                "session_rule_set_id": rule_set.id,
                "instrument_id": instrument.id,
            },
        )
        return instrument

    # Normalise ``exclude_self_reviews=False`` on every update so
    # sessions whose SessionRuleSet was materialised before
    # PR #1452 (which flipped the default) heal the moment the
    # operator next saves Band 1. The per-instrument Self review
    # toggle on the Assignments page is the sole include / exclude
    # surface; baking exclusion in at the rule-set level would
    # silently disable that toggle.
    needs_self_review_fix = rule_set.exclude_self_reviews
    if (rule_set.rules_json or []) == rules_json and not needs_self_review_fix:
        return instrument

    prev_count = len(rule_set.rules_json or [])
    new_count = len(rules_json)
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_band1_rules_updated",
    )
    rule_set.rules_json = rules_json
    if needs_self_review_fix:
        rule_set.exclude_self_reviews = False
    db.flush()
    audit.write_event(
        db,
        event_type="session_rule_set.updated",
        summary=(
            f"Updated Band 1 rules on new-model instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id,
        session=instrument.session,
        payload=audit.changes(
            {
                "rules_edited": [True, True],
                "rule_count": [prev_count, new_count],
            }
        ),
        refs={
            "session_rule_set_id": rule_set.id,
            "instrument_id": instrument.id,
        },
    )
    return instrument


def decode_band1_state(instrument: Instrument, db: Session) -> dict[str, Any]:
    """Read the instrument's stored Band 1 state back into the same
    shape the UI submits. Returns ``{"link1": {...}, "link2": {...}}``
    with each link's ``mode`` / ``combinator`` / ``rules`` / ``touched``
    populated.

    ``touched`` is True iff the operator has previously clicked the
    link's pill into a set state (see ``instrument.band1_touched_links``).
    Untouched links render as the ``"Not set"`` pill state in the UI.
    """
    touched = set(instrument.band1_touched_links or [])
    state: dict[str, Any] = {
        "link1": _empty_link_state(touched=("link1" in touched)),
        "link2": _empty_link_state(touched=("link2" in touched)),
    }
    if instrument.rule_set_id is None:
        return state
    rule_set = db.get(SessionRuleSet, instrument.rule_set_id)
    if rule_set is None:
        return state
    for entry in rule_set.rules_json or []:
        if entry.get("kind") != "COMPOSITE":
            continue
        link_id = entry.get("id")
        if link_id not in ("link1", "link2"):
            continue
        target = state[link_id]
        target["mode"] = "filter"
        op = entry.get("op", "AND")
        target["combinator"] = "OR" if op == "OR" else "AND"
        target["rules"] = [
            _decode_match_rule(child)
            for child in entry.get("rules", [])
            if child.get("kind") == "MATCH"
        ]
    return state


def parse_band1_form(form: Any) -> dict[str, Any]:
    """Parse a Starlette ``FormData`` payload's Band 1 fields into the
    shape :func:`set_band1_assignment_rules` consumes. Missing fields
    default to "All" mode with no rules — the empty default.

    Raises :class:`Band1ParseError` if the parallel arrays for a link
    have mismatched lengths.
    """
    return {
        "link1_mode": _form_mode(form, "link1_mode"),
        "link1_combinator": _form_combinator(form, "link1_combinator"),
        "link1_rules": _form_rules(form, "link1"),
        "link2_mode": _form_mode(form, "link2_mode"),
        "link2_combinator": _form_combinator(form, "link2_combinator"),
        "link2_rules": _form_rules(form, "link2"),
        "touched_links": _form_touched_links(form, ("link1", "link2")),
    }


def parse_link3_form(
    form: Any,
) -> tuple[str, list[tuple[str, str]], bool]:
    """Parse Link 3 (Unit of review) from the form payload. Returns
    ``(mode, boundary_pairs, touched)`` where ``mode`` is
    ``"individual"`` or ``"grouped"``, ``boundary_pairs`` is the
    decoded list of ``(source_type, source_field)`` pairs (empty when
    mode is ``"individual"`` or grouped-with-no-boundary), and
    ``touched`` is True iff the operator clicked the Link 3 pill in
    this submit (carried via the ``link3_touched`` hidden input).
    """
    mode = str(form.get("link3_mode") or "individual").strip()
    if mode not in ("individual", "grouped"):
        mode = "individual"
    touched = _form_touched_links(form, ("link3",)) == {"link3"}
    if mode == "individual":
        return mode, [], touched
    pairs: list[tuple[str, str]] = []
    for raw in form.getlist("link3_boundary"):
        s = str(raw).strip()
        if not s:
            continue
        if "." not in s:
            continue
        source, _, slot = s.partition(".")
        if source not in ("reviewee", "pair_context"):
            continue
        if not slot.startswith("tag"):
            continue
        tag_num = slot[len("tag"):]
        if tag_num not in ("1", "2", "3"):
            continue
        pair = (source, f"tag_{tag_num}")
        if pair not in pairs:
            pairs.append(pair)
    return mode, pairs, touched


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _empty_link_state(*, touched: bool = False) -> dict[str, Any]:
    return {
        "mode": "all",
        "combinator": "AND",
        "rules": [],
        "touched": touched,
    }


def _mark_touched_links(
    instrument: Instrument,
    touched_links: set[str] | None,
    allowed: set[str],
) -> None:
    """Replace the ``allowed`` slice of
    ``instrument.band1_touched_links`` with ``touched_links`` (which
    must be a subset of ``allowed``). Links outside ``allowed`` —
    e.g. ``link3`` when this is called from ``set_band1_assignment_rules``
    (which only owns Link 1 + 2) — are left untouched so the two
    Band 1 writers don't clobber each other.

    ``touched_links=None`` is treated as the empty set (the operator
    cycled every owned pill back to "Not set"). The pill UI cycles
    "Not set" → "All" → "Filter using …" → "Not set" → …; once the
    operator returns a pill to "Not set" the link drops off the
    stored touched list, so the workflow card can re-surface the
    instrument as unconfigured.
    """
    incoming = {link for link in (touched_links or set()) if link in allowed}
    existing = set(instrument.band1_touched_links or [])
    merged = (existing - allowed) | incoming
    if merged == existing:
        return
    instrument.band1_touched_links = sorted(merged)
    object_session(instrument).flush()


def _form_touched_links(form: Any, keys: tuple[str, ...]) -> set[str]:
    touched: set[str] = set()
    for key in keys:
        raw = str(form.get(f"{key}_touched") or "").strip().lower()
        if raw in ("true", "1", "yes", "on"):
            touched.add(key)
    return touched


def _build_rules_json(
    *,
    link1_mode: str,
    link1_combinator: str,
    link1_rules: list[dict[str, str]],
    link2_mode: str,
    link2_combinator: str,
    link2_rules: list[dict[str, str]],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for link_id, mode, combinator, rules in (
        ("link1", link1_mode, link1_combinator, link1_rules),
        ("link2", link2_mode, link2_combinator, link2_rules),
    ):
        if mode != "filter":
            continue
        match_rules = [_build_match_rule(r, link_id, idx) for idx, r in enumerate(rules)]
        match_rules = [m for m in match_rules if m is not None]
        if not match_rules:
            continue
        op = "OR" if combinator == "OR" else "AND"
        payload.append(
            {
                "id": link_id,
                "enabled": True,
                "kind": "COMPOSITE",
                "op": op,
                "rules": match_rules,
            }
        )
    return payload


def _build_match_rule(
    rule_dict: dict[str, str], link_id: str, idx: int
) -> dict[str, Any] | None:
    ui_op = rule_dict.get("op", "").strip()
    engine_op = _UI_TO_ENGINE_OP.get(ui_op)
    if engine_op is None:
        return None
    field = rule_dict.get("field", "").strip()
    if not field:
        return None
    if engine_op in _TAG_OPERAND_OPS:
        operand = rule_dict.get("operand_tag", "").strip()
        if not operand:
            return None
    else:
        operand = rule_dict.get("operand_value", "").strip()
        if not operand:
            return None
    return {
        "id": f"{link_id}-r{idx}",
        "enabled": True,
        "kind": "MATCH",
        "predicate": {
            "field": field,
            "operator": engine_op,
            "operand": operand,
            "case_sensitive": False,
        },
    }


def _decode_match_rule(child: dict[str, Any]) -> dict[str, str]:
    predicate = child.get("predicate", {})
    engine_op = predicate.get("operator", "equals")
    ui_op = _ENGINE_TO_UI_OP.get(engine_op, "IS")
    operand = predicate.get("operand", "") or ""
    if engine_op in _TAG_OPERAND_OPS:
        return {
            "field": predicate.get("field", ""),
            "op": ui_op,
            "operand_value": "",
            "operand_tag": str(operand),
        }
    return {
        "field": predicate.get("field", ""),
        "op": ui_op,
        "operand_value": str(operand),
        "operand_tag": "",
    }


def _create_band1_rule_set(
    db: Session, *, instrument: Instrument, rules_json: list[dict[str, Any]]
) -> SessionRuleSet:
    name = _band1_rule_set_name(db, instrument)
    rule_set = SessionRuleSet(
        session_id=instrument.session_id,
        name=name,
        description=(
            f"Auto-managed by Band 1 of new-model instrument "
            f"#{instrument.id}."
        ),
        combinator="ALL_OF",
        # Align with the synthetic Full Matrix default
        # (assignments._full_matrix_schema) so self-review pairs
        # materialise as assignment rows on every Band 1 instrument.
        # The per-instrument "Self review" toggle on the Assignments
        # page is the operator's include / exclude surface; baking
        # exclusion in at the rule-set level would silently disable
        # that toggle.
        exclude_self_reviews=False,
        seed=None,
        rules_json=rules_json,
    )
    db.add(rule_set)
    db.flush()
    return rule_set


def _band1_rule_set_name(db: Session, instrument: Instrument) -> str:
    """Compose a per-instrument SessionRuleSet name unique within the
    session. The base name is stable across edits (the same
    instrument always points at the same row); collisions only happen
    if a non-new-model RuleSet already carries the same name."""
    base = f"New-model instrument #{instrument.id} Band 1"
    candidate = base
    suffix = 2
    while _name_exists_in_session(
        db, session_id=instrument.session_id, name=candidate
    ):
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


def _name_exists_in_session(db: Session, *, session_id: int, name: str) -> bool:
    return (
        db.execute(
            SessionRuleSet.__table__.select()
            .where(SessionRuleSet.session_id == session_id)
            .where(SessionRuleSet.name == name)
        ).first()
        is not None
    )


def _form_mode(form: Any, key: str) -> str:
    raw = str(form.get(key) or "all").strip().lower()
    return "filter" if raw == "filter" else "all"


def _form_combinator(form: Any, key: str) -> str:
    raw = str(form.get(key) or "AND").strip().upper()
    return "OR" if raw == "OR" else "AND"


def _form_rules(form: Any, link_prefix: str) -> list[dict[str, str]]:
    fields = [str(v) for v in form.getlist(f"{link_prefix}_field")]
    ops = [str(v) for v in form.getlist(f"{link_prefix}_op")]
    operand_values = [
        str(v) for v in form.getlist(f"{link_prefix}_operand_value")
    ]
    operand_tags = [str(v) for v in form.getlist(f"{link_prefix}_operand_tag")]
    n = len(fields)
    if not (len(ops) == n and len(operand_values) == n and len(operand_tags) == n):
        raise Band1ParseError(
            f"Band 1 {link_prefix} arrays misaligned: "
            f"fields={len(fields)}, ops={len(ops)}, "
            f"operand_values={len(operand_values)}, "
            f"operand_tags={len(operand_tags)}"
        )
    return [
        {
            "field": fields[i],
            "op": ops[i],
            "operand_value": operand_values[i],
            "operand_tag": operand_tags[i],
        }
        for i in range(n)
    ]


def find_sample_in_scope_reviewee(
    db: Session,
    *,
    instrument: Instrument,
    link1_mode: str,
    link1_combinator: str,
    link1_rules: list[dict[str, str]],
    link2_mode: str,
    link2_combinator: str,
    link2_rules: list[dict[str, str]],
) -> tuple[Any, list[int] | None] | None:
    """Run the rule engine with the given Band 1 + Link 2 inputs and
    return both the sample reviewee and the rule-surviving group
    member IDs that share its reviewee-side boundary key — the
    Band 2 preview's "Refresh" button consumes this so the Grouped-
    mode preview's member list is honest about Links 1+2 filtering
    (Segment 18J Wave 1 Gap 10).

    Returns ``(reviewee, member_ids)`` where:

    - ``reviewee`` is the first matched pair's reviewee (an ORM
      ``Reviewee`` instance);
    - ``member_ids`` is the sorted list of unique reviewee IDs
      whose surviving pairs share the sample's reviewee-side
      boundary key, or ``None`` when the instrument has no
      reviewee-side boundary (per-reviewee mode, or grouped-by-
      pair-context-only — the render path falls back to its
      pre-Gap-10 unconstrained partition for those cases).

    Returns ``None`` when the rules narrow the candidate pair space
    down to zero. The roster bytes loaded here are the same set the
    actual assignment generator uses, so the picked sample is one
    the operator's reviewers would really see when generation runs.
    """
    # Local imports to avoid pulling the rule engine + roster
    # primitives at module-load time (this module is imported during
    # every operator request, the engine + roster only when the
    # operator clicks Refresh).
    from sqlalchemy import select as sa_select

    from app.db.models import Relationship, Reviewee, Reviewer
    from app.schemas.rules import Combinator, RuleSetOptions, RuleSetSchema
    from app.services.rules import engine

    review_session = instrument.session
    reviewers = list(
        db.execute(
            sa_select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.name, Reviewer.id)
        ).scalars()
    )
    reviewees = list(
        db.execute(
            sa_select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .where(Reviewee.status == "active")
            .order_by(Reviewee.name, Reviewee.id)
        ).scalars()
    )
    if not reviewers or not reviewees:
        return None
    pair_context_lookup = {
        (r.reviewer_id, r.reviewee_id): r
        for r in db.execute(
            sa_select(Relationship)
            .where(Relationship.session_id == review_session.id)
            .where(Relationship.status == "active")
        ).scalars()
    }
    rules_json = _build_rules_json(
        link1_mode=link1_mode,
        link1_combinator=link1_combinator,
        link1_rules=link1_rules,
        link2_mode=link2_mode,
        link2_combinator=link2_combinator,
        link2_rules=link2_rules,
    )
    # Build a temp RuleSetSchema directly from the JSON payload so
    # we evaluate exactly the Link 1 + Link 2 the operator has on
    # screen (not whatever's persisted on the SessionRuleSet row).
    from pydantic import TypeAdapter

    from app.schemas.rules import Rule

    rule_adapter = TypeAdapter(Rule)
    try:
        rules = [rule_adapter.validate_python(payload) for payload in rules_json]
    except Exception:
        return None
    schema = RuleSetSchema(
        name="_band1_preview",
        combinator=Combinator.ALL_OF,
        rules=rules,
        options=RuleSetOptions(excludeSelfReviews=True),
    )
    try:
        result = engine.evaluate(
            schema,
            reviewers=reviewers,
            reviewees=reviewees,
            pair_context_lookup=pair_context_lookup,
        )
    except Exception:
        return None
    if not result.pairs:
        return None
    # Gap 10: compute rule-surviving group member IDs for the
    # sample's reviewee-side boundary key. Skipped when there's no
    # reviewee-side boundary (per-reviewee mode or grouped-by-
    # pair-context-only) — render falls back to its existing
    # unconstrained partition. Iterates result.pairs the engine
    # already produced; no second engine call.
    from app.services.instruments._instrument_crud import decode_group_kind

    reviewee_boundary_fields = [
        field
        for (src, field) in decode_group_kind(instrument.group_kind)
        if src == "reviewee"
    ]
    if not reviewee_boundary_fields:
        # Default sample = first surviving pair's reviewee.
        return result.pairs[0][1], None

    def _key_of(rev: Any) -> tuple[str, ...]:
        return tuple(
            (getattr(rev, field, "") or "") for field in reviewee_boundary_fields
        )

    # Member-ID computation is scoped to one reviewer's pool.
    # Pre-2026-05-26 ``find_sample_in_scope_reviewee`` walked every
    # ``(reviewer, reviewee)`` pair the engine produced and collected
    # reviewees whose boundary key matched the sample. That widened
    # the set when boundary tag values repeat across reviewer pools
    # (e.g. tutorial-group → team setup where "Team 1" exists in
    # every tutorial group). The reviewer surface narrows correctly
    # because each reviewer's collapse uses only their own pairs;
    # mirror that here by anchoring on a single sample reviewer.
    sample_reviewer, sample_reviewee = result.pairs[0]
    sample_key = _key_of(sample_reviewee)
    member_ids: set[int] = set()
    for r, e in result.pairs:
        if r.id != sample_reviewer.id:
            continue
        if _key_of(e) == sample_key:
            member_ids.add(e.id)
    return sample_reviewee, sorted(member_ids)
