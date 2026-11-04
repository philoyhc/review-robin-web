"""The Band 1 card's preview: which reviewee to show as a sample in
scope, and the group boundary and self-review exclusion it previews
with (segment 20E rung 4, moved unchanged from ``_band1.py``). Reads
nothing but the rules it is given; ``_band1`` never imports it.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.db.models import Instrument, SessionRuleSet
from app.services.instruments._band1 import _build_rules_json


def _preview_group_boundary(
    instrument: Instrument, link3_boundary: list[str] | None
) -> list[tuple[str, str]]:
    """The FULL decoded group boundary the preview should group by —
    reviewee tags **and** pair-context tags, in the shape
    ``group_key_for_pair`` expects.

    Distinct from ``reviewee_boundary_fields``, which is deliberately
    reviewee-only because it drives the member-id partition. Grouping
    for self-review exclusion has to match the generator exactly or the
    preview shows samples Generate will not produce.

    Live ``link3_boundary`` (canonical keys like ``"pair_context.tag2"``)
    wins when the Refresh handler supplies it, falling back to the
    persisted ``group_kind`` — the same precedence the rest of this
    function uses.
    """
    from app.services.instruments._instrument_crud import decode_group_kind

    if link3_boundary is None:
        return decode_group_kind(instrument.group_kind)
    boundary: list[tuple[str, str]] = []
    for raw in link3_boundary:
        source, _, slot = raw.strip().partition(".")
        if not slot.startswith("tag"):
            continue
        num = slot[len("tag") :]
        if num not in {"1", "2", "3"}:
            continue
        if source == "reviewee":
            pair = ("reviewee", f"tag_{num}")
        elif source == "pair_context":
            # ``group_key_for_pair`` takes the bare slot number for
            # pair-context and derives ``tag_N`` itself.
            pair = ("pair_context", num)
        else:
            continue
        if pair not in boundary:
            boundary.append(pair)
    return boundary


def _preview_excludes_self_reviews(
    db: Session, instrument: Instrument
) -> bool:
    """Whether the Band 2 preview should drop self-reviews for this
    instrument — i.e. whether its pinned rule set carries
    ``exclude_self_reviews`` (19O Item 1).

    Reads the PERSISTED flag rather than a form field: the Link 3
    checkbox is not among the inputs the Refresh handler posts, so an
    unsaved tick is not reflected until the card is saved. Only the
    flag is persisted: Links 1-2, the boundary and the Individual /
    Group pill all come from the live edit.
    """
    if instrument.rule_set_id is None:
        return False
    rule_set = db.get(SessionRuleSet, instrument.rule_set_id)
    return bool(rule_set is not None and rule_set.exclude_self_reviews)


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
    link3_boundary: list[str] | None = None,
    link3_mode: str | None = None,
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
      boundary key; for a pair-context-only boundary, or a group
      instrument with no boundary, the sample reviewer's surviving
      reviewees (A5, A4 — the preview does not partition on
      pair-context tags, and with no boundary the reviewer's
      survivors are the one group); ``None`` for a per-reviewee
      instrument, whose render keeps its unconstrained list. Grouped
      or per-reviewee is the posted ``link3_mode`` (the live pill),
      else the saved ``group_kind``.

    Returns ``None`` when the rules narrow the candidate pair space
    down to zero. Samples are drawn from active reviewees only, so the
    picked sample is one the operator's reviewers would really see
    when generation runs; self-review group membership is read off the
    whole roster, as the generator reads it.
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
    # The whole reviewee roster decides self-review group membership
    # below, as it does in Generate; only the active reviewees are
    # offered to the engine as samples.
    roster_reviewees = list(
        db.execute(
            sa_select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .order_by(Reviewee.name, Reviewee.id)
        ).scalars()
    )
    reviewees = [e for e in roster_reviewees if e.status == "active"]
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
        # Project-wide policy: ``excludeSelfReviews`` is ALWAYS
        # ``False`` at the DESUGAR stage — here as in assignments
        # generation. Excluding at this stage drops pairs before
        # group composition is known, which silently undercounts a
        # team by one on every symmetric session
        # (``spec/assignments.md`` "Self-review policy").
        #
        # The instrument's own ``exclude_self_reviews`` flag is
        # honored below instead, AFTER the fan-out, where whole
        # groups can be recognized — the same placement the
        # generator uses (19O Item 1).
        options=RuleSetOptions(excludeSelfReviews=False),
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

    # ``pairs`` rather than ``result.pairs`` from here down: the
    # self-review filter below narrows it, and everything after must
    # see the narrowed set (the sample pick AND the member-id scan).
    # The engine hands back the roster rows it was given.
    pairs = cast(list[tuple[Reviewer, Reviewee]], list(result.pairs))

    # The boundary fields are needed BEFORE the sample is picked now,
    # because self-review exclusion is whole-group and the group key
    # is built from them. (They are also used further down, for the
    # sample's member ids.)
    from app.services.instruments._instrument_crud import decode_group_kind

    if link3_boundary is not None:
        reviewee_boundary_fields: list[str] = []
        for raw in link3_boundary:
            v = raw.strip()
            if not v.startswith("reviewee.tag"):
                continue
            num = v[len("reviewee.tag") :]
            if num in {"1", "2", "3"}:
                field = f"tag_{num}"
                if field not in reviewee_boundary_fields:
                    reviewee_boundary_fields.append(field)
    else:
        reviewee_boundary_fields = [
            field
            for (src, field) in decode_group_kind(instrument.group_kind)
            if src == "reviewee"
        ]

    # Grouped or per-reviewee: the live Link 3 pill the Refresh posts,
    # else the saved instrument (A4). Both the self-review filter and
    # the member-id set below read it, so neither follows a unit of
    # review the other does not (Ac1).
    grouped = (
        link3_mode == "grouped"
        if link3_mode is not None
        else instrument.group_kind is not None
    )

    # 19O Item 1 — the preview follows the instrument's self-review
    # rule (author, 2026-09-14). Applied to the engine's OUTPUT, not
    # to its options: on a grouped instrument a reviewer who is one of
    # their own group's reviewees makes the whole group a self-review,
    # so every pair in it goes, not just the ``(R, R)`` one.
    #
    # **Keyed exactly as the generator keys it** — ``group_key_for_pair``
    # over the FULL decoded boundary, pair-context tags included. The
    # reviewee-only ``reviewee_boundary_fields`` above is the right key
    # for the member-id partition further down and the wrong one here:
    # a pair-context-only boundary (``group_kind="p1"``) leaves it
    # empty, which would drop this to a pair-level test while the
    # generator still groups — so the preview would offer a teammate
    # Generate is about to exclude. A mixed boundary (``"r1,p1"``) fails
    # the other way, merging groups the generator keeps apart. Two
    # keyings of one concept is one too many.
    if _preview_excludes_self_reviews(db, instrument):
        from app.services.assignments import is_self_review
        from app.services.responses import group_key_for_pair

        full_boundary = _preview_group_boundary(instrument, link3_boundary)

        def _group_key(r: Any, e: Any) -> tuple[str, ...]:
            return group_key_for_pair(
                reviewee=e,
                reviewer_id=r.id,
                reviewee_id=e.id,
                boundary=full_boundary,
                pair_context_lookup=pair_context_lookup,
            )

        if grouped:
            # Membership from the roster, not from the surviving pairs,
            # as Generate reads it (``_generate._diff_one_instrument``):
            # a Link rule, or an inactive reviewee row, can take the
            # ``(R, R)`` pair out of ``pairs`` while the reviewer's
            # group-mates stay, and the group is still the reviewer's
            # own. Candidates are narrowed by normalized address or by
            # directory account (segment 21F: Jane by UPN on one roster,
            # by mail on the other), and ``is_self_review`` still decides
            # each one.
            from app.services.email_identity import normalize_email, normalize_object_id

            by_address: dict[str, list[Any]] = {}
            by_account: dict[str, list[Any]] = {}
            for e in roster_reviewees:
                by_address.setdefault(
                    normalize_email(e.email_or_identifier), []
                ).append(e)
                if e.directory_object_id:
                    by_account.setdefault(
                        normalize_object_id(e.directory_object_id), []
                    ).append(e)
            from app.services.responses import is_catch_all_key

            def _candidates(r: Any) -> list[Any]:
                found = by_address.get(normalize_email(r.email), [])
                if r.directory_object_id:
                    found = found + by_account.get(
                        normalize_object_id(r.directory_object_id), []
                    )
                return found

            self_groups = {
                (r.id, _group_key(r, e))
                for r in reviewers
                for e in _candidates(r)
                if is_self_review(r, e)
                and not is_catch_all_key(_group_key(r, e))
            }
            pairs = [
                (r, e)
                for r, e in pairs
                if (r.id, _group_key(r, e)) not in self_groups
            ]
        else:
            pairs = [(r, e) for r, e in pairs if not is_self_review(r, e)]
        if not pairs:
            return None

    sample_reviewer, reviewee = pairs[0]
    # Gap 10: compute rule-surviving group member IDs for the
    # sample's reviewee-side boundary key. A pair-context-only
    # boundary, and a group instrument with no boundary, take the
    # sample reviewer's survivors instead (A5, A4); a per-reviewee
    # instrument returns None and render keeps its unconstrained
    # list. Iterates the pairs the engine already produced; no
    # second engine call.
    #
    # ``link3_boundary`` is the live Band 1 boundary list (canonical
    # keys like ``"reviewee.tag3"``) — the operator's in-progress
    # edit, posted by the Refresh handler. Falls back to the
    # persisted ``instrument.group_kind`` when None so callers that
    # don't supply it (older / non-Refresh paths) keep their old
    # behaviour.
    if not grouped:
        # Per-reviewee, by the live pill or the saved instrument: no
        # group, whatever boundary selects the card still posts.
        return reviewee, None
    if not reviewee_boundary_fields:
        # A pair-context-only boundary (A5, ruled 2026-10-06): the
        # partition needs a reviewer's relationship tags, so the preview
        # does not split on it. A group instrument with no boundary
        # (A4, ruled 2026-10-08) groups each reviewer's reviewees as
        # one, as ``group_key_for_pair`` does with an empty boundary.
        # Both honour Links 1-2: the group is the sample reviewer's
        # surviving reviewees.
        return reviewee, sorted(
            {e.id for r, e in pairs if r.id == sample_reviewer.id}
        )
    sample_key = tuple(
        getattr(reviewee, field, "") or ""
        for field in reviewee_boundary_fields
    )
    # Scope member-IDs to pairs involving the SAMPLE REVIEWER, not
    # every reviewer in the surviving set. The Band 2 preview
    # represents what *one* reviewer sees on their review surface;
    # if Link 2 uses an "IS THE SAME AS" predicate (e.g. Reviewee
    # group same as Reviewer group), each reviewer's reviewee pool
    # is different, and unioning across reviewers silently widens
    # the preview past what the sample's reviewer actually sees.
    #
    # The rule engine runs with ``excludeSelfReviews=False`` (the
    # project-wide policy — see ``spec/assignments.md`` "Self-
    # review policy"), so the sample reviewer's reviewee-side twin
    # (when one exists, matched by email) lands in the fan-out
    # naturally as ``(sample_reviewer, twin)`` and is counted here —
    # unless the instrument's own rule excluded it above, in which
    # case the whole group went with it and this sample is from a
    # different group.
    member_ids: set[int] = set()
    for r, e in pairs:
        if r.id != sample_reviewer.id:
            continue
        if (
            tuple(getattr(e, field, "") or "" for field in reviewee_boundary_fields)
            == sample_key
        ):
            member_ids.add(e.id)
    return reviewee, sorted(member_ids)
