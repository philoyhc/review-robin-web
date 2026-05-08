"""Legacy container holding every operator route until the slice PRs
relocate them. See ``guide/major_refactor.md`` §6 — this file shrinks
once per slice PR and is deleted in PR 10.

Mounted unprefixed; the package ``__init__`` owns the ``/operator``
prefix and tag.
"""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.services import (
    assignments,
    instruments as instruments_service,
    invitations,
    monitoring,
    validation,
)
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _lifecycle_error_response,
    _require_editable,
    _require_response_loss_ack,
    _templates,
)

router = APIRouter()


@router.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_session(
    request: Request,
    severity: str = "all",
    activate: int = 0,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    issues = validation.validate_session_setup(db, review_session)
    report = lifecycle.build_readiness_report(issues)
    # Activate-warns detour: ?activate=1 requests the inline
    # confirmation banner (Segment 11G PR D). It only renders on
    # ``validated`` sessions that have warnings or new errors. On
    # ineligible states (draft / ready / closed) or when there's
    # nothing to acknowledge, drop the param and 303 to the clean
    # URL — operator can activate (or not) from Home.
    activate_banner: dict[str, object] | None = None
    if activate:
        if not lifecycle.is_validated(review_session):
            return RedirectResponse(
                url=f"/operator/sessions/{review_session.id}/validate",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if report.errors:
            activate_banner = {
                "kind": "error",
                "errors": report.errors,
            }
        elif report.warnings:
            activate_banner = {
                "kind": "warning",
                "warnings": report.warnings,
            }
        else:
            return RedirectResponse(
                url=f"/operator/sessions/{review_session.id}/validate",
                status_code=status.HTTP_303_SEE_OTHER,
            )
    validate_ctx = views.build_validate_context(
        db, review_session, issues, severity_filter=severity
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_validate.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "issues": issues,
            "validate": validate_ctx,
            "activate_banner": activate_banner,
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
            "can_activate": report.can_activate
            and lifecycle.is_validated(review_session),
            "needs_acknowledge": report.has_non_blocking_findings,
            "is_draft": lifecycle.is_draft(review_session),
            "is_validated": lifecycle.is_validated(review_session),
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Validate setup"
            ),
        },
    )



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

    from app.services.rules import library

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
    from app.services.rules import library

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

    from app.services.rules import library

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
    from pydantic import TypeAdapter

    from app.schemas.rules import Combinator, Rule, RuleSetOptions, RuleSetSchema
    from app.services.rules import engine, library

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
    result = engine.evaluate(
        rule_set_schema,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=override_exclude_self,
        revision_seed=revision.id,
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



# --------------------------------------------------------------------------- #
# Slice-local helper (Instruments). The cross-slice edit-lock guards
# (``_require_editable`` / ``_require_response_loss_ack`` /
# ``_lifecycle_error_response``) live in ``_shared.py``.
# --------------------------------------------------------------------------- #


def _require_instrument_in_session(
    instrument_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    db: Session = Depends(get_db),
) -> tuple[Instrument, ReviewSession]:
    instrument = db.execute(
        select(Instrument).where(
            Instrument.id == instrument_id,
            Instrument.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return instrument, review_session


# --------------------------------------------------------------------------- #
# Lifecycle routes (Segment 9.1)
# --------------------------------------------------------------------------- #


def _can_edit_instrument(review_session: ReviewSession) -> bool:
    """Setup-side mutations are blocked while session is ready."""
    return not lifecycle.is_ready(review_session)


def _require_instrument_editable(review_session: ReviewSession) -> None:
    if not _can_edit_instrument(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Instrument structure is locked while the session is ready"
            ),
        )


@router.get(
    "/sessions/{session_id}/instruments",
    response_class=HTMLResponse,
)
def instruments_index(
    request: Request,
    editing: int | None = Query(default=None),
    saved: int | None = Query(default=None),
    rtd_error: str | None = Query(default=None),
    rtd_id: int | None = Query(default=None),
    rf_save_error: str | None = Query(default=None),
    editing_rtd_id: int | None = Query(default=None),
    rtd_delete_blocked_id: int | None = Query(default=None),
    rtd_delete_blocked_rfs: int | None = Query(default=None),
    rtd_delete_blocked_instruments: int | None = Query(default=None),
    rtd_delete_blocked_responses: int | None = Query(default=None),
    rtd_delete_blocked_assignments: int | None = Query(default=None),
    rtd_would_empty_id: int | None = Query(default=None),
    rtd_would_empty_instruments: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    context = views.build_instruments_context(
        db,
        review_session=review_session,
        user=user,
        editing=editing,
        saved=saved,
        rtd_error=rtd_error,
        rtd_id=rtd_id,
        rf_save_error=rf_save_error,
        editing_rtd_id=editing_rtd_id,
        rtd_delete_blocked_id=rtd_delete_blocked_id,
        rtd_delete_blocked_rfs=rtd_delete_blocked_rfs,
        rtd_delete_blocked_instruments=rtd_delete_blocked_instruments,
        rtd_delete_blocked_responses=rtd_delete_blocked_responses,
        rtd_delete_blocked_assignments=rtd_delete_blocked_assignments,
        rtd_would_empty_id=rtd_would_empty_id,
        rtd_would_empty_instruments=rtd_would_empty_instruments,
    )
    return _templates.TemplateResponse(
        request, "operator/instruments_index.html", context
    )


@router.get("/sessions/{session_id}/previews", response_class=HTMLResponse)
def previews_index(
    request: Request,
    reviewer_email: str = "",
    email: str = "invitation",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Operations-row Previews tab — pre-flight reviewer experience hub.

    Distinct from ``/preview`` (singular), which is the operator's
    preview of the reviewer surface and is retired in PR C of segment
    11F. URL state:

    - ``?reviewer_email=…`` selects the picker's current reviewer; an
      unmatched value renders an inline "No reviewer matched" note
      rather than 404 or fall back to first.
    - ``?email=invitation|reminder|responses_received`` selects the
      active email-preview tab. PR B ships only the invitation render;
      unknown / unshipped values fall through to invitation so the
      page never blanks out.
    """
    picker = views.build_preview_picker_context(
        db, review_session, reviewer_email
    )
    active_email_tab = views.resolve_email_preview_tab(email)
    email_body: views.EmailBody | None = None
    surface_card: views.SurfacePreviewContext | None = None
    surface_html: str | None = None
    if picker.current is not None:
        reviewer_obj = db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id,
                Reviewer.id == picker.current.reviewer_id,
            )
        ).scalar_one()
        from_display = views.email_preview_from_display(user)
        email_body = views.build_email_preview_body(
            tab=active_email_tab,
            review_session=review_session,
            reviewer=reviewer_obj,
            from_display=from_display,
        )
        surface_card = views.build_surface_preview_context(
            db=db,
            user=user,
            review_session=review_session,
            reviewer=reviewer_obj,
        )
        if surface_card.preview is not None:
            # The iframe document is its own page, so breadcrumbs +
            # request go through the rendering context — the
            # breadcrumb partial in the operator chrome reads them
            # via Jinja's default. We point breadcrumbs at the
            # previews hub itself rather than back to a "Preview"
            # leaf so the operator-chrome trail inside the iframe
            # mirrors where they actually are.
            surface_html = _templates.get_template(
                "reviewer/review_surface.html"
            ).render(
                {
                    **surface_card.preview,
                    "request": request,
                    "breadcrumbs": breadcrumbs.operator_session_child(
                        review_session, "Previews"
                    ),
                }
            )
    return _templates.TemplateResponse(
        request,
        "operator/session_previews.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Previews"
            ),
            "picker": picker,
            "email_tabs": views.EMAIL_PREVIEW_TABS,
            "active_email_tab": active_email_tab,
            "email_body": email_body,
            "surface_card": surface_card,
            "surface_html": surface_html,
        },
    )


@router.post("/sessions/{session_id}/previews/random")
def previews_random(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Pick a random reviewer and 303 to the previews page.

    Random selection happens server-side via ``secrets.choice`` so no
    list of reviewer emails has to leak into client-side JS. Empty
    sessions 303 back without a ``?reviewer_email=`` param so the
    picker stays in its disabled empty state.
    """
    reviewers = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.email)
        ).scalars()
    )
    base_url = f"/operator/sessions/{review_session.id}/previews"
    if not reviewers:
        return RedirectResponse(
            url=base_url, status_code=status.HTTP_303_SEE_OTHER
        )
    selected = secrets.choice(reviewers)
    return RedirectResponse(
        url=f"{base_url}?reviewer_email={quote(selected.email)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/preview")
def session_preview(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Permanent redirect from the standalone reviewer-surface preview
    (Segment 10B-3) to the consolidated previews hub's surface card
    (Segment 11F PR C).

    Status 308 keeps the GET method and preserves the bookmark / link
    semantics for stragglers. The fragment lands the operator on the
    surface card directly. The hub renders the surface card only after
    the operator picks a reviewer in the picker, so this redirect lands
    on the empty-state body until they do.
    """
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/previews"
            f"#reviewer-surface"
        ),
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


def _instruments_redirect(
    session_id: int, fragment: str | None = None
) -> RedirectResponse:
    """Redirect to the Instruments index, optionally landing on an
    in-page anchor.

    Per-instrument actions (open / close / visibility / save) should
    pass ``fragment="instrument-{id}"`` so the operator lands on the
    instrument they were just acting on instead of being yanked to
    the top of the page. Bulk actions (accepting/visibility all-on/
    off) pass no fragment — they affect the whole list, so landing
    at the top is appropriate.
    """
    url = f"/operator/sessions/{session_id}/instruments"
    if fragment:
        url = f"{url}#{fragment}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _require_response_field_in_instrument(
    field_id: int, instrument: Instrument, db: Session
):
    from app.db.models import InstrumentResponseField

    field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.id == field_id,
            InstrumentResponseField.instrument_id == instrument.id,
        )
    ).scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return field


def _require_display_field_in_instrument(
    df_id: int, instrument: Instrument, db: Session
):
    from app.db.models import InstrumentDisplayField

    field = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.id == df_id,
            InstrumentDisplayField.instrument_id == instrument.id,
        )
    ).scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return field


@router.get(
    "/sessions/{session_id}/instruments/{instrument_id}",
)
def instrument_detail_redirect(
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
) -> RedirectResponse:
    """Back-compat: legacy per-instrument page redirects to consolidated view."""
    _, review_session = bundle
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/edit")
def instrument_edit_description(
    description: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    instruments_service.update_instrument_description(
        db,
        instrument=instrument,
        description=description,
        actor=user,
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/fields")
def instrument_add_field(
    field_key: str | None = Form(default=None),
    label: str = Form(...),
    response_type: str = Form(...),
    required: str | None = Form(default=None),
    validation_min: str | None = Form(default=None),
    validation_max: str | None = Form(default=None),
    help_text: str | None = Form(default=None),
    help_text_visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)

    key = (field_key or "").strip()
    if not key:
        key = instruments_service.slugify_field_key(label)

    # Validation is now derived from the chosen Response Type
    # Definition (Slice 4a); the legacy ``validation_min`` /
    # ``validation_max`` form fields are accepted but ignored.
    _ = validation_min, validation_max  # silence unused-arg

    try:
        instruments_service.add_response_field(
            db,
            instrument=instrument,
            field_key=key,
            label=label,
            response_type=response_type,
            required=required == "true",
            help_text=help_text,
            help_text_visible=(help_text_visible == "true"),
            actor=user,
        )
    except instruments_service.FieldKeyError as exc:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?field_key_error={int(False)}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"X-FieldKey-Error": str(exc)},
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/add-row"
)
def instrument_add_default_field(
    after: int | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    instruments_service.add_default_response_field(
        db, instrument=instrument, after_field_id=after, actor=user
    )
    # Preserve editing state: the ➕ button is only rendered while
    # editing, so the operator stays in editing mode after the add.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/{field_id}/edit"
)
def instrument_edit_field(
    field_id: int,
    label: str = Form(...),
    required: str | None = Form(default=None),
    validation_min: str | None = Form(default=None),
    validation_max: str | None = Form(default=None),
    help_text: str | None = Form(default=None),
    help_text_visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_response_field_in_instrument(field_id, instrument, db)

    # Validation now derives from the field's Response Type
    # Definition (Slice 4a); the legacy ``validation_min`` /
    # ``validation_max`` form fields are accepted but ignored, and
    # the existing derived block on the row is preserved as-is.
    _ = validation_min, validation_max  # silence unused-arg
    validation_block = field.validation

    _, warning_count = instruments_service.update_response_field(
        db,
        field=field,
        label=label,
        required=required == "true",
        validation=validation_block,
        help_text=help_text,
        help_text_visible=(help_text_visible == "true"),
        actor=user,
    )

    if warning_count > 0:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?required_warning={warning_count}&field_id={field.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/{field_id}/delete"
)
def instrument_delete_field(
    field_id: int,
    confirm: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_response_field_in_instrument(field_id, instrument, db)

    try:
        instruments_service.delete_response_field(
            db,
            field=field,
            confirm=(confirm == "true"),
            actor=user,
        )
    except instruments_service.ResponsesPresentError as exc:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&delete_blocked_field_id={field.id}"
                f"&delete_blocked_count={exc.cascaded_response_count}"
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    # Preserve editing state on the redirect.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/{field_id}/move"
)
def instrument_move_field(
    field_id: int,
    direction: str = Form(...),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_response_field_in_instrument(field_id, instrument, db)
    if direction not in ("up", "down"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    instruments_service.move_response_field(
        db, field=field, direction=direction, actor=user  # type: ignore[arg-type]
    )
    # Preserve editing state: the ▲ / ▼ buttons are only rendered
    # while editing.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/display-fields")
def instrument_add_display_field(
    source_pair: str = Form(...),
    label: str | None = Form(default=None),
    visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)

    if ":" not in source_pair:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?display_source_error=invalid_pair"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    source_type, source_field = source_pair.split(":", 1)

    try:
        instruments_service.add_display_field(
            db,
            instrument=instrument,
            source_type=source_type,
            source_field=source_field,
            label=label or "",
            visible=(visible == "true"),
            actor=user,
        )
    except instruments_service.DisplaySourceError:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?display_source_error={source_type}:{source_field}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}"
    "/display-fields/{df_id}/edit"
)
def instrument_edit_display_field(
    df_id: int,
    label: str | None = Form(default=None),
    visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)

    try:
        instruments_service.update_display_field(
            db,
            field=field,
            label=label or "",
            visible=(visible == "true"),
            actor=user,
        )
    except instruments_service.LockedDisplayFieldError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Locked display fields cannot be hidden.",
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}"
    "/display-fields/{df_id}/delete"
)
def instrument_delete_display_field(
    df_id: int,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)

    try:
        instruments_service.delete_display_field(db, field=field, actor=user)
    except instruments_service.LockedDisplayFieldError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Locked display fields cannot be deleted.",
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}"
    "/display-fields/{df_id}/move"
)
def instrument_move_display_field(
    df_id: int,
    direction: str = Form(...),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)
    if direction not in ("up", "down"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    try:
        instruments_service.move_display_field(
            db, field=field, direction=direction, actor=user
        )
    except instruments_service.LockedDisplayFieldError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Locked display fields cannot be reordered.",
        )
    # Preserve editing state on the redirect so the operator stays in
    # the editable view after moving a row.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/fields/save")
async def instrument_bulk_save_fields(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)

    form = await request.form()
    kinds = [str(v) for v in form.getlist("kind")]
    raw_ids = [str(v) for v in form.getlist("id")]
    orders = [str(v) for v in form.getlist("order")]
    labels = [str(v) for v in form.getlist("label")]
    # ``visible_ids`` and ``required_ids`` are submitted as raw row
    # ids so they can carry either real ints or ``new_N`` placeholders
    # for JS-added rows.
    visible_id_strs: set[str] = {
        str(v) for v in form.getlist("visible_ids")
    }
    required_id_strs: set[str] = {
        str(v) for v in form.getlist("required_ids")
    }
    # JS-deferred deletes: each ✗ click appends a hidden
    # ``response_delete_ids`` input on the bulk-save form so Cancel
    # discards the deletion.
    response_delete_ids: set[int] = set()
    for raw in form.getlist("response_delete_ids"):
        try:
            response_delete_ids.add(int(str(raw)))
        except ValueError:
            continue
    # Response Fields Help: per-row help_text + help_text_visible.
    # The Help card emits parallel ``help_text_id`` + ``help_text``
    # arrays plus a ``help_text_visible_ids`` set. Help ids may also
    # be ``new_N`` placeholders for JS-added rows.
    help_text_id_strs = [str(v) for v in form.getlist("help_text_id")]
    help_texts = [str(v) for v in form.getlist("help_text")]
    help_text_visible_id_strs: set[str] = {
        str(v) for v in form.getlist("help_text_visible_ids")
    }
    help_by_id_str: dict[str, str] = {}
    if len(help_text_id_strs) == len(help_texts):
        for raw_id, text in zip(help_text_id_strs, help_texts):
            help_by_id_str[raw_id] = text

    if not (len(kinds) == len(raw_ids) == len(orders) == len(labels)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk save row inputs are misaligned.",
        )

    # Slice 4d Gap 2: refuse to save an instrument with zero
    # Response Fields rows. Compute the post-save RF count up-front
    # (existing - deletes + new_* draft adds) and bounce back to the
    # editing context with an inline error banner if it would be
    # zero. Symmetric with the cascade-side guard on the Response
    # Type Definitions card.
    existing_rf_count = int(
        db.execute(
            select(func.count(instruments_service.InstrumentResponseField.id)).where(
                instruments_service.InstrumentResponseField.instrument_id
                == instrument.id
            )
        ).scalar_one()
    )
    new_response_count = sum(
        1
        for kind, raw_id in zip(kinds, raw_ids)
        if kind == "response"
        and raw_id.startswith("new_")
        and raw_id not in {str(d) for d in response_delete_ids}
    )
    # Deduplicate ``new_*`` ids — duplicates in the form payload
    # don't create extra rows.
    new_unique_ids = {
        raw_id
        for kind, raw_id in zip(kinds, raw_ids)
        if kind == "response"
        and raw_id.startswith("new_")
        and raw_id not in {str(d) for d in response_delete_ids}
    }
    new_response_count = len(new_unique_ids)
    post_save_rf_count = (
        existing_rf_count - len(response_delete_ids) + new_response_count
    )
    if post_save_rf_count <= 0:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&rf_save_error=An+instrument+must+have+at+least+one+response+field."
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )


    # 1. Apply JS-deferred deletes first so the bulk-save step below
    #    sees a clean existing-rows list. Use ``confirm=True`` since
    #    the page is only editable while the session is in setup; no
    #    responses can exist yet.
    for delete_id in response_delete_ids:
        field = db.get(instruments_service.InstrumentResponseField, delete_id)
        if field is None or field.instrument_id != instrument.id:
            continue
        try:
            instruments_service.delete_response_field(
                db, field=field, confirm=True, actor=user
            )
        except instruments_service.ResponsesPresentError:
            # Defensive: if a concurrent edit made the session ongoing
            # between the GET and POST, just skip this row.
            continue

    # 2. Allocate real ids for any ``new_*`` response rows. The route
    #    creates them via ``add_default_response_field``, passing the
    #    operator-chosen RTD (Slice 4c), the typed label, and the
    #    Required flag so the new row lands at the right shape on
    #    Save. ``add_default_response_field`` slugifies the label
    #    into a non-conflicting ``field_key`` (falling back to the
    #    auto ``rating{N}`` series when the label is blank).
    #    The bulk-save step below then folds in any subsequent edits.
    new_rtd_targets = [str(v) for v in form.getlist("new_rtd_target")]
    new_rtd_ids = [str(v) for v in form.getlist("new_rtd_id")]
    new_rtd_by_draft: dict[str, int] = {}
    if len(new_rtd_targets) == len(new_rtd_ids):
        for target, rtd_id_str in zip(new_rtd_targets, new_rtd_ids):
            try:
                new_rtd_by_draft[target] = int(rtd_id_str)
            except ValueError:
                continue
    new_label_by_draft: dict[str, str] = {}
    for kind, raw_id, label_value in zip(kinds, raw_ids, labels):
        if kind == "response" and raw_id.startswith("new_"):
            new_label_by_draft[raw_id] = label_value

    new_id_map: dict[str, int] = {}
    for kind, raw_id in zip(kinds, raw_ids):
        if kind != "response":
            continue
        if not raw_id.startswith("new_") or raw_id in new_id_map:
            continue
        if raw_id in {str(d) for d in response_delete_ids}:
            continue  # added then deleted before save — skip
        new_field = instruments_service.add_default_response_field(
            db,
            instrument=instrument,
            after_field_id=None,
            rtd_id=new_rtd_by_draft.get(raw_id),
            label=new_label_by_draft.get(raw_id),
            required=raw_id in required_id_strs,
            actor=user,
        )
        new_id_map[raw_id] = new_field.id

    def _resolve_id(raw: str) -> int | None:
        if raw.startswith("new_"):
            return new_id_map.get(raw)
        try:
            return int(raw)
        except ValueError:
            return None

    visible_ids: set[int] = set()
    for s in visible_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            visible_ids.add(rid)
    required_ids: set[int] = set()
    for s in required_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            required_ids.add(rid)
    help_text_visible_ids: set[int] = set()
    for s in help_text_visible_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            help_text_visible_ids.add(rid)
    help_by_id: dict[int, str] = {}
    for raw_id, text in help_by_id_str.items():
        rid = _resolve_id(raw_id)
        if rid is not None:
            help_by_id[rid] = text

    rows: list[dict[str, Any]] = []
    for kind, raw_id, raw_order, label in zip(kinds, raw_ids, orders, labels):
        row_id = _resolve_id(raw_id)
        if row_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bulk save id values must be integers or new_*.",
            )
        # Skip rows the operator marked deleted in this same submit.
        if kind == "response" and row_id in response_delete_ids:
            continue
        try:
            row_order = int(raw_order)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bulk save order values must be integers.",
            )
        row: dict[str, Any] = {"kind": kind, "id": row_id, "order": row_order}
        if kind == "display":
            row["label"] = label
            row["visible"] = row_id in visible_ids
        elif kind == "response":
            row["label"] = label
            row["required"] = row_id in required_ids
            if row_id in help_by_id:
                row["help_text"] = help_by_id[row_id]
                row["help_text_visible"] = row_id in help_text_visible_ids
        rows.append(row)

    instruments_service.bulk_save_fields(
        db, instrument=instrument, rows=rows, actor=user
    )
    # Section A — instrument description shares the same Save / Cancel
    # state machine as the tables. Only push the update when the value
    # actually changed to avoid an audit-event for a no-op edit.
    if "description" in form:
        submitted_desc = form.get("description")
        cleaned = (
            submitted_desc.strip() if isinstance(submitted_desc, str) else None
        ) or None
        if cleaned != instrument.description:
            instruments_service.update_instrument_description(
                db, instrument=instrument, description=cleaned, actor=user
            )
    # Section A — short_label shares the same Save / Cancel state machine
    # as description. Per Segment 11L, the field is reviewer-facing and
    # capped at 32 chars (HTML5 ``maxlength`` is the user-visible
    # guardrail; the service helper raises ValueError as a defensive
    # fallback that yields HTTP 400).
    if "short_label" in form:
        submitted_label = form.get("short_label")
        try:
            instruments_service.update_short_label(
                db,
                instrument=instrument,
                short_label=(
                    submitted_label
                    if isinstance(submitted_label, str)
                    else None
                ),
                actor=user,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    # Redirect with ``?saved={iid}`` so the page renders a flash
    # confirmation. The ``?editing`` param is intentionally cleared —
    # per spec, a successful Save locks the tables.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?saved={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/add")
def instruments_add(
    after: int | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    instrument = instruments_service.create_instrument(
        db, review_session=review_session, after_instrument_id=after, actor=user
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --- Slice 4b: operator add / edit / delete on Response Type
# Definitions card. ``response_type`` (name) + ``data_type`` are
# spec-locked once a row is saved, so the edit route only accepts
# Min / Max / Step / List. Cascade-on-delete confirmation is
# handled via a redirect-with-query when the dependent count is
# nonzero and ``confirm`` is not set.

def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse {raw!r} as a number.",
        )


def _rtd_redirect_with_error(
    session_id: int,
    *,
    error: str,
    rtd_id: int | None = None,
    keep_editing: bool = False,
) -> RedirectResponse:
    fragment = "rtd-card" if rtd_id is None else f"rtd-row-{rtd_id}"
    encoded = error.replace("&", "%26").replace(" ", "+")
    rtd_param = f"&rtd_id={rtd_id}" if rtd_id is not None else ""
    editing_param = (
        f"&editing_rtd_id={rtd_id}"
        if (keep_editing and rtd_id is not None)
        else ""
    )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{session_id}/instruments"
            f"?rtd_error={encoded}{rtd_param}{editing_param}#{fragment}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types")
def response_type_add(
    response_type: str = Form(...),
    data_type: str = Form(...),
    min: str | None = Form(default=None),
    max: str | None = Form(default=None),
    step: str | None = Form(default=None),
    list_csv: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    min_value = _parse_optional_float(min)
    max_value = _parse_optional_float(max)
    step_value = _parse_optional_float(step)

    try:
        instruments_service.add_response_type_definition(
            db,
            review_session=review_session,
            response_type=response_type,
            data_type=data_type,
            min=min_value,
            max=max_value,
            step=step_value,
            list_csv=list_csv,
            actor=user,
        )
    except (
        instruments_service.RTDValidationError,
        instruments_service.RTDPrecisionError,
    ) as exc:
        return _rtd_redirect_with_error(review_session.id, error=str(exc))
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _require_rtd_in_session(
    rtd_id: int,
    review_session: ReviewSession,
    db: Session,
):
    rtd = db.execute(
        select(instruments_service.ResponseTypeDefinition).where(
            instruments_service.ResponseTypeDefinition.id == rtd_id,
            instruments_service.ResponseTypeDefinition.session_id
            == review_session.id,
        )
    ).scalar_one_or_none()
    if rtd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response Type Definition not found",
        )
    return rtd


@router.post("/sessions/{session_id}/response-types/{rtd_id}/edit")
def response_type_edit(
    rtd_id: int,
    min: str | None = Form(default=None),
    max: str | None = Form(default=None),
    step: str | None = Form(default=None),
    list_csv: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    if rtd.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seeded Response Types are spec-locked and cannot be edited.",
        )

    min_value = _parse_optional_float(min)
    max_value = _parse_optional_float(max)
    step_value = _parse_optional_float(step)

    try:
        instruments_service.update_response_type_definition(
            db,
            rtd=rtd,
            min=min_value,
            max=max_value,
            step=step_value,
            list_csv=list_csv,
            actor=user,
        )
    except (
        instruments_service.RTDValidationError,
        instruments_service.RTDPrecisionError,
    ) as exc:
        return _rtd_redirect_with_error(
            review_session.id,
            error=str(exc),
            rtd_id=rtd.id,
            keep_editing=True,
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types/{rtd_id}/delete")
def response_type_delete(
    rtd_id: int,
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    if rtd.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seeded Response Types are spec-locked and cannot be deleted.",
        )

    try:
        instruments_service.delete_response_type_definition(
            db, rtd=rtd, confirm=(confirm == "true"), actor=user
        )
    except instruments_service.RTDDeleteWouldEmptyInstrumentError as exc:
        # Slice 4d Gap 3: hard-block. The cascade would leave at
        # least one instrument with zero RF rows; operator must add
        # a non-ODT row to that instrument first.
        names = ",".join(
            str(e["instrument_number"]) for e in exc.would_empty
        )
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?rtd_would_empty_id={rtd.id}"
                f"&rtd_would_empty_instruments={names}"
                f"#rtd-row-{rtd.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except instruments_service.RTDInUseError as exc:
        d = exc.dependents
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?rtd_delete_blocked_id={rtd.id}"
                f"&rtd_delete_blocked_rfs={d['response_field_count']}"
                f"&rtd_delete_blocked_instruments={d['instrument_count']}"
                f"&rtd_delete_blocked_responses={d['response_count']}"
                f"&rtd_delete_blocked_assignments={d['assignment_count']}"
                f"#rtd-row-{rtd.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/delete")
def instruments_delete(
    instrument_id: int,
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.id == instrument_id)
        .where(Instrument.session_id == review_session.id)
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrument not found",
        )
    total = db.execute(
        select(func.count())
        .select_from(Instrument)
        .where(Instrument.session_id == review_session.id)
    ).scalar_one()
    if total <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last instrument",
        )
    # Pick the next-or-previous sibling so the operator lands near
    # the instrument they just deleted instead of being yanked to
    # the top of the page. Captured BEFORE the delete since the row
    # is gone after.
    sibling_ids = (
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        )
        .scalars()
        .all()
    )
    idx = sibling_ids.index(instrument_id)
    if idx + 1 < len(sibling_ids):
        landing_id = sibling_ids[idx + 1]
    else:
        landing_id = sibling_ids[idx - 1]
    instruments_service.delete_instrument(
        db, instrument=instrument, actor=user
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{landing_id}"
    )


@router.post("/sessions/{session_id}/instruments/accepting/all-on")
def instruments_bulk_accept_on(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bulk accepting toggle requires session to be ready",
        )
    instruments_service.bulk_set_accepting(
        db, review_session=review_session, target=True, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/accepting/all-off")
def instruments_bulk_accept_off(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bulk accepting toggle requires session to be ready",
        )
    instruments_service.bulk_set_accepting(
        db, review_session=review_session, target=False, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/visibility/all-on")
def instruments_bulk_visibility_on(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instruments_service.bulk_set_visibility(
        db, review_session=review_session, target=True, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/visibility/all-off")
def instruments_bulk_visibility_off(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instruments_service.bulk_set_visibility(
        db, review_session=review_session, target=False, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/open")
def instrument_open(
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    try:
        lifecycle.open_instrument(
            db,
            instrument=instrument,
            review_session=review_session,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except lifecycle.LifecycleError as exc:
        raise _lifecycle_error_response(exc) from exc
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/close")
def instrument_close(
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    lifecycle.close_instrument(
        db,
        instrument=instrument,
        review_session=review_session,
        user=user,
        reason="manual",
        correlation_id=request_correlation_id(),
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/visibility")
def instrument_visibility(
    visible_when_closed: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    lifecycle.set_responses_visible_when_closed(
        db,
        instrument=instrument,
        review_session=review_session,
        user=user,
        visible=visible_when_closed == "true",
        correlation_id=request_correlation_id(),
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


# --------------------------------------------------------------------------- #
# Invitation + outbox routes (Segment 9.2)
# --------------------------------------------------------------------------- #


def _require_ready(review_session: ReviewSession) -> None:
    """Reject invitation actions while session is not ready.

    Inverse of the 9.1 ``_require_draft`` lock: invitations point at a live
    reviewer surface, so they must only be issued / sent on a ready session.
    """
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Invitations can only be issued while the session is ready"
            ),
        )


def _require_invitation_in_session(
    invitation_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    db: Session = Depends(get_db),
) -> tuple[Invitation, ReviewSession]:
    invitation = db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return invitation, review_session


@router.get(
    "/sessions/{session_id}/invitations", response_class=HTMLResponse
)
def invitations_index(
    request: Request,
    status: str = "all",
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    all_rows = views.build_invitations_rows(db, review_session)
    rows = views.filter_invitations_rows(all_rows, status=status, search=q)
    search_options = views.invitations_search_options(all_rows)
    invitation_rows = invitations.list_invitations_for_session(
        db, review_session.id
    )
    eligible = invitations.reviewers_eligible_for_invitation(db, review_session.id)
    invited_ids = {r.invitation.reviewer_id for r in invitation_rows}
    pending_count = sum(
        1
        for r in invitation_rows
        if r.invitation.status == "pending"
    )
    incomplete_count = sum(1 for r in all_rows if r.is_incomplete)
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "total_row_count": len(all_rows),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.INVITATIONS_STATUS_OPTIONS,
            "filter_search_options": search_options,
            "eligible_count": len(eligible),
            "uninvited_count": sum(1 for r in eligible if r.id not in invited_ids),
            "pending_count": pending_count,
            "incomplete_count": incomplete_count,
            "total_invitation_count": len(invitation_rows),
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Invitations"
            ),
        },
    )


@router.get(
    "/sessions/{session_id}/invitations/{invitation_id}/detail",
    response_class=HTMLResponse,
)
def invitation_reviewer_detail(
    request: Request,
    bundle: tuple[Invitation, ReviewSession] = Depends(
        _require_invitation_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Drill-in from a row on the Manage Invitations table.

    Segment 11C Part 1 scaffolds this as a thin per-reviewer summary —
    the same Email Status / Review Progress / Required Fields fields the
    consolidated table renders, plus the latest invitation outbox row's
    raw token URL when available. Future segments grow this surface
    (per-assignment progress, per-response detail).
    """
    invitation, review_session = bundle
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    rows = views.build_invitations_rows(db, review_session)
    row = next((r for r in rows if r.reviewer.id == reviewer.id), None)
    invite_url = invitations.most_recent_invitation_url(
        db, invitation_id=invitation.id
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations_reviewer_detail.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewer": reviewer,
            "invitation": invitation,
            "row": row,
            "invite_url": invite_url,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_invitations_reviewer(
                review_session, reviewer.name
            ),
        },
    )


@router.post("/sessions/{session_id}/invitations/generate")
def invitations_generate(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_ready(review_session)
    invitations.generate_invitations(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/invitations/send-all")
def invitations_send_all(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_ready(review_session)
    rows = invitations.list_invitations_for_session(db, review_session.id)
    for row in rows:
        if row.invitation.status != "pending":
            continue
        invitations.send_invitation(
            db,
            invitation=row.invitation,
            review_session=review_session,
            reviewer=row.reviewer,
            user=user,
            build_invite_url=lambda token: str(
                request.url_for("reviewer_invite", token=token)
            ),
            correlation_id=request_correlation_id(),
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/invitations/regenerate-all")
def invitations_regenerate_all(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-rotate every invitation token in the session. Each
    invitation flips to ``pending`` and ``sent_at`` / ``opened_at``
    clear; previously-issued URLs go stale uniformly. One batch
    ``invitations.regenerated`` audit event when at least one
    invitation was rotated."""
    _require_ready(review_session)
    invitations.regenerate_all_tokens(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/invitations/{invitation_id}/regenerate"
)
def invitations_regenerate(
    bundle: tuple[Invitation, ReviewSession] = Depends(_require_invitation_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    invitation, review_session = bundle
    _require_ready(review_session)
    invitations.regenerate_token(
        db,
        invitation=invitation,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/invitations/{invitation_id}/send"
)
def invitations_send_one(
    request: Request,
    bundle: tuple[Invitation, ReviewSession] = Depends(_require_invitation_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    invitation, review_session = bundle
    _require_ready(review_session)
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    invitations.send_invitation(
        db,
        invitation=invitation,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/outbox", response_class=HTMLResponse)
def outbox_index(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = invitations.list_outbox_for_session(db, review_session.id)
    return _templates.TemplateResponse(
        request,
        "operator/session_outbox.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Outbox"
            ),
        },
    )


# --------------------------------------------------------------------------- #
# Monitoring + reminders (Segment 9.3)
# --------------------------------------------------------------------------- #


@router.get("/sessions/{session_id}/monitoring")
def session_monitoring_redirect(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Segment 11C Part 1 PR 3 retired the Monitoring template; the
    consolidated Manage Invitations page (PR 2) absorbed its
    reviewer-centric surface. Existing bookmarks land here and 303
    forward to ``/invitations``."""
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/sessions/{session_id}/responses", response_class=HTMLResponse
)
def session_responses(
    request: Request,
    status: str = "all",
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Reviewee-centric coverage view (Segment 11C Part 1 PR 3).

    Each row classifies a reviewee per ``monitoring.AT_RISK_THRESHOLDS``
    (Complete / Adequate / At risk / No responses) based on the fraction
    of their assigned reviewers who have submitted. Bulk reminder funnels
    through the same ``invitations.send_reminders_to_incomplete`` helper
    the Manage Invitations page calls.

    ``status`` and ``q`` query params drive the per-page filter strip
    (Segment 11C Part 1 follow-up). Filter state is page-local; not
    persisted across navigations.
    """
    all_rows = views.build_responses_rows(db, review_session)
    rows = views.filter_responses_rows(all_rows, status=status, search=q)
    search_options = views.responses_search_options(all_rows)
    summary = monitoring.summary_counts(db, review_session)
    incomplete_count = summary.incomplete
    return _templates.TemplateResponse(
        request,
        "operator/session_responses.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "total_row_count": len(all_rows),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.RESPONSES_STATUS_OPTIONS,
            "filter_search_options": search_options,
            "incomplete_count": incomplete_count,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Responses"
            ),
        },
    )


@router.get(
    "/sessions/{session_id}/responses/{reviewee_id}/detail",
    response_class=HTMLResponse,
)
def responses_reviewee_detail(
    request: Request,
    reviewee_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Drill-in from a Responses table row (Segment 11C Part 1 PR 3
    scaffold). Per-assignment / per-response detail lands in a future
    segment; this surface mirrors the row-level fields plus a list of
    the reviewers assigned to this reviewee."""
    reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.id == reviewee_id,
            Reviewee.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if reviewee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    coverage = monitoring.per_reviewee_coverage(db, review_session)
    row = next((c for c in coverage if c.reviewee.id == reviewee.id), None)
    return _templates.TemplateResponse(
        request,
        "operator/session_responses_reviewee_detail.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewee": reviewee,
            "row": row,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_responses_reviewee(
                review_session, reviewee.name
            ),
        },
    )


@router.post(
    "/sessions/{session_id}/invitations/{invitation_id}/remind"
)
def invitations_remind_one(
    request: Request,
    bundle: tuple[Invitation, ReviewSession] = Depends(
        _require_invitation_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    invitation, review_session = bundle
    _require_ready(review_session)
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    invitations.send_reminder(
        db,
        invitation=invitation,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/invitations/remind-incomplete"
)
def invitations_remind_incomplete(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk reminder dispatch from the consolidated Manage Invitations
    page (Segment 11C Part 1). Funnels through the same
    ``invitations.send_reminders_to_incomplete`` helper the (still-
    existing) Monitoring page uses; PR 3 retires the Monitoring
    counterpart endpoint."""
    _require_ready(review_session)
    invitations.send_reminders_to_incomplete(
        db,
        review_session=review_session,
        user=user,
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# The POST /sessions/{id}/monitoring/remind-incomplete endpoint retired
# in Segment 11C Part 1 PR 3. Its only caller was the (now-deleted)
# Monitoring template; bulk reminder dispatch funnels through
# ``POST /sessions/{id}/invitations/remind-incomplete`` (PR 2) instead.
