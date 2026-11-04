"""The Setup cards' upload handling (segment 20E rung 3, moved unchanged
from ``app/web/routes_operator/_shared.py``): reading an upload and holding
it while the page asks (19W), and the roster import every card's Upload
posts to (``_handle_import``, ``_save_field_labels``).

Outside the routes package so ``_shared`` stays the only module slices
share there (``CLAUDE.md``, "Architecture at a glance"). The slices import
this module, and it reads the package's guards and templates from
``_shared``, so it imports ``_shared`` inside the two functions that use it,
never at the top: a top-level import would be a cycle through the
package's ``__init__``. It calls ``_shared.directory_or_none`` through the
module, so a test that replaces it there reaches this code too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi import HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import (
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import RevieweeImportRow, ReviewerImportRow
from app.services import (
    assignments,
    csv_imports,
    directory_lookups,
    held_uploads,
    roster_bulk,
    unit_of_work,
)
from app.services import field_labels as field_labels_service
from app.services import session_lifecycle as lifecycle
from app.services import symmetric_review as symmetric_review_service
from app.services.responses import GroupAnswersWouldClear
from app.web import breadcrumbs, urls, views
from app.web.deps import request_correlation_id

__all__ = [
    "UploadIn",
    "read_upload",
    "hold_for_ask",
    "release_hold",
    "dismiss_held_upload",
    "_handle_import",
    "_save_field_labels",
]


@dataclass(frozen=True)
class UploadIn:
    """The file a Setup upload card sent: the one chosen, or, with
    none chosen, the one its last ask held (segment 19W). ``token`` is
    the hold in play, if any; ``lost`` says a hold was named but had
    expired or was not this operator's and session's."""

    content: bytes
    filename: str | None
    token: str | None
    lost: bool = False


async def read_upload(
    db: Session,
    *,
    file: UploadFile | None,
    held_token: str | None,
    user: User,
    review_session: ReviewSession,
    slot: str,
) -> UploadIn:
    """Read a Setup upload card's file, falling back to the held one.

    A newly chosen file wins over the hold, even an empty one: a file
    is chosen when it has a filename, as Quick Setup's ``_attached``
    reads it, since an untouched input posts an empty-named part. An
    empty chosen file is then refused as a fresh empty upload is
    (findings S2). The held
    bytes are parsed again by the caller, exactly as a fresh upload's
    would be."""
    token = (held_token or "").strip() or None
    content = await file.read() if file is not None else b""
    chosen = file is not None and bool(file.filename)
    if content or chosen or token is None:
        return UploadIn(
            content=content,
            filename=file.filename if file is not None else None,
            token=token,
        )
    held = held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ).get(slot)
    if held is None:
        return UploadIn(content=b"", filename=None, token=None, lost=True)
    return UploadIn(content=held.content, filename=held.filename, token=token)


def hold_for_ask(
    db: Session,
    *,
    upload: UploadIn,
    user: User,
    review_session: ReviewSession,
    slot: str,
) -> dict[str, str] | None:
    """Hold the file of an upload refused with a question, so the
    operator answers it without choosing the file again (segment 19W).
    Commits the hold: the refusal re-renders at 400 without one. Returns
    the template's ``held_upload`` (token and filename), or ``None`` when
    nothing could be held (an empty file, or one over the cap)."""
    token = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={
            slot: held_uploads.HeldFile(
                filename=upload.filename or "upload.csv",
                content=upload.content,
            )
        },
        token=upload.token,
    )
    db.commit()
    if token is None:
        return None
    # Name what the hold holds, not what was sent: a file it skipped (an
    # empty or oversized one) is not held, and must not read as held.
    held = held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ).get(slot)
    if held is None:
        return None
    return {"token": token, "filename": held.filename}


def release_hold(
    db: Session,
    *,
    token: str | None,
    user: User,
    review_session: ReviewSession,
) -> None:
    """End a hold once its upload is done with: saved, refused for good,
    or dismissed. A token that is not this operator's and this session's
    deletes nothing."""
    token = (token or "").strip()
    if not token:
        return
    if held_uploads.discard(
        db, token=token, user=user, session_id=review_session.id
    ):
        db.commit()


def dismiss_held_upload(
    request: Request, db: Session,
    *,
    held_token: str | None,
    user: User,
    review_session: ReviewSession,
    page: str,
) -> RedirectResponse:
    """A Setup upload card's Dismiss while its ask holds a file: end the
    hold, then back to the card with the panel open (segment 19W).
    ``page`` is the route segment (``reviewers``, ``reviewees``,
    ``relationships``, ``observers``), never a URL from the form."""
    release_hold(db, token=held_token, user=user, review_session=review_session)
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/{page}"
            "?unlocked=1#upload-csv"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _handle_import(
    *,
    request: Request,
    file: UploadFile | None,
    held_token: str | None,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn: Callable[[Session, int], int],
    parse_fn: Callable[
        [bytes],
        csv_imports.ParseResult[ReviewerImportRow]
        | csv_imports.ParseResult[RevieweeImportRow],
    ],
    # Called with the import's keywords plus a merge's ``**extra``, so
    # its parameters are not spelled here.
    save_fn: Callable[..., tuple[int, int]],
    append: str | None = None,
    merge: str | None = None,
    acknowledge_group_clear: str | None = None,
) -> HTMLResponse | RedirectResponse:
    """Shared Reviewers / Reviewees CSV-import handler.

    ``kind`` is ``"reviewers"`` or ``"reviewees"``; the *_fn callables
    are the matching ``csv_imports`` entry points. On a parse / confirm
    / ack failure it re-renders the Setup page with the reason in the
    upload card's banner; on success it saves and 303s back to the
    page.

    An ask (no tick, both ticks, or the response-loss ack) holds the
    file, so the next submit answers it with no file chosen (segment
    19W); a save or a plain refusal ends the hold.

    ``append`` is the card's append tick (segment 19Z): the file's rows
    are added and nothing is replaced, so no response-loss ack applies.
    A row already on the roster, or on a directory account already
    there, refuses the file as its problems.

    ``merge`` is the merge tick (the upsert amendment): matched rows are
    updated, the rest added. A Reviewees merge whose tag changes would
    clear saved group answers asks first with the count, as the row
    editor does; its tick is ``acknowledge_group_clear``, a field of its
    own, since the card's hidden ``acknowledge_response_loss`` already
    carries ``true`` for a replace."""
    # Imported here, not at the top: the routes package imports this
    # module, so a top-level import of it would be a cycle (20E rung 3).
    from app.web.routes_operator import _shared
    from app.web.routes_operator._shared import (
        _require_editable,
        _templates,
        acknowledged_loss,
        roster_address,
    )
    _require_editable(review_session)
    upload = await read_upload(
        db,
        file=file,
        held_token=held_token,
        user=user,
        review_session=review_session,
        slot=kind,
    )
    result = parse_fn(upload.content)
    if not result.is_blocked:
        result.issues.extend(
            csv_imports.check_cross_table_identity(
                db,
                session_id=review_session.id,
                rows=result.rows,
                kind=kind,
            )
        )
    existing = existing_count_fn(db, review_session.id)
    assignment_count = csv_imports.existing_assignment_count(db, review_session.id)

    if kind == "reviewers":
        template = "operator/session_reviewers.html"
        crumb_label = "Reviewers"
        list_key = "reviewers"
        list_items = assignments.list_reviewers(db, review_session.id)
    else:
        template = "operator/session_reviewees.html"
        crumb_label = "Reviewees"
        list_key = "reviewees"
        list_items = assignments.list_reviewees(db, review_session.id)

    # An append onto an empty roster is just the roster (plan,
    # Decision): only a direct POST can send one, as the card shows no
    # ticks there.
    appending = append == "true" and existing > 0
    merging = merge == "true" and existing > 0
    ticked = (confirm_replace == "true") + appending + merging

    def render(
        status_code: int = status.HTTP_200_OK,
        *,
        missing_confirm: bool = False,
        missing_response_ack: bool = False,
        both_ticks: bool = False,
        held_upload: dict[str, str] | None = None,
        group_clear: dict[str, object] | None = None,
        directory_renew: bool = False,
    ) -> HTMLResponse:
        context: dict[str, object] = {
            # These two are the ids the page's own controls point at.
            # They were missing here, and Jinja's `Undefined` is falsy
            # rather than loud — so this re-render emitted `id=""` on
            # the table card and a bare `#` on every control that
            # targets it, which means "top of document". The landing
            # anchors silently did nothing on exactly the page where an
            # operator is reading hardest: a failed import.
            "pager_anchor": f"{kind}-table-card",
            "row_editor_anchor": f"{kind}-row-editor",
            # Same reason as the two above, and the same failure mode:
            # this path re-renders the page template, so it owes every
            # key that template reads. Without these, Reviewers rendered
            # `<input name="filter_offset" value="">` on a failed import
            # — harmless today only because an empty form value reads as
            # absent for an `int` field with a default, and because this
            # path renders unpaged so 0 is the right answer anyway.
            #
            # 19P.1 rung 3c moved the import card INTO the Unlock
            # panel, so this line flipped, as the rung-3 slicing said it
            # would have to. The panel ships `hidden` unless the server
            # says otherwise, and `?unlocked=1` cannot reach an in-place
            # re-render — this path returns 400 with the page, it does
            # not redirect. Left False, a failed import would answer
            # with a collapsed panel and the operator would see no
            # errors at all: `_upload_problems.html` renders the file's
            # problems inside that card.
            #
            # The suite cannot catch a regression here. With no JS
            # runtime `hidden` is an inert attribute, so the issues are
            # in the markup and every assertion on them passes either
            # way; Chromium is what proves it. Third time this shape has
            # bitten this segment (`.is-locked`, `.filter-actions`).
            #
            # 19P.3 rung 4 — BOTH kinds now, and the literal collapses
            # rather than gaining a branch. This handler serves exactly
            # `reviewers` and `reviewees`, and both render the panel
            # since Reviewees gained one, so there is no page left for
            # which the flag means nothing.
            "current_offset": 0,
            "panel_open": True,
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            list_key: list_items,
            "existing_count": existing,
            "directory_check": views.last_directory_check(db, review_session, kind),
            "directory_unmatched": views.unmatched_count(db, review_session, kind),
            "assignment_count": assignment_count,
            "upload_problems": views.upload_problems(
                kind,
                result.issues,
                missing_confirm=missing_confirm,
                missing_response_ack=missing_response_ack,
                both_ticks=both_ticks,
            ),
            "filename": upload.filename,
            # Segment 19W: the file an ask holds, named in the card in
            # place of the empty input; a hold that had lapsed; and the
            # replace tick, ticked again when the operator had ticked it
            # (author, 2026-10-19).
            "held_upload": held_upload,
            "held_upload_lost": upload.lost,
            # Segment 20G: the check stopped on the sign-in, so nothing
            # was saved and the file is held; the card asks to renew.
            "directory_renew": directory_renew,
            "confirm_replace_checked": (
                held_upload is not None and confirm_replace == "true" and not both_ticks
            ),
            # Segment 19Z: the append and merge ticks, likewise. None
            # comes back on the both-ticks ask, which asks the operator
            # to choose.
            "append_checked": held_upload is not None and appending and not both_ticks,
            "merge_checked": held_upload is not None and merging and not both_ticks,
            # A Reviewees merge refused for clearing group answers: the
            # count and line, offered back with a tick in the card.
            "group_clear": group_clear,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, crumb_label
            ),
        }
        if kind in ("reviewers", "reviewees"):
            # Segment 15F — the Reviewers / Reviewees templates'
            # right-side operator-actions card needs the filter / cap
            # context even on the CSV-import error-render path so the
            # form keeps reading consistent. The error render is
            # never an edit state.
            if kind == "reviewers":
                status_options = views.REVIEWERS_STATUS_OPTIONS
                search_options = views.reviewers_search_options(
                    cast(list[Reviewer], list_items)  # loaded for this kind above
                )
                # 19I Item 12 rung 2 — this path re-renders the same
                # template, so it owes it the same chip flags. Missing
                # them here would render every chip as "no data" on a
                # failed import, which is exactly when an operator is
                # looking hardest at which columns arrived.
                # 19P.1 — this path re-renders the same template, so it
                # owes it the same keys. The comment above says why that
                # matters; ``col_readouts`` is now one of them, and an
                # absent key would raise in the index row rather than
                # degrade quietly.
                column_state = views.reviewer_column_state(db, review_session)
                col_data = column_state.col_data
                col_readouts = column_state.readouts
                # participant info Item 1 — the same lesson again: the
                # Unlock panel's self-fields card and the readout row's
                # `Reviewers see:` pills read three keys this path owes.
                context.update(
                    views.reviewer_self_card_context(
                        review_session, col_readouts
                    )
                )
            else:
                status_options = views.REVIEWEES_STATUS_OPTIONS
                search_options = views.reviewees_search_options(
                    cast(list[Reviewee], list_items)  # loaded for this kind above
                )
                # 19P.3 rung 4 — same as the branch above, and for the
                # same reason. This once set ``col_readouts = []`` with
                # a note that Reviewees had no index row yet; once it
                # had one, the empty list stopped being a placeholder
                # and started being a lie — a failed import rendered
                # an empty index ("Populated columns: none yet", as the
                # row then read) over a roster of three.
                # One helper answers both keys, so they cannot drift.
                column_state = views.reviewee_column_state(db, review_session)
                col_data = column_state.col_data
                col_readouts = column_state.readouts
                # participant info Item 4 — Item 1's lesson, kept: this
                # path owes the own-entry card and readout their keys.
                context.update(
                    views.reviewee_self_card_context(
                        review_session, col_readouts
                    )
                )
            context.update(
                {
                    "total_row_count": len(list_items),
                    "displayed_row_count": len(list_items),
                    # Segment 19I Item 10 — this path renders the
                    # whole roster unfiltered and uncapped, so the
                    # shared count line has nothing to report. Set
                    # explicitly rather than left undefined: an
                    # absent key would render the same today, but
                    # only by relying on Jinja's undefined being
                    # falsy.
                    "preview_count_line": None,
                    "filter_status": "all",
                    "filter_search": "",
                    "filter_status_options": status_options,
                    "filter_search_options": search_options,
                    "is_ready": lifecycle.is_ready(review_session),
                    # Segment 19I Item 3. This render path builds its
                    # own context, so every key the strip reads has to
                    # be repeated here. `delete_discards_responses`
                    # (Item 2) was missing and **nothing failed**:
                    # Jinja's `Undefined` is falsy in `{% if %}`, so
                    # the label silently took its no-loss branch on
                    # this page. Only `roster_response_count`, which is
                    # compared rather than tested, raised — which is
                    # how the older omission was found.
                    "is_editable": lifecycle.is_editable(review_session),
                    # No ``is_archived``: this path is behind
                    # ``_require_editable`` above, so it renders only
                    # when editable, and the lock card (19H.6) gates on
                    # ``not is_editable`` and never reads it here.
                    "delete_discards_responses": (
                        lifecycle.session_has_responses(db, review_session)
                    ),
                    "delete_discards_assignments": assignment_count > 0,
                    "roster_response_count": (
                        lifecycle.session_response_count(db, review_session)
                    ),
                    # 19O.5 rung 2 — this path builds its own context,
                    # so it owes the per-row counts the rows read. An
                    # absent key raises in the `<tr>` rather than
                    # degrading quietly; twelve tests caught it, which
                    # is the third time this handler has taught the
                    # lesson (19P.1, 19P.3, here).
                    "relationships_per_row": roster_bulk.relationships_per_row(
                        db,
                        model=Reviewer if kind == "reviewers" else Reviewee,
                        session_id=review_session.id,
                    ),
                    "col_data": col_data,
                    "col_readouts": col_readouts,
                    "edit_id": None,
                    "add_mode": False,
                    "edit_values": None,
                    "edit_error": None,
                    "selected_ids": set[int](),
                }
            )
        return _templates.TemplateResponse(
            request, template, context, status_code=status_code
        )

    def ask() -> dict[str, str] | None:
        return hold_for_ask(
            db, upload=upload, user=user, review_session=review_session,
            slot=kind,
        )

    if result.is_blocked:
        release_hold(
            db, token=upload.token, user=user, review_session=review_session
        )
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and ticked > 1:
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            both_ticks=True,
            held_upload=ask(),
        )

    if existing > 0 and ticked == 0:
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            missing_confirm=True,
            held_upload=ask(),
        )

    # The same gate as `_require_response_loss_ack`, answered in the
    # upload card's banner rather than as a full error page: that page
    # asked for an "acknowledge response loss" tick no page offers. The
    # card sends the field beside the tick whenever it names responses,
    # so this is a tab loaded before the session had any, or a direct
    # POST; the re-render names them and carries the field.
    if (
        existing > 0
        and not appending
        and not merging
        and acknowledge_response_loss != "true"
        and lifecycle.session_has_responses(db, review_session)
    ):
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            missing_response_ack=True,
            held_upload=ask(),
        )

    # Segment 21F: each address resolved through the directory on the
    # operator's token, at the save and not at an ask, so a held file is
    # looked up once. Off the event loop, as the lookups block.
    # Segment 20H Item 6: what the card's countdown already fetched is
    # read, not asked again.
    addresses = [roster_address(row) for row in result.rows]
    directory_check = await run_in_threadpool(
        csv_imports.directory_check,
        _shared.directory_or_none(request),
        addresses,
        directory_lookups.known_for(
            db, user=user, session_id=review_session.id, addresses=addresses
        ),
    )
    # Segment 20G: a check an expired token stopped (Graph's
    # ``unauthorized``) saves nothing. The file is held, and the card asks
    # to renew the sign-in and upload again, every address checked. Any
    # other failure, no token included, saves and the line says why.
    if directory_check.stopped:
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            held_upload=ask(),
            directory_renew=True,
        )
    # Segment 19Z: an append refuses a row already on the roster, or on
    # a directory account already there, as the file's problems. The
    # save checks again under the session lock.
    if appending:
        result.issues.extend(
            csv_imports.append_conflicts(
                db,
                session_id=review_session.id,
                kind=kind,
                rows=result.rows,
                directory=directory_check,
            )
        )
        if result.is_blocked:
            release_hold(
                db, token=upload.token, user=user, review_session=review_session
            )
            return render(status_code=status.HTTP_400_BAD_REQUEST)
    # A merge refuses two file rows on one directory account.
    if merging:
        result.issues.extend(
            csv_imports.merge_conflicts(kind=kind, rows=result.rows, directory=directory_check)
        )
        if result.is_blocked:
            release_hold(
                db, token=upload.token, user=user, review_session=review_session
            )
            return render(status_code=status.HTTP_400_BAD_REQUEST)
    extra: dict[str, object] = {}
    if merging:
        extra["merge"] = True
        extra["columns"] = result.columns
        # 20B — a Reviewers merge redraws mirrored reviewees' groups under
        # symmetric review, so it asks as a Reviewees merge does.
        if kind == "reviewees" or (kind == "reviewers" and review_session.symmetric_review):
            extra["acknowledged_loss"] = acknowledged_loss(acknowledge_group_clear)
    # The service locks the session row (findings Bc4): wait for it off
    # the event loop.
    try:
        await run_in_threadpool(
            save_fn,
            db,
            session=review_session,
            user=user,
            rows=result.rows,
            filename=upload.filename or "",
            correlation_id=request_correlation_id(),
            field_labels_captured=result.field_labels,
            directory=directory_check,
            append=appending,
            **extra,
        )
    except csv_imports.AppendConflict as refused:
        db.rollback()
        result.issues.extend(refused.issues)
        release_hold(db, token=upload.token, user=user, review_session=review_session)
        return render(status_code=status.HTTP_400_BAD_REQUEST)
    except GroupAnswersWouldClear as exc:
        # Rolled back in the save's own unit; roll back again before the
        # hold commits, so nothing of the refused merge rides with it.
        db.rollback()
        return render(
            status_code=status.HTTP_400_BAD_REQUEST,
            held_upload=ask(),
            group_clear={"count": exc.count, "message": str(exc), "surface": "import"},
        )
    release_hold(db, token=upload.token, user=user, review_session=review_session)
    # 19P.1 rung 3c — a successful import lands back with the panel still
    # open, matching the two controls that moved before it (the labels
    # save and delete-all). The author's rule from the UI pass: a Save
    # does not close the roster card, the Lock button does.
    # `#roster-card` lands on the card instead of the top of the
    # document.
    #
    # 19P.3 rung 4 — unconditional now. This was
    # `if kind == "reviewers" else ""` while Reviewees had no panel to
    # keep open; it has one, and this handler serves no other kind.
    return urls.redirect(request,
        url=(
            f"/operator/sessions/{review_session.public_id}/{kind}"
            "?unlocked=1#roster-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _save_field_labels(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    source_type: str,
    slots: tuple[tuple[str, str], ...],
    submitted: dict[str, str],
    correlation_id: str | None,
) -> None:
    """Upsert / clear per submitted slot (Segment 15A Slice 3).

    Rejected with 409 whenever the session is not editable — labels
    are locked alongside the rest of the page's data once it stops
    being a draft; operators revert to draft to rename.

    Segment 19H Item 7. This was ``is_ready`` from Segment 15A until
    then, so ``expired`` and ``archived`` sessions accepted the save
    (303) while the page's lock card said the roster could not be
    modified — 19H.6 put that card on those two states and turned a
    quiet inconsistency into a page contradicting itself. The gate is
    now ``_require_editable``'s predicate, so the editor, the Upload
    and Danger Zone cards, the selection surface and the lock card
    all answer one question.
    """
    if not lifecycle.is_editable(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to "
                "draft to rename labels."
            ),
        )
    # Every slot is checked before any is written, so an over-long label
    # refuses the save whole rather than landing the slots before it, or
    # reaching Postgres as a 500 (findings Cc3).
    for form_param, _ in slots:
        too_long = field_labels_service.label_length_error(
            submitted.get(form_param) or ""
        )
        if too_long is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=too_long,
            )
    # One commit for the form, so each slot's gate decides under the lock
    # the first one took, and a refusal part-way lands none of them
    # (findings Bc4; Codex on #2882).
    with unit_of_work.atomic(db):
        for form_param, source_field in slots:
            value = (submitted.get(form_param) or "").strip()
            if value:
                field_labels_service.upsert(
                    db,
                    review_session,
                    source_type=source_type,
                    source_field=source_field,
                    label=value,
                    user=user,
                    correlation_id=correlation_id,
                )
            else:
                field_labels_service.clear(
                    db,
                    review_session,
                    source_type=source_type,
                    source_field=source_field,
                    user=user,
                    correlation_id=correlation_id,
                )
        if source_type == "reviewer":
            # 20B — under symmetric review the reviewee labels follow.
            symmetric_review_service.sync_reviewees_from_reviewers(db, review_session)
