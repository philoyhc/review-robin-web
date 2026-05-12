"""Rule Builder page (Segment 13A-1) and the Rule-Based generate
action that runs from the Assignments hub. Slice 8 of the major
refactor.

Note: although ``rule_based_generate`` lives at
``/assignments/rule-based/generate`` and the editor / copy / save /
delete routes live at ``/assignments/rule-based-editor/...``, both
URL families are Rule Builder territory — the Assignments slice
(PR 4) covers manual + full-matrix + delete-all only.

Source range in pre-refactor ``routes_operator.py``: 1345-2014.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, RuleSet, User
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.services import assignments, relationships as relationships_service
from app.services.rules import engine, library, session_library
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _require_editable,
    _require_response_loss_ack,
    _templates,
)


router = APIRouter()


@router.get(
    "/sessions/{session_id}/assignments/rule-based-editor",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_builder_page(
    request: Request,
    rule_set_id: int | None = Query(default=None),
    new: int | None = Query(default=None),
    draft_from: int | None = Query(default=None),
    previous_id: int | None = Query(default=None),
    error: str | None = Query(default=None),
    saved: int | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Segment 13A-1 — single-card Rule Builder page.

    Selection comes in via the optional ``rule_set_id`` query param;
    ``?new=1`` selects the blank-draft sentinel; ``?draft_from=<id>``
    renders an unsaved draft cloning that source's rules (the Copy
    flow). Stale / non-visible ids fall back to the first seed —
    refresh always renders rather than 404, since the URL bar is
    intentionally clean of selection state. PR 3 wires the
    blank-sentinel branch live.
    """

    if new == 1:
        selected_id: int | None = views.RULE_BUILDER_BLANK_SENTINEL_ID
    else:
        selected_id = rule_set_id

    context = views.build_rule_builder_context(
        review_session,
        db=db,
        user=user,
        selected_id=selected_id,
        as_draft_from=draft_from,
        previous_id=previous_id,
        error_kind=error,
        saved_flash=(saved == 1),
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_rule_builder.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "builder": context,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Rule Builder"
            ),
        },
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based-editor/copy",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_builder_copy(
    from_rule_set_id: int = Form(...),
    previous_id: int | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Segment 13A-1 PR 2 — Copy from seed/Personal.

    Per locked decision #3 the result is an *unsaved draft*: the row
    isn't created until Save (Save-As semantics). We 303 to the page
    URL with ``?draft_from=<id>`` so the GET handler renders the
    draft state, the operator can edit, and refresh re-renders the
    same draft from source rather than re-POSTing.
    """


    base_url = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )

    loaded = library.load_rule_set(db, from_rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=base_url, status_code=status.HTTP_303_SEE_OTHER
        )
    source_rule_set, _ = loaded
    if (
        not source_rule_set.is_seed
        and source_rule_set.owner_user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    redirect = f"{base_url}?draft_from={from_rule_set_id}"
    if previous_id is not None and previous_id > 0:
        redirect = f"{redirect}&previous_id={previous_id}"
    return RedirectResponse(
        url=redirect, status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based-editor/save",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_builder_save(
    request: Request,
    rule_set_id: int | None = Form(default=None),
    source_rule_set_id: int | None = Form(default=None),
    name: str = Form(...),
    description: str | None = Form(default=None),
    combinator: str = Form(...),
    rules_json: str = Form(...),
    exclude_self_reviews: str | None = Form(default=None),
    seed: str | None = Form(default=None),
    auto_name: str | None = Form(default=None),
    is_blank_draft: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Segment 13A-1 PR 2 / PR 3 — Save.

    Three branches:
    - ``rule_set_id`` set → in-place revision write on a Personal
      RuleSet owned by the caller. Mirrors the existing
      ``/rule-based/save`` route.
    - ``rule_set_id`` unset + ``source_rule_set_id`` set → Save-As
      from an unsaved Copy draft. Creates a new Personal RuleSet
      from the form's edited tree, pinning provenance to the
      source. ``auto_name=true`` opts into the auto-suffix on
      collision per locked decision #5 — operator-edited names get
      a 422 instead.
    - ``rule_set_id`` unset + ``is_blank_draft=true`` → Save from
      the blank-draft sentinel (PR 3). Creates a new Personal
      RuleSet with no provenance source. Server-side gate: the
      rules list must be non-empty (locked decision #8).
    """

    import json as _json

    from pydantic import ValidationError

    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetSchema,
    )

    base_url = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )

    cleaned_name = name.strip()
    blank_draft = is_blank_draft == "true" and rule_set_id is None

    def _redirect_back(
        error: str,
        *,
        draft: bool = False,
        draft_source: int | None = None,
        blank: bool = False,
    ) -> RedirectResponse:
        target = base_url
        if blank:
            target = f"{base_url}?new=1&error={error}"
        elif draft and draft_source is not None:
            target = f"{base_url}?draft_from={draft_source}&error={error}"
        elif rule_set_id is not None:
            target = f"{base_url}?rule_set_id={rule_set_id}&error={error}"
        else:
            target = f"{base_url}?error={error}"
        return RedirectResponse(
            url=target, status_code=status.HTTP_303_SEE_OTHER
        )

    is_draft = rule_set_id is None

    if not cleaned_name:
        return _redirect_back(
            "empty_name",
            draft=is_draft,
            draft_source=source_rule_set_id,
            blank=blank_draft,
        )
    if combinator not in {c.value for c in Combinator}:
        return _redirect_back(
            "bad_combinator",
            draft=is_draft,
            draft_source=source_rule_set_id,
            blank=blank_draft,
        )

    seed_value: int | None = None
    if seed is not None and seed.strip():
        try:
            seed_value = int(seed.strip())
        except ValueError:
            return _redirect_back(
                "bad_seed",
                draft=is_draft,
                draft_source=source_rule_set_id,
                blank=blank_draft,
            )

    try:
        parsed_rules = _json.loads(rules_json)
    except _json.JSONDecodeError:
        return _redirect_back(
            "malformed_json",
            draft=is_draft,
            draft_source=source_rule_set_id,
            blank=blank_draft,
        )
    if not isinstance(parsed_rules, list):
        return _redirect_back(
            "malformed_json",
            draft=is_draft,
            draft_source=source_rule_set_id,
            blank=blank_draft,
        )

    if blank_draft:
        # Server-side gate: a blank-draft Save must carry at least
        # one rule (locked decision #8). The client-side JS in
        # ``_rule_builder_card.html`` keeps the Save button disabled
        # until the indent-stack serialiser reports ≥1 row, so this
        # branch only fires for crafted POSTs / no-JS clients.
        if not parsed_rules:
            return _redirect_back("empty_rules", blank=True)

        final_name = _resolve_save_as_name(
            db,
            user=user,
            requested_name=cleaned_name,
            # The blank-draft default is the literal "New RuleSet"
            # — auto-suffix on collision to mirror the Copy flow.
            source_default="New RuleSet",
            auto_suffix=True,
        )
        if final_name is None:
            return _redirect_back("name_collision", blank=True)

        cleaned_description = (description or "").strip()

        try:
            rule_set_schema = RuleSetSchema(
                id=None,
                name=final_name,
                description=cleaned_description,
                scope="personal",  # type: ignore[arg-type]
                combinator=Combinator(combinator),
                rules=parsed_rules,  # type: ignore[arg-type]
                options=RuleSetOptions(
                    excludeSelfReviews=(exclude_self_reviews == "true"),
                    seed=seed_value,
                ),
            )
        except ValidationError:
            return _redirect_back("validation", blank=True)

        new_rule_set = library.save_as_rule_set_from_schema(
            db,
            rule_set_schema=rule_set_schema,
            owner=user,
            new_name=final_name,
            # No source — this is a from-scratch RuleSet.
            source_rule_set_id=None,
            source_revision_id=None,
            correlation_id=request_correlation_id(),
        )
        return RedirectResponse(
            url=f"{base_url}?rule_set_id={new_rule_set.id}&saved=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if is_draft:
        # Save-As from a Copy draft. Source must exist + be visible.
        if source_rule_set_id is None:
            return _redirect_back(
                "validation", draft=True, draft_source=None
            )
        loaded = library.load_rule_set(db, source_rule_set_id)
        if loaded is None:
            return RedirectResponse(
                url=base_url, status_code=status.HTTP_303_SEE_OTHER
            )
        source_rule_set, source_revision = loaded
        if (
            not source_rule_set.is_seed
            and source_rule_set.owner_user_id != user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="That RuleSet is private to its owner.",
            )

        # Auto-suffix when the operator hasn't edited the literal
        # ``Copy of <source>`` default and the name collides with a
        # caller-owned Personal RuleSet (locked decision #5).
        final_name = _resolve_save_as_name(
            db,
            user=user,
            requested_name=cleaned_name,
            source_default=f"Copy of {source_rule_set.name}",
            auto_suffix=(auto_name == "true"),
        )
        if final_name is None:
            return _redirect_back(
                "name_collision",
                draft=True,
                draft_source=source_rule_set_id,
            )

        cleaned_description = (description or "").strip()

        try:
            rule_set_schema = RuleSetSchema(
                id=None,
                name=final_name,
                description=cleaned_description,
                scope="personal",  # type: ignore[arg-type]
                combinator=Combinator(combinator),
                rules=parsed_rules,  # type: ignore[arg-type]
                options=RuleSetOptions(
                    excludeSelfReviews=(exclude_self_reviews == "true"),
                    seed=seed_value,
                ),
            )
        except ValidationError:
            return _redirect_back(
                "validation",
                draft=True,
                draft_source=source_rule_set_id,
            )

        new_rule_set = library.save_as_rule_set_from_schema(
            db,
            rule_set_schema=rule_set_schema,
            owner=user,
            new_name=final_name,
            source_rule_set_id=source_rule_set.id,
            source_revision_id=source_revision.id,
            correlation_id=request_correlation_id(),
        )
        return RedirectResponse(
            url=f"{base_url}?rule_set_id={new_rule_set.id}&saved=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # In-place save on a saved Personal RuleSet.
    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=base_url, status_code=status.HTTP_303_SEE_OTHER
        )
    rule_set, _ = loaded
    if rule_set.is_seed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seeded RuleSets are read-only.",
        )
    if rule_set.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    # Inline rename via the name field — Save commits the edited
    # name when it's changed. Collision check excludes the row
    # being saved so re-saving with the same name no-ops cleanly.
    if cleaned_name != rule_set.name and _name_taken_by_other(
        db,
        user=user,
        candidate_name=cleaned_name,
        exclude_id=rule_set.id,
    ):
        return _redirect_back("name_collision")

    if cleaned_name != rule_set.name:
        rule_set.name = cleaned_name

    # Description is editable via the inline textarea on the card.
    # ``None`` means the form didn't carry a description field (older
    # client / crafted POST) — leave the existing description in
    # place rather than blanking it.
    if description is not None:
        cleaned_description = description.strip()
        if cleaned_description != (rule_set.description or ""):
            rule_set.description = cleaned_description

    try:
        rule_set_schema = RuleSetSchema(
            id=rule_set.id,
            name=cleaned_name,
            description=rule_set.description or "",
            scope="personal",  # type: ignore[arg-type]
            combinator=Combinator(combinator),
            rules=parsed_rules,  # type: ignore[arg-type]
            options=RuleSetOptions(
                excludeSelfReviews=(exclude_self_reviews == "true"),
                seed=seed_value,
            ),
        )
    except ValidationError:
        return _redirect_back("validation")

    library.save_in_place(
        db,
        rule_set=rule_set,
        rule_set_schema=rule_set_schema,
        actor=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"{base_url}?rule_set_id={rule_set.id}&saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based-editor/delete",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_builder_delete(
    rule_set_id: int = Form(...),
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Segment 13A-1 PR 2 — Soft-delete a Personal RuleSet.

    Mirrors the existing ``/rule-based/delete`` route. After delete
    the redirect drops back to the bare page URL so the GET handler
    falls through to the first-seed default — locked decision says
    "reloads the next-visible RuleSet (first seed fallback)"."""


    base_url = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )

    if confirm != "true":
        return RedirectResponse(
            url=f"{base_url}?rule_set_id={rule_set_id}"
            "&error=needs_delete_confirm",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=base_url, status_code=status.HTTP_303_SEE_OTHER
        )
    rule_set, _ = loaded
    if rule_set.is_seed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seeded RuleSets are read-only.",
        )
    if rule_set.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    library.soft_delete_rule_set(
        db,
        rule_set=rule_set,
        actor=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=base_url, status_code=status.HTTP_303_SEE_OTHER
    )


def _resolve_save_as_name(
    db: Session,
    *,
    user: User,
    requested_name: str,
    source_default: str,
    auto_suffix: bool,
) -> str | None:
    """Resolve the final name for a Save-As / Copy-then-Save flow.

    When ``auto_suffix`` is True and ``requested_name`` is the
    literal source-derived default (``"Copy of <source>"``), append
    ``" (n)"`` until a free name is found. For operator-edited names
    return ``None`` on collision so the route surfaces a 422-style
    redirect instead of silently changing the name.
    """

    from app.db.models import RuleSet as RuleSetModel

    if not _name_taken_by_other(
        db, user=user, candidate_name=requested_name, exclude_id=None
    ):
        return requested_name
    if not auto_suffix or requested_name != source_default:
        return None

    n = 2
    while True:
        candidate = f"{requested_name} ({n})"
        existing = db.execute(
            select(RuleSetModel.id).where(
                RuleSetModel.owner_user_id == user.id,
                RuleSetModel.name == candidate,
                RuleSetModel.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        n += 1
        if n > 1000:
            return None  # defensive — give up after absurd suffix run


def _name_taken_by_other(
    db: Session,
    *,
    user: User,
    candidate_name: str,
    exclude_id: int | None,
) -> bool:
    """Check whether ``candidate_name`` is already used by a Personal
    RuleSet owned by ``user`` (excluding the row being saved, if
    any). Soft-deleted rows are ignored — names are recyclable after
    delete."""

    from app.db.models import RuleSet as RuleSetModel

    stmt = select(RuleSetModel.id).where(
        RuleSetModel.owner_user_id == user.id,
        RuleSetModel.name == candidate_name,
        RuleSetModel.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(RuleSetModel.id != exclude_id)
    return db.execute(stmt).scalar_one_or_none() is not None


@router.post(
    "/sessions/{session_id}/assignments/rule-based/generate",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_generate(
    request: Request,
    rule_set_id: int = Form(...),
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:

    from app.schemas.rules import Combinator, Rule, RuleSetOptions, RuleSetSchema

    _require_editable(review_session)

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    rule_set_row, revision = loaded

    existing = assignments.existing_count(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=needs_confirm"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)

    # Rehydrate the persisted RuleSet through the typed schema so the
    # engine sees the same shape as the editor would. Validators run
    # at ``model_validate`` time; the seed installer + editor save
    # paths already gate on that, so a malformed row here is a
    # data-integrity bug rather than user error.
    rule_adapter = TypeAdapter(Rule)
    rule_set_schema = RuleSetSchema(
        id=rule_set_row.id,
        name=rule_set_row.name,
        description=rule_set_row.description or "",
        scope=rule_set_row.scope,  # type: ignore[arg-type]
        combinator=Combinator(revision.combinator),
        rules=[
            rule_adapter.validate_python(payload)
            for payload in revision.rules_json
        ],
        options=RuleSetOptions(
            excludeSelfReviews=revision.exclude_self_reviews,
            seed=revision.seed,
        ),
    )

    override_exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )
    result = engine.evaluate(
        rule_set_schema,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=override_exclude_self,
        revision_seed=revision.id,
        pair_context_lookup=pair_context_lookup,
    )

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=result.pairs,
        mode=AssignmentMode.rule_based,
        correlation_id=request_correlation_id(),
        excluded_counts=result.excluded_counts,
        rule_set_revision=revision,
        exclude_self_reviews=override_exclude_self,
    )

    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ---------------------------------------------------------------------------
# Segment 15C Slice 4 — cross-tier promote / demote
# ---------------------------------------------------------------------------
#
# Both routes operate on the session tier (``session_rule_sets``) for the
# session-side of the transition, leaving the legacy library-tier Rule
# Builder flow (Save / Copy / Delete against ``operator_rule_sets``)
# untouched. The picker source flip itself lands in Slice 4b; until then
# these routes are reachable only via direct POST and let downstream
# work (the per-instrument picker on the Instruments page,
# ``instruments.rule_set_id`` resolution in 15B) exercise the cross-tier
# audit trail end-to-end.


@router.post(
    "/sessions/{session_id}/assignments/rule-based-editor/save-to-library",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_builder_save_to_library(
    rule_set_id: int = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Promote a SessionRuleSet to the actor's operator library.

    Refuses (303 with ``error=name_collision``) when the actor already
    has a library RuleSet with the same name. Both sides emit a fresh
    audit event: ``rule_set.created`` on the workspace tier and
    ``session_rule_sets.saved_to_library`` on the session tier.
    """
    base_url = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )
    row = session_library.load_session_rule_set(
        db, rule_set_id, session_id=review_session.id
    )
    if row is None:
        return RedirectResponse(
            url=base_url, status_code=status.HTTP_303_SEE_OTHER
        )
    try:
        session_library.save_to_library(
            db,
            session_rule_set=row,
            actor=user,
            correlation_id=request_correlation_id(),
        )
    except session_library.LibraryRuleSetNameConflictError:
        return RedirectResponse(
            url=f"{base_url}?rule_set_id={row.id}&error=name_collision",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    db.commit()
    return RedirectResponse(
        url=f"{base_url}?rule_set_id={row.id}&saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based-editor/add-from-library",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_builder_add_from_library(
    library_rule_set_id: int = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Copy a library Personal RuleSet into the session's
    ``session_rule_sets`` pool. Refuses on cross-operator ids and on
    name collisions in the session."""
    base_url = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )
    library_row = db.execute(
        select(RuleSet).where(
            RuleSet.id == library_rule_set_id,
            RuleSet.owner_user_id == user.id,
            RuleSet.is_seed.is_(False),
            RuleSet.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if library_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library RuleSet not found",
        )
    try:
        new_row = session_library.add_from_library(
            db,
            review_session=review_session,
            library_rule_set=library_row,
            actor=user,
            correlation_id=request_correlation_id(),
        )
    except session_library.SessionRuleSetNameConflictError:
        return RedirectResponse(
            url=f"{base_url}?error=name_collision",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    db.commit()
    return RedirectResponse(
        url=f"{base_url}?rule_set_id={new_row.id}&saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
