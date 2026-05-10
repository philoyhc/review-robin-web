"""Quick Setup card on Session Home — per-slot lock toggle, per-slot
submit handlers (reviewers / reviewees / assignments), and the
consolidated submit-all handler. Also owns ``POST /sessions``
(``create_session``), which dispatches the same per-slot pipeline
when the operator stages uploads on the new-session page.

Slice 7 of the major refactor.

Source range in pre-refactor ``routes_operator.py``: 669-1259
(plus ``create_session`` from 80-205, deferred from PR 5 because
of its tight coupling to the helpers in this slice).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.schemas.sessions import SessionCreate
from app.services import assignments, csv_imports, sessions
from app.services import session_lifecycle as lifecycle
from app.services.rules import engine, library
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _quick_setup_cookie_name,
    _require_response_loss_ack,
)


router = APIRouter()


@router.post("/sessions", response_model=None)
async def create_session(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    help_contact: str | None = Form(default=None),
    reviewers_file: UploadFile | None = File(default=None),
    reviewees_file: UploadFile | None = File(default=None),
    assignments_file: UploadFile | None = File(default=None),
    rule_set_id: str | None = Form(default=None),
    exclude_self_review: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    parsed_deadline: datetime | None = None
    if deadline:
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="deadline must be ISO-8601",
            ) from exc

    payload = SessionCreate(
        name=name,
        code=code,
        description=description or None,
        deadline=parsed_deadline,
        help_contact=help_contact or None,
    )
    review_session = sessions.create_session(
        db,
        user=user,
        payload=payload,
        correlation_id=request_correlation_id(),
    )

    # If the operator staged any Quick Setup uploads on the new-session
    # page, dispatch them through the same per-slot pipeline used by
    # the consolidated submit-all handler on Session Home. The session
    # was just created — no replace-confirmation is needed (there's
    # nothing to overwrite). On the first slot's failure, redirect to
    # Home with the slot's error flag.
    home_url = f"/operator/sessions/{review_session.id}"

    def quick_setup_error_redirect(
        kind: str, reason: str
    ) -> RedirectResponse:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={reason}#quick-setup-{kind}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    last_fragment = ""

    if reviewers_file is not None and reviewers_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewers_file,
            confirm_replace="true",
            acknowledge_response_loss=None,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewers",
            existing_count_fn=csv_imports.existing_reviewer_count,
            parse_fn=csv_imports.parse_reviewer_csv,
            save_fn=csv_imports.save_reviewers,
        )
        if reason is not None:
            return quick_setup_error_redirect("reviewers", reason)
        last_fragment = "#quick-setup-reviewers"

    if reviewees_file is not None and reviewees_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewees_file,
            confirm_replace="true",
            acknowledge_response_loss=None,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewees",
            existing_count_fn=csv_imports.existing_reviewee_count,
            parse_fn=csv_imports.parse_reviewee_csv,
            save_fn=csv_imports.save_reviewees,
        )
        if reason is not None:
            return quick_setup_error_redirect("reviewees", reason)
        last_fragment = "#quick-setup-reviewees"

    has_assignments_file = (
        assignments_file is not None and assignments_file.filename
    )
    parsed_rule_set_id: int | None = None
    if rule_set_id is not None and rule_set_id.strip():
        candidate = rule_set_id.strip()
        if candidate.lstrip("-").isdigit():
            parsed = int(candidate)
            if parsed > 0:
                parsed_rule_set_id = parsed
    if has_assignments_file or parsed_rule_set_id is not None:
        reason = await _run_quick_setup_assignments(
            file=assignments_file,
            rule_set_id=parsed_rule_set_id,
            exclude_self_review=exclude_self_review,
            confirm_replace="true",
            acknowledge_response_loss=None,
            review_session=review_session,
            user=user,
            db=db,
        )
        if reason is not None:
            return quick_setup_error_redirect("assignments", reason)
        last_fragment = "#quick-setup-assignments"

    return RedirectResponse(
        url=f"{home_url}{last_fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 11J PR A — Quick Setup card live wiring
# --------------------------------------------------------------------------- #
#
# Three live POST endpoints back the Quick Setup card on Session Home:
#
#   - ``POST /sessions/{id}/quick-setup/lock`` flips the per-session
#     ``HttpOnly`` cookie that drives the card's ``is_locked`` state.
#   - ``POST /sessions/{id}/quick-setup/reviewers`` /
#     ``POST /sessions/{id}/quick-setup/reviewees`` delegate to a thin
#     ``_handle_quick_setup_import`` wrapper that reuses the existing
#     per-entity import pipeline. On success the wrapper 303s back to
#     Session Home with no flag (the slot's count indicator is the
#     success signal). On parse / validation / lifecycle rejection it
#     303s with ``?quick_setup_error={kind}&quick_setup_reason=...``
#     so the GET render places a ``.banner.banner-error`` inside the
#     offending slot.


@router.post(
    "/sessions/{session_id}/quick-setup/lock",
    response_class=HTMLResponse,
    response_model=None,
)
def quick_setup_lock_toggle(
    action: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Flip the Quick Setup card's per-session lock cookie.

    ``action="unlock"`` sets ``qsu_{id}=1`` (and the next render
    drops ``.locked`` from the body wrapper); ``action="lock"`` clears
    the cookie. The toggle is visual only — the service layer
    (``_require_editable``) stays the source of truth for whether a
    slot's submit can mutate.
    """

    redirect = RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}#quick-setup"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    cookie_name = _quick_setup_cookie_name(review_session.id)
    # Path ``/`` so the cookie is visible on every subsequent request
    # — including pages outside ``/operator/sessions/{id}/`` like
    # ``/operator/sessions`` (lobby), ``/operator/settings``, and
    # ``/about``. The navigation middleware in ``app/main.py`` deletes
    # the cookie on any path that isn't Session Home or a quick-setup
    # endpoint, so leaving Home from any direction relocks the card.
    cookie_path = "/"
    if action == "unlock":
        redirect.set_cookie(
            key=cookie_name,
            value="1",
            path=cookie_path,
            httponly=True,
            samesite="lax",
        )
    else:
        redirect.delete_cookie(
            key=cookie_name,
            path=cookie_path,
        )
    # Touch unused params to silence type checkers; ``user`` / ``db``
    # are pulled in for the operator-permission dependency chain.
    del user, db
    return redirect


@router.post(
    "/sessions/{session_id}/quick-setup/reviewers",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewers_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _handle_quick_setup_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewers",
        existing_count_fn=csv_imports.existing_reviewer_count,
        parse_fn=csv_imports.parse_reviewer_csv,
        save_fn=csv_imports.save_reviewers,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/reviewees",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewees_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _handle_quick_setup_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewees",
        existing_count_fn=csv_imports.existing_reviewee_count,
        parse_fn=csv_imports.parse_reviewee_csv,
        save_fn=csv_imports.save_reviewees,
    )


async def _handle_quick_setup_import(
    *,
    request: Request,
    file: UploadFile,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> RedirectResponse:
    """Quick Setup card slot handler — thin wrapper over the same
    parse / save pipeline the per-entity Setup pages use.

    On success: 303 → Session Home with no flag; the slot's count
    indicator on the next render is the success signal (per the
    "no flash banner" direction in segment_11J).

    On parse / validation failure, missing-confirm, or lifecycle
    rejection: 303 → Session Home with ``?quick_setup_error={kind}``
    and a ``quick_setup_reason`` token that drives the slot's
    inline ``banner-error`` copy.
    """

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = f"#quick-setup-{kind}"
    error_reason = await _run_quick_setup_import(
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind=kind,
        existing_count_fn=existing_count_fn,
        parse_fn=parse_fn,
        save_fn=save_fn,
    )
    if error_reason is not None:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={error_reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"{home_url}{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _run_quick_setup_import(
    *,
    file: UploadFile,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> str | None:
    """Reusable parse / save pipeline shared by the per-slot routes
    and the consolidated ``submit-all`` handler. Returns the
    ``quick_setup_reason`` token on failure, ``None`` on success."""

    if not lifecycle.is_editable(review_session):
        return "lifecycle"

    content = await file.read()
    result = parse_fn(content)
    if not result.is_blocked:
        result.issues.extend(
            csv_imports.check_cross_table_identity(
                db,
                session_id=review_session.id,
                rows=result.rows,
                kind=kind,
            )
        )

    if result.is_blocked or any(
        issue.severity == "error" for issue in result.issues
    ):
        return "parse"

    existing = existing_count_fn(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return "needs_confirm"

    if existing > 0:
        try:
            _require_response_loss_ack(
                db, review_session, acknowledge_response_loss
            )
        except HTTPException:
            return "needs_confirm"

    save_fn(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return None


@router.post(
    "/sessions/{session_id}/quick-setup/assignments",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_assignments_submit(
    file: UploadFile | None = File(default=None),
    rule_set_id: int | None = Form(default=None),
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Quick Setup card slot 3 (Assignments) handler.

    Auto-detects mode from the form payload: when ``file`` is
    attached and non-empty, the route runs the manual-CSV pipeline;
    otherwise it routes the selected RuleSet through the new rule-
    based engine (``app.services.rules.engine.evaluate``).

    ``rule_set_id`` is the canonical input from the populated
    "Generate by rule" dropdown.

    Lifecycle / parse / confirm-required failures 303 → Home with
    ``?quick_setup_error=assignments&quick_setup_reason=...``; the
    GET render places the corresponding ``.banner.banner-error``
    inside the slot. Success 303s back to Home with no flag — the
    slot's count + active-rule indicator updates in place.
    """

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = "#quick-setup-assignments"

    error_reason = await _run_quick_setup_assignments(
        file=file,
        rule_set_id=rule_set_id,
        exclude_self_review=exclude_self_review,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
    )
    if error_reason is not None:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error=assignments"
                f"&quick_setup_reason={error_reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"{home_url}{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _run_quick_setup_assignments(
    *,
    file: UploadFile | None,
    rule_set_id: int | None,
    exclude_self_review: str | None,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> str | None:
    """Reusable assignments-slot pipeline shared by the per-slot
    route and the consolidated ``submit-all`` handler. Returns the
    ``quick_setup_reason`` token on failure, ``None`` on success."""

    if not lifecycle.is_editable(review_session):
        return "lifecycle"

    file_content = b""
    if file is not None and file.filename:
        file_content = await file.read()

    use_csv_mode = bool(file_content)
    existing = assignments.existing_count(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return "needs_confirm"
    if existing > 0:
        try:
            _require_response_loss_ack(
                db, review_session, acknowledge_response_loss
            )
        except HTTPException:
            return "needs_confirm"

    exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)

    if use_csv_mode:
        assert file is not None  # narrowed by ``use_csv_mode`` guard
        result = assignments.parse_manual_csv(
            file_content, reviewers, reviewees
        )
        if result.is_blocked or any(
            issue.severity == "error" for issue in result.issues
        ):
            return "parse"
        rows = result.rows
        if exclude_self:
            rows = [
                r
                for r in rows
                if r.reviewer_email.casefold()
                != r.reviewee_identifier.casefold()
            ]
        pairs, contexts, includes = assignments.manual_rows_to_pairs(
            rows, reviewers, reviewees
        )
        assignments.replace_assignments(
            db,
            review_session=review_session,
            user=user,
            pairs=pairs,
            mode=AssignmentMode.manual,
            correlation_id=request_correlation_id(),
            filename=file.filename,
            contexts=contexts,
            includes=includes,
        )
        return None

    # Rule mode. Route through the same library + engine pair that
    # drives the Rule Based card on the Assignments page — one
    # engine path, one audit shape, regardless of which surface
    # initiated the generation.

    from app.schemas.rules import (
        Combinator,
        Rule,
        RuleSetOptions,
        RuleSetSchema,
    )

    resolved_id = rule_set_id
    if resolved_id is None:
        return "parse"

    loaded = library.load_rule_set(db, resolved_id)
    if loaded is None:
        return "parse"
    rule_set_row, revision = loaded

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
    result = engine.evaluate(
        rule_set_schema,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=exclude_self,
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
        exclude_self_reviews=exclude_self,
    )
    return None


@router.post(
    "/sessions/{session_id}/quick-setup/submit-all",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_submit_all(
    request: Request,
    reviewers_file: UploadFile | None = File(default=None),
    reviewees_file: UploadFile | None = File(default=None),
    assignments_file: UploadFile | None = File(default=None),
    rule_set_id: str | None = Form(default=None),
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Consolidated Quick Setup submit handler.

    Replaces the per-slot Submit buttons (one per slot) with a
    single bottom Submit on the card. For each slot whose file is
    attached, dispatches to the same internal pipeline the per-slot
    route uses (kept alive as backend-only entry points). The
    Assignments slot also runs when no file is attached but a
    ``rule_set_id`` is supplied — the rule-based path through
    ``engine.evaluate``.

    Per the locked decision, the Submit button itself is gated
    client-side on file presence; this server-side handler is the
    source of truth and skips empty slots silently.

    On the first slot's failure the operator is redirected back to
    Home with that slot's ``?quick_setup_error=...&quick_setup_reason=...``
    flag; later slots in the dispatch order don't run on a failure
    upstream. Success 303s to Home with no flag and the slot
    fragment of the last slot that ran (or the card root when
    nothing did).
    """

    home_url = f"/operator/sessions/{review_session.id}"

    def error_redirect(kind: str, reason: str) -> RedirectResponse:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={reason}#quick-setup-{kind}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    last_fragment = ""

    if reviewers_file is not None and reviewers_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewers_file,
            confirm_replace=confirm_replace,
            acknowledge_response_loss=acknowledge_response_loss,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewers",
            existing_count_fn=csv_imports.existing_reviewer_count,
            parse_fn=csv_imports.parse_reviewer_csv,
            save_fn=csv_imports.save_reviewers,
        )
        if reason is not None:
            return error_redirect("reviewers", reason)
        last_fragment = "#quick-setup-reviewers"

    if reviewees_file is not None and reviewees_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewees_file,
            confirm_replace=confirm_replace,
            acknowledge_response_loss=acknowledge_response_loss,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewees",
            existing_count_fn=csv_imports.existing_reviewee_count,
            parse_fn=csv_imports.parse_reviewee_csv,
            save_fn=csv_imports.save_reviewees,
        )
        if reason is not None:
            return error_redirect("reviewees", reason)
        last_fragment = "#quick-setup-reviewees"

    has_assignments_file = (
        assignments_file is not None and assignments_file.filename
    )
    # ``rule_set_id`` arrives as a string because the dropdown's
    # default option is the empty-value sentinel ("— —") that means
    # "skip the assignments slot". Coerce to int when we have a
    # positive integer literal; treat anything else as no rule.
    parsed_rule_set_id: int | None = None
    if rule_set_id is not None and rule_set_id.strip():
        candidate = rule_set_id.strip()
        if candidate.lstrip("-").isdigit():
            parsed = int(candidate)
            if parsed > 0:
                parsed_rule_set_id = parsed
    if has_assignments_file or parsed_rule_set_id is not None:
        reason = await _run_quick_setup_assignments(
            file=assignments_file,
            rule_set_id=parsed_rule_set_id,
            exclude_self_review=exclude_self_review,
            confirm_replace=confirm_replace,
            acknowledge_response_loss=acknowledge_response_loss,
            review_session=review_session,
            user=user,
            db=db,
        )
        if reason is not None:
            return error_redirect("assignments", reason)
        last_fragment = "#quick-setup-assignments"

    return RedirectResponse(
        url=f"{home_url}{last_fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
