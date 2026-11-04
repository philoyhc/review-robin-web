"""The directory pickers' searches (segment 19Z, invite from the
directory): a session's roster rows ask the session's (rung 20), and the
"Help contact (optional)" boxes on New session and Session Home ask the
workspace's (rung 21), since New session has no session yet. Asked on the
operator's own delegated token; a local run asks the fake directory.

Also the roster upload's countdown (segment 20H Item 6): the Upload
card's script asks ``directory-keys`` which of the file's addresses still
need a lookup, then sends them to ``directory-lookup`` in batches, which
keeps each answer for the upload to read (`directory_lookups`).

And the Upload card's "Recheck N unmatched" (segment 20I Item 1): a
roster's saved rows with an address and no directory account looked up
again, those found bound (`directory_recheck`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import csv_imports, directory_accounts, directory_lookups, directory_recheck
from app.web import urls
from app.web.deps import get_or_create_user, request_correlation_id, require_session_operator
from app.web.roster_import import read_upload
from app.web.routes_operator._shared import (
    ROSTER_PARSERS,
    directory_or_none,
    directory_search_response,
    roster_address,
)

router = APIRouter()

#: A countdown batch: at most this many keys, in a body this large,
#: looked up within this many seconds (the Email Address Checker's
#: shape, `utilityapps/email_check/routes.py`).
LOOKUP_BATCH_MAX = 25
LOOKUP_BODY_MAX = 64 * 1024
LOOKUP_BUDGET = 30.0

_NO_STORE = {"Cache-Control": "no-store"}


def _error(status: int, error: str) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=status, headers=_NO_STORE)


@router.get("/sessions/{session_id}/directory-search")
def roster_directory_search(
    request: Request,
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
) -> JSONResponse:
    """Up to ten people for a roster row's picker; the session's operators
    only (`_shared.directory_search_response`)."""
    return directory_search_response(directory_or_none(request), q)


@router.get("/directory-search")
def workspace_directory_search(request: Request, q: str = "") -> JSONResponse:
    """Up to ten people for a help-contact box's picker; any workspace
    operator (the package's `require_operator` gate)."""
    return directory_search_response(directory_or_none(request), q)


@router.post("/sessions/{session_id}/directory-keys")
async def roster_directory_keys(
    roster: str = Form(...),
    file: UploadFile | None = File(None),
    held_token: str | None = Form(None),
    recheck: str | None = Form(None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """The file's lookup keys not yet answered within the cache's life:
    what the countdown has left to look up. The file (or the held one)
    is parsed by its roster's own parser; a file that does not parse
    answers no keys, and the upload then shows its problems. With
    ``recheck`` (segment 20I Item 1), every key of the roster's
    unmatched rows instead, kept or not, and no file is read. Saves
    nothing but the sweep of stale answers."""
    parse = ROSTER_PARSERS.get(roster)
    if parse is None:
        return _error(404, "unknown_roster")
    if recheck == "true":
        if roster not in directory_recheck.ROSTERS:
            return _error(404, "unknown_roster")
        if roster == "observers" and not review_session.observers_enabled:
            return _error(404, "unknown_roster")
        directory_lookups.sweep(db)
        db.commit()
        # Every unmatched key, kept answers or not: a recheck asks for
        # a fresh answer, and the POST then reads the ones just fetched.
        addresses = directory_recheck.unmatched_addresses(
            db, session_id=review_session.id, kind=roster
        )
        keys = list(dict.fromkeys(
            k for k in (directory_accounts.key(a) for a in addresses) if k is not None
        ))
        # `since`: the recheck POST reads only answers fetched from now
        # on, so a countdown stopped early leaves the rest to the server.
        return JSONResponse(
            {"keys": keys, "since": datetime.now(UTC).isoformat()},
            headers=_NO_STORE,
        )
    upload = await read_upload(
        db, file=file, held_token=held_token, user=user,
        review_session=review_session, slot=roster,
    )
    directory_lookups.sweep(db)
    db.commit()
    if not upload.content or len(upload.content) > csv_imports.MAX_BYTES:
        return JSONResponse({"keys": []}, headers=_NO_STORE)
    result = parse(upload.content)
    if result.is_blocked:
        return JSONResponse({"keys": []}, headers=_NO_STORE)
    keys = directory_lookups.still_to_look_up(
        db, user=user, session_id=review_session.id,
        addresses=[roster_address(row) for row in result.rows],
    )
    return JSONResponse({"keys": keys}, headers=_NO_STORE)


@router.post("/sessions/{session_id}/directory-lookup")
async def roster_directory_lookup(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """One countdown batch: ``{"keys": [...]}`` in, each key's status
    out (``{"outcomes": {key: {"status", "error_kind"}}}``), the answers
    kept for the upload. JSON only, so a cross-site form cannot post it
    without a preflight. The page learns no account, only whether each
    address was answered."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return _error(415, "json_required")
    length = request.headers.get("content-length", "")
    if not length.isdecimal() or int(length) > LOOKUP_BODY_MAX:
        return _error(413, "too_large")
    try:
        body = json.loads(await request.body())
    except (ValueError, RecursionError):
        return _error(400, "bad_json")
    keys = body.get("keys") if isinstance(body, dict) else None
    if (
        not isinstance(keys, list)
        or not 1 <= len(keys) <= LOOKUP_BATCH_MAX
        or not all(isinstance(k, str) and directory_accounts.key(k) == k for k in keys)
    ):
        return _error(400, "bad_keys")
    directory = directory_or_none(request)
    if directory is None:
        return _error(503, "no_graph")
    outcomes = await run_in_threadpool(
        directory_lookups.look_up_and_keep,
        db, directory, user=user, session_id=review_session.id, keys=keys, budget=LOOKUP_BUDGET,
    )
    db.commit()
    return JSONResponse(
        {
            "outcomes": {
                k: {"status": o.status, "error_kind": o.error_kind} for k, o in outcomes.items()
            }
        },
        headers=_NO_STORE,
    )


@router.post("/sessions/{session_id}/directory-recheck")
async def roster_directory_recheck(
    request: Request,
    roster: str = Form(...),
    since: str | None = Form(None),
    stop: str | None = Form(None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """The Upload card's "Recheck N unmatched" (segment 20I Item 1): the
    roster's unmatched rows looked up again, on the operator's token,
    reading what the card's countdown already fetched, and each one the
    directory now finds bound. Reviewers and Reviewees while the session
    is editable, Observers until it is archived (author, 2026-11-04), the
    service deciding under the session lock. Back to
    the card, whose directory line shows the recheck's counts; an
    expired sign-in saves nothing and the card asks to renew.

    A recheck asks for fresh answers: it reads only those its own
    countdown fetched (``since``, set by the page from `directory-keys`).
    Without the script there is no ``since``, and every address is
    looked up here.

    ``stop=true`` is *Stop and save* (author, 2026-11-04): the countdown
    was stopped, so only what it fetched is read and nothing is looked up
    here. It needs ``since``; without one it is ignored."""
    if roster not in directory_recheck.ROSTERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if roster == "observers" and not review_session.observers_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    addresses = directory_recheck.unmatched_addresses(
        db, session_id=review_session.id, kind=roster
    )
    started = _parse_since(since)
    known = (
        directory_lookups.known_for(
            db, user=user, session_id=review_session.id, addresses=addresses, since=started
        )
        if started is not None
        else {}
    )
    # The lookups block, and the service waits for the session lock:
    # both off the event loop.
    result = await run_in_threadpool(
        directory_recheck.recheck,
        db,
        review_session=review_session,
        user=user,
        kind=roster,
        directory=directory_or_none(request),
        known=known,
        stopped=stop == "true" and started is not None,
        correlation_id=request_correlation_id(),
    )
    db.commit()
    renew = "&recheck_renew=1" if result.stopped else ""
    return urls.redirect(
        request,
        url=f"/operator/sessions/{review_session.public_id}/{roster}?unlocked=1{renew}#upload-csv",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _parse_since(value: str | None) -> datetime | None:
    """The recheck countdown's start, as `directory-keys` gave it, or
    ``None`` for none or a value that does not parse."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
