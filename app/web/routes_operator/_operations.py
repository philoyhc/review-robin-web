"""Operations row — Validate / Manage Invitations /
Outbox / Responses, plus the reminder dispatch endpoints.
Slice 9 of the major refactor.

Source ranges in pre-refactor ``routes_operator.py``:
460-525 (Validate), 2727-2868 (Previews + preview redirect),
3963-4423 (Manage Invitations + Outbox + Responses + reminders +
monitoring redirect).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import invitations, monitoring, validation
from app.services.email_identity import normalize_email
from app.services._queries import tag_slot_presence
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _REVERT_RETURN_TO,
    _require_reviewer_in_session,
    _templates,
)


# --------------------------------------------------------------------------- #
# Column sort — Segment 19I Item 11 rung 2.
#
# Both tables opt into the shared ``data-rrw-sortable`` primitive, so the
# cookie carries the operator's cascade and the route re-applies it here:
# the first paint lands in the chosen order rather than being re-shuffled
# by JS after load.
#
# These rows are **wrappers**, not ORM objects, so the roster pages'
# one-line ``getattr(row, key)`` resolver does not reach
# ``row.reviewer.name``. Hence the explicit maps below.
# --------------------------------------------------------------------------- #

_INVITATIONS_SORT_KEYS = {
    "name",
    "tag_1",
    "tag_2",
    "tag_3",
    "email_status",
    "email_sent_at",
    "review_progress",
    "required_fields",
    "last_reminder_at",
}

_RESPONSES_SORT_KEYS = {
    "name",
    "tag_1",
    "tag_2",
    "tag_3",
    "coverage_state",
    "reviewers_done",
    "last_response_at",
}


def _completion_pct(done: int, total: int) -> int | None:
    """Percentage complete, or ``None`` when there is nothing to do.

    The progress columns show ``done/total`` and the totals differ per
    row, so ordering by the raw done count orders nothing an operator
    would recognise. ``None`` sorts last on both sides — the template
    renders an empty ``data-sort-value`` for the same state, and
    ``apply_cookie_sort`` and the client comparator both treat
    empty/None as "no data, sorts last regardless of direction".
    """
    return (done * 100) // total if total else None


def _invitations_sort_value(row, key: str):
    if key == "name":
        return row.reviewer.name
    if key in ("tag_1", "tag_2", "tag_3"):
        return getattr(row.reviewer, key)
    if key == "email_status":
        return row.email_status
    if key == "email_sent_at":
        return row.email_sent_at
    if key == "review_progress":
        return _completion_pct(
            row.review_progress_done, row.review_progress_total
        )
    if key == "required_fields":
        return _completion_pct(
            row.required_fields_done, row.required_fields_total
        )
    if key == "last_reminder_at":
        return row.last_reminder_at
    return None


def _responses_sort_value(row, key: str):
    if key == "name":
        return row.reviewee.name
    if key in ("tag_1", "tag_2", "tag_3"):
        return getattr(row.reviewee, key)
    if key == "coverage_state":
        return row.coverage_state
    if key == "reviewers_done":
        return _completion_pct(row.reviewers_done, row.reviewers_total)
    if key == "last_response_at":
        return row.last_response_at
    return None


def _page_operations_rows(
    matching: list, *, is_filtered: bool, offset: int
) -> tuple[list, int, views.Pager | None]:
    """Cut the page the operator asked for out of the Invitations /
    Responses row list — Segment 19J.5 rung 3.

    Both pages rendered **every** matching row until now, whatever the
    number, which is why they are the two that hurt most on a large
    roster. They page at 200 unfiltered, on the same terms as the
    rosters.

    **A filtered view stays uncapped here**, unlike the four Setup
    pages, which cap theirs at 500. Those two carry the 500 from
    Segment 15F; these two never had a cap, and inventing one would
    take rows away from a filtered view that shows them today — a loss
    no part of 19J.5 asks for. The pager is still suppressed while a
    filter is active, so the two pages behave identically where it is
    visible; they differ only in what a filter that matches more than
    500 rows renders.
    """
    if is_filtered:
        return matching, 0, None
    offset = views.clamp_offset(offset, total=len(matching))
    return (
        matching[offset : offset + views.PAGE_SIZE],
        offset,
        views.build_pager(total=len(matching), offset=offset),
    )


def _invitation_redirect_url(session_id: int, return_to: str | None) -> str:
    """Resolve the redirect target for an invitation action. ``return_to``
    overrides only when it matches the operations-row allowlist; otherwise
    fall back to the consolidated Invitations page."""
    if return_to in _REVERT_RETURN_TO:
        return f"/operator/sessions/{session_id}/{return_to}"
    if return_to == "home":
        return f"/operator/sessions/{session_id}"
    return f"/operator/sessions/{session_id}/invitations"


router = APIRouter()


@router.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_session(
    request: Request,
    severity: str = "all",
    activate: int = 0,
    return_to: str | None = None,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: str | None = None,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    issues = validation.validate_session_setup(db, review_session)
    report = lifecycle.build_readiness_report(issues)
    # Activate-warns detour: ?activate=1 requests the inline
    # confirmation banner (Segment 11G PR D). It only renders on
    # ``validated`` sessions that have warnings or new errors. On
    # ineligible states (draft / ready / expired / archived) or
    # when there's
    # nothing to acknowledge, drop the param and 303 to the clean
    # URL — operator can activate (or not) from the Workflow card.
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
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="validate",
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
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
            "activate_return_to": return_to,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Validate setup"
            ),
            **workflow_ctx,
        },
    )


@router.get("/sessions/{session_id}/previews", response_class=HTMLResponse)
def previews_index(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Keep old Previews bookmarks useful after the hub's retirement."""
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


@router.get("/sessions/{session_id}/preview")
def session_preview(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Permanent redirect from the standalone reviewer-surface preview
    (Segment 10B-3) to the operator-side full preview surface.
    Through Segment 11F PR C this redirected to the Previews hub's
    iframe surface card; the card was retired by the 2026-05-28
    preview-surface follow-on to Segment 11F, so the redirect now
    targets the standalone preview route directly.

    Status 308 keeps the GET method and preserves the bookmark / link
    semantics for stragglers.
    """
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/preview-surface/1",
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


def _require_validated_or_ready(review_session: ReviewSession) -> None:
    """Reject invitation actions while the session is still in draft.

    Segment 18F Part 2 relaxes the gate from "ready only" to
    "validated or ready" — operators can create and send invites
    from the Prepared (`validated`) state so reviewers receive a
    notification *before* the session is activated. Invitations
    still can't fire from `draft` (the assignment pairs aren't
    settled yet) or any post-`ready` state.
    """
    if not (
        lifecycle.is_validated(review_session)
        or lifecycle.is_ready(review_session)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Invitations can only be issued once the session has been "
                "prepared (validated or ready)."
            ),
        )


# Back-compat alias — kept so any direct caller from outside this module
# (test fixtures, future routes) keeps working through the rename.



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


def _unmatched_email(
    db: Session, review_session: ReviewSession, candidate: str
) -> str:
    """The candidate address, but only if no reviewer really has it.

    Folds through `normalize_email` — `str.lower` since 19N Item 2,
    and the authority is that module's own docstring plus
    `tests/unit/test_email_identity_fold.py`, not `spec/architecture.md`,
    which says nothing about folding. Without it `ALICE@example.edu`
    would be reported missing while `alice@example.edu` sits in the
    roster.

    **No status filter, unlike the participant gates.** Those answer
    "may this person act"; this one answers "does the picker's
    population contain this address", and that population is
    `build_preview_picker_context`'s — every `Reviewer` in the session,
    active or not. Filtering here would suppress the card for a
    withdrawn reviewer whose address the picker also failed to resolve,
    landing the operator on Invitations with nothing said, which is the
    regression this whole item exists to undo.
    """
    candidate = candidate.strip()
    if not candidate:
        return ""
    folded = normalize_email(candidate)
    exists = db.execute(
        select(Reviewer.id)
        .where(Reviewer.session_id == review_session.id)
        .where(func.lower(Reviewer.email) == folded)
        .limit(1)
    ).first()
    return "" if exists else candidate


@router.get(
    "/sessions/{session_id}/invitations", response_class=HTMLResponse
)
def invitations_index(
    request: Request,
    status: str = "all",
    q: str = "",
    offset: int = 0,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: str | None = None,
    no_match: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    all_rows = views.build_invitations_rows(db, review_session)
    all_rows = views.apply_cookie_sort(
        all_rows,
        views.decode_cookie_sort_spec(
            cookies=dict(request.cookies),
            cookie_name=f"rrw-sort-invitations-{review_session.id}",
            valid_keys=_INVITATIONS_SORT_KEYS,
        ),
        value_resolver=_invitations_sort_value,
    )
    matching = views.filter_invitations_rows(all_rows, status=status, search=q)
    # Segment 19J.5 rung 3 — this page rendered every matching row until
    # now, whatever the number. It pages at 200 unfiltered; a filtered
    # view stays uncapped and carries no pager (see the route's
    # ``pager`` entry below).
    is_filtered = bool(status != "all" or q.strip())
    rows, offset, pager = _page_operations_rows(
        matching, is_filtered=is_filtered, offset=offset
    )
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
    # Info-card metric inventory: eight counters across the
    # invitation / reminder / response lifecycle.
    invitations_sent_count = sum(
        1 for r in all_rows if r.email_sent_at is not None
    )
    reminders_sent_count = sum(
        1 for r in all_rows if r.last_reminder_at is not None
    )
    pending_reminders_count = sum(
        1
        for r in all_rows
        if r.is_incomplete and r.last_reminder_at is None
    )
    completed_count = sum(1 for r in all_rows if not r.is_incomplete)
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="invitations",
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
    )
    # Auto-send invites / reminders captions are part of
    # ``workflow_ctx`` now — the Workflow card renders them in its
    # right-column aside.
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            # 19O Item 6 — the address `/preview-surface` could not
            # resolve, echoed back so this page can say so. Empty on
            # every other entry path, which is all of them but one.
            #
            # **Re-checked here rather than trusted.** The value is a
            # query parameter, so anything can put anything in it, and
            # the card states a fact about the roster: "no reviewer in
            # this session has this email". Echoing it unverified let
            # `?no_match=alice@example.edu` assert that about Alice
            # while Alice sat in the table below. A page whose job is
            # to report the roster accurately cannot take a caller's
            # word for what the roster contains.
            "no_match": _unmatched_email(db, review_session, no_match),
            "total_row_count": len(all_rows),
            # Segment 19I Item 10 — the shared preview-count
            # sentence, moved out of the filter row to sit with
            # the rows it counts. These two pages are uncapped by
            # decision, so `shown` and `matching` are the same
            # number and only the filter branch ever fires. The
            # noun is the page's subject, not its row type: one
            # row per reviewer here, per reviewee on Responses.
            # Segment 19J.5 rung 1 — the scaffold. The ranges are real,
            # computed from the real count; the links are inert until a
            # later rung supplies ``pager_url_base``. ``None`` while a
            # filter is active is the suppression rule: the operator's
            # own partition of the roster wins, and the count line
            # speaks for that view instead. Both read the same filter
            # flag, so the two affordances can never disagree about
            # which mode the page is in.
            "pager": pager,
            # Only ever rendered on an unfiltered view, so the link
            # carries no filter state — and deliberately not the
            # sort cookie either, which is a cookie and travels on
            # its own.
            "pager_url_base": (
                f"/operator/sessions/{review_session.id}/invitations?"
            ),
            # The fragment the range links land on (19J.8): the
            # table's card, so a page turn arrives showing the card's
            # top edge, the column chips, the page links and the new
            # rows — in that order down the screen. Passed rather than
            # derived: a macro guessing the id would land silently at
            # the top of the document the first time someone renamed
            # it, which is a failure with no error.
            "pager_anchor": "invitations-table-card",
            # 19J.5 rung 3 — paged now, so the unfiltered branch says
            # nothing and the ranges speak instead. A filtered view is
            # uncapped here, so its sentence never carries a withheld
            # clause.
            "preview_count_line": views.preview_count_line(
                shown=len(rows),
                pool=len(matching),
                noun="reviewers",
                is_filtered=is_filtered,
            ),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.INVITATIONS_STATUS_OPTIONS,
            # 19I Item 12 rung 2 — chip flags over the session's whole
            # reviewer roster, not over ``rows``, which a filter
            # narrows. A tag populated only on rows the filter excluded
            # used to read as "no data" and strike its chip out.
            "col_data": views.chip_slots(
                tag_slot_presence(
                    db, session_id=review_session.id, model=Reviewer
                ),
                prefix="tag-",
            ),
            "filter_search_options": search_options,
            "eligible_count": len(eligible),
            "uninvited_count": sum(1 for r in eligible if r.id not in invited_ids),
            "pending_count": pending_count,
            "incomplete_count": incomplete_count,
            "total_invitation_count": len(invitation_rows),
            "invitations_sent_count": invitations_sent_count,
            "reminders_sent_count": reminders_sent_count,
            "pending_reminders_count": pending_reminders_count,
            "completed_count": completed_count,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Invitations"
            ),
            **workflow_ctx,
        },
    )


@router.get(
    "/sessions/{session_id}/invitations/reviewers/{reviewer_id}",
    response_class=HTMLResponse,
)
def invitation_reviewer_detail(
    request: Request,
    reviewer_id: int,
    email: str = "invitation",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Drill-in from a row on the Manage Invitations table.

    Segment 11C Part 1 scaffolds this as a thin per-reviewer summary —
    the same Email Status / Review Progress / Required Fields fields the
    consolidated table renders, plus the latest invitation outbox row's
    raw token URL when available. Future segments grow this surface
    (per-assignment progress, per-response detail).

    **Keyed on the reviewer since 19P.6 rung 1**, not on the invitation
    it used to take from the path. The invitation supplied one field
    (`invite_url`) while the reviewer looked up from it supplied the
    row match, the heading, the email and the breadcrumb label — so
    keying on the field made the table's link conditional on a row
    that may not exist yet. It is resolved here instead, through the
    row, and is simply absent before **Create invites**.
    """
    reviewer = _require_reviewer_in_session(db, review_session, reviewer_id)
    rows = views.build_invitations_rows(db, review_session)
    row = next((r for r in rows if r.reviewer.id == reviewer.id), None)
    # `row` is None for a reviewer the table does not list — inactive,
    # or with no included assignment. **Not a new state**, though an
    # earlier version of this comment said so: deactivating a reviewer
    # leaves their invitation alone (`reviewers.bulk_inactivate` flips
    # `status` only), so the old invitation-keyed URL already reached
    # this page from a bookmark. Measured on the pre-re-key commit:
    # 200, no Review Progress card. What changed is WHO can reach it —
    # every reviewer in the session, including one that never had an
    # invitation, where before only an invitation could name one.
    #
    # **The invitation is resolved from the reviewer, not from `row`.**
    # Taking `row.invitation` loses it for exactly the reviewers above:
    # a sent invitation outlives its reviewer's place on the table, and
    # is still the live link in their inbox, so the page that shows it
    # must keep showing it. `generate_invitations` skips reviewers who
    # already have one and `regenerate_token` mutates in place, so
    # there is at most one per (session, reviewer) and this is
    # unambiguous.
    #
    # `session_id` in the filter is redundant by construction — the
    # reviewer above is already session-scoped, so their invitation
    # cannot belong to another session without corrupt data. Kept as
    # defence in depth, and named here because no test can distinguish
    # it: a mutation dropping it survives the suite, and should.
    invitation = db.execute(
        select(Invitation).where(
            Invitation.session_id == review_session.id,
            Invitation.reviewer_id == reviewer.id,
        )
    ).scalar_one_or_none()
    invite_url = (
        invitations.most_recent_invitation_url(db, invitation_id=invitation.id)
        if invitation is not None
        else None
    )
    # 19P.6 rung 2b — the Invitation card's delivery slot (Item 6 open
    # question 5). `invitation.sent_at` says a send was attempted on the
    # current token; this says what became of it. Different facts from
    # different tables, which is the distinction rung 2a drew — so the
    # card carries both rather than picking one.
    #
    # **Why not `row.email_status`, which is already in hand?** Because
    # `row` is None for a reviewer the table does not list, the same
    # reason the invitation above is re-resolved rather than taken from
    # `row.invitation`. Rung 2b's commit gave a different reason — that
    # one query cannot disagree with itself — and `diff-reviewer` was
    # right that it is only half the story: this keys on
    # `invitation_id` while the view keys on `reviewer_id`, and
    # `detach_outbox` can unlink those independently, so agreeing with
    # the URL beside it does not mean agreeing with the table.
    delivery_status = (
        invitations.most_recent_invitation_status(
            db, invitation_id=invitation.id
        )
        if invitation is not None
        else None
    )
    active_email_tab = views.resolve_email_preview_tab(email)
    email_body = views.build_email_preview_body(
        tab=active_email_tab,
        review_session=review_session,
        reviewer=reviewer,
        from_display=views.email_preview_from_display(user),
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations_reviewer_detail.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewer": reviewer,
            # Back in the context at 19P.6 rung 2a. Rung 1's cold read
            # removed it as a slot nothing read — true then, and the
            # reason the card below could not tell "no invitation" from
            # "invitation not sent".
            "invitation": invitation,
            "row": row,
            "invite_url": invite_url,
            "delivery_status": delivery_status,
            "email_tabs": views.EMAIL_PREVIEW_TABS,
            "active_email_tab": active_email_tab,
            "email_body": email_body,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_invitations_reviewer(
                review_session, reviewer.name
            ),
        },
    )


@router.get("/sessions/{session_id}/invitations/{invitation_id}/detail")
def invitation_reviewer_detail_legacy(
    bundle: tuple[Invitation, ReviewSession] = Depends(
        _require_invitation_in_session
    ),
) -> RedirectResponse:
    """The pre-19P.6 invitation-keyed URL, kept for bookmarks.

    **308, not 303**: the move is permanent and the method is
    preserved, which is what `/preview` → `/preview-surface/1` already
    does (`spec/preview_hub.md`). The two paths cannot collide — one
    ends in the literal `detail`, the other has the literal `reviewers`
    one segment earlier — so declaration order does not matter here.
    """
    invitation, review_session = bundle
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}"
            f"/invitations/reviewers/{invitation.reviewer_id}"
        ),
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


@router.post("/sessions/{session_id}/invitations/generate")
def invitations_generate(
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_validated_or_ready(review_session)
    invitations.generate_invitations(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=_invitation_redirect_url(review_session.id, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/invitations/send-all")
def invitations_send_all(
    request: Request,
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_validated_or_ready(review_session)
    # `list_sendable_invitations`, not `list_invitations_for_session`
    # (19Q Item 2 rung 1). The listing is every row, which is what the
    # page wants; the send set is pending **and** still eligible. Before
    # this the button emailed reviewers the page above it does not list
    # — `build_invitations_rows` goes through
    # `monitoring.per_reviewer_progress`, which is assigned-and-active —
    # so an operator saw one row and sent two mails.
    rows = invitations.list_sendable_invitations(db, review_session.id)
    for row in rows:
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
        url=_invitation_redirect_url(review_session.id, return_to),
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
    _require_validated_or_ready(review_session)
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
    _require_validated_or_ready(review_session)
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
    _require_validated_or_ready(review_session)
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    # Segment 15F — defensive status re-check. The Invitations table
    # filters inactive reviewers out so the per-row Send button never
    # renders for them, but a direct POST / stale tab could still
    # reach this route. Match the bulk send-path's active-only gate.
    if reviewer.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reviewer is inactive; reactivate before sending.",
        )
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


# Per-session ``GET /sessions/{id}/outbox`` route retired 2026-05-11
# in favour of the inline outbox section on
# ``/operator/sys-admin/sessions`` (Sessions Diagnostics tab).
# Bookmarked URLs lose the route; users land on a 404. The Admin
# chrome is now the only canonical entry point.


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
    offset: int = 0,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: str | None = None,
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
    all_rows = views.apply_cookie_sort(
        all_rows,
        views.decode_cookie_sort_spec(
            cookies=dict(request.cookies),
            cookie_name=f"rrw-sort-responses-{review_session.id}",
            valid_keys=_RESPONSES_SORT_KEYS,
        ),
        value_resolver=_responses_sort_value,
    )
    matching = views.filter_responses_rows(all_rows, status=status, search=q)
    # Segment 19J.5 rung 3 — see the Invitations route above; the two
    # pages page on identical terms.
    is_filtered = bool(status != "all" or q.strip())
    rows, offset, pager = _page_operations_rows(
        matching, is_filtered=is_filtered, offset=offset
    )
    search_options = views.responses_search_options(all_rows)
    summary = monitoring.summary_counts(db, review_session)
    incomplete_count = summary.incomplete
    # Info-card metrics: total reviewees + the with-response /
    # without-response split. ``no responses`` is the only
    # coverage_state value that means "this reviewee has had
    # nothing submitted about them".
    reviewees_with_responses_count = sum(
        1 for r in all_rows if r.coverage_state != "no responses"
    )
    reviewees_without_responses_count = sum(
        1 for r in all_rows if r.coverage_state == "no responses"
    )
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="responses",
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_responses.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "total_row_count": len(all_rows),
            # Segment 19I Item 10 — the shared preview-count
            # sentence, moved out of the filter row to sit with
            # the rows it counts. These two pages are uncapped by
            # decision, so `shown` and `matching` are the same
            # number and only the filter branch ever fires. The
            # noun is the page's subject, not its row type: one
            # row per reviewer here, per reviewee on Responses.
            # Segment 19J.5 rung 1 — the scaffold. The ranges are real,
            # computed from the real count; the links are inert until a
            # later rung supplies ``pager_url_base``. ``None`` while a
            # filter is active is the suppression rule: the operator's
            # own partition of the roster wins, and the count line
            # speaks for that view instead. Both read the same filter
            # flag, so the two affordances can never disagree about
            # which mode the page is in.
            "pager": pager,
            # Only ever rendered on an unfiltered view, so the link
            # carries no filter state — and deliberately not the
            # sort cookie either, which is a cookie and travels on
            # its own.
            "pager_url_base": (
                f"/operator/sessions/{review_session.id}/responses?"
            ),
            # The fragment the range links land on (19J.8): the
            # table's card, so a page turn arrives showing the card's
            # top edge, the column chips, the page links and the new
            # rows — in that order down the screen. Passed rather than
            # derived: a macro guessing the id would land silently at
            # the top of the document the first time someone renamed
            # it, which is a failure with no error.
            "pager_anchor": "responses-table-card",
            # 19J.5 rung 3 — paged now, so the unfiltered branch says
            # nothing and the ranges speak instead. A filtered view is
            # uncapped here, so its sentence never carries a withheld
            # clause.
            "preview_count_line": views.preview_count_line(
                shown=len(rows),
                pool=len(matching),
                noun="reviewees",
                is_filtered=is_filtered,
            ),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.RESPONSES_STATUS_OPTIONS,
            # 19I Item 12 rung 2 — chip flags over the session's whole
            # reviewee roster, not over ``rows``, which a filter
            # narrows. A tag populated only on rows the filter excluded
            # used to read as "no data" and strike its chip out.
            "col_data": views.chip_slots(
                tag_slot_presence(
                    db, session_id=review_session.id, model=Reviewee
                ),
                prefix="tag-",
            ),
            "filter_search_options": search_options,
            "incomplete_count": incomplete_count,
            "reviewees_with_responses_count": reviewees_with_responses_count,
            "reviewees_without_responses_count": (
                reviewees_without_responses_count
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Responses"
            ),
            **workflow_ctx,
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
    _require_validated_or_ready(review_session)
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
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk reminder dispatch from the consolidated Manage Invitations
    page (Segment 11C Part 1). Funnels through the same
    ``invitations.send_reminders_to_incomplete`` helper the (still-
    existing) Monitoring page uses; PR 3 retires the Monitoring
    counterpart endpoint."""
    _require_validated_or_ready(review_session)
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
        url=_invitation_redirect_url(review_session.id, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# The POST /sessions/{id}/monitoring/remind-incomplete endpoint retired
# in Segment 11C Part 1 PR 3. Its only caller was the (now-deleted)
# Monitoring template; bulk reminder dispatch funnels through
# ``POST /sessions/{id}/invitations/remind-incomplete`` (PR 2) instead.
