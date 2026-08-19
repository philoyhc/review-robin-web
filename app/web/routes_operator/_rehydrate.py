"""Rehydrate an extracted session — operator surface.

Segment 18P Group 2. Reached from the ``Rehydrate`` button in the
Sessions Lobby search-card row; rebuilds a session from a complete set
of extract CSV files (``spec/rehydrate.md``).

**PR G0** landed the UI scaffold; **PR G3** wired the mandatory pre-flight
**Validate** action (the upload is analyzed via
:func:`session_rehydrate.analyze_rehydrate_set`, stashed under a token, and
the page re-renders with the findings + preview; **Rehydrate** enables only
on a clean verdict). **PR H (this file)** wires the **Rehydrate** commit:
``POST …/rehydrate/commit`` loads the stashed set, re-runs the analyzer
(a stale / expired stash fails safe), and on a clean verdict calls
:func:`session_rehydrate.rehydrate_session` and redirects to the new draft's
Session Home.
"""
from __future__ import annotations

import io
import os
import zipfile

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import rehydrate_stash
from app.services.session_rehydrate import (
    RehydrateReport,
    analyze_rehydrate_set,
    pack_file_set,
    rehydrate_session,
    unpack_file_set,
)
from app.web import breadcrumbs
from app.web.deps import get_or_create_user, request_correlation_id
from app.web.routes_operator._shared import _templates

router = APIRouter()


def _render(
    request: Request,
    user: User,
    *,
    report: RehydrateReport | None = None,
    token: str | None = None,
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_rehydrate.html",
        {
            "user": user,
            "breadcrumbs": breadcrumbs.operator_rehydrate_session(),
            "report": report,
            "token": token,
        },
    )


def _collect_files(uploads: list[UploadFile]) -> dict[str, bytes]:
    """Flatten the upload into a ``{basename: bytes}`` CSV set — loose
    CSVs plus the members of any uploaded ZIP bundles. Non-CSV members
    and unreadable ZIPs are ignored."""
    files: dict[str, bytes] = {}
    for upload in uploads:
        name = (upload.filename or "").strip()
        if not name:
            continue
        content = upload.file.read()
        low = name.lower()
        if low.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for member in zf.namelist():
                        if member.lower().endswith(".csv"):
                            files[os.path.basename(member)] = zf.read(member)
            except zipfile.BadZipFile:
                continue
        elif low.endswith(".csv"):
            files[os.path.basename(name)] = content
    return files


@router.get("/sessions/rehydrate", response_class=HTMLResponse)
def rehydrate_page(
    request: Request,
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    """The rehydrate landing page — the empty form before any Validate."""
    return _render(request, user)


@router.post("/sessions/rehydrate/validate", response_class=HTMLResponse)
def rehydrate_validate(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Run the mandatory pre-flight, stash a clean set, re-render with
    the findings + preview. Creates no session."""
    collected = _collect_files(files)
    report = analyze_rehydrate_set(db, files=collected, user=user)
    token = None
    if report.ok:
        # Only a clean set is worth stashing — the Rehydrate button gates
        # on the same verdict, so a failed run has nothing to commit.
        token = rehydrate_stash.put(
            db, payload=pack_file_set(collected), user=user
        )
    return _render(request, user, report=report, token=token)


@router.post("/sessions/rehydrate/commit", response_class=HTMLResponse)
def rehydrate_commit(
    request: Request,
    token: str = Form(default=""),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """Commit a validated set: load it from the stash, **re-run the
    analyzer** (a stale / altered / expired stash fails safe), and on a
    clean verdict rebuild the session and redirect to its Session Home.
    An unusable token or a verdict that no longer passes re-renders the
    page with the findings — no session is created."""
    payload = rehydrate_stash.get(db, token=token or "", user=user)
    if payload is None:
        report = RehydrateReport(
            ok=False,
            errors=[
                "Your validated upload expired or is no longer available — "
                "re-upload the extract files and run Validate again."
            ],
        )
        return _render(request, user, report=report)

    files = unpack_file_set(payload)
    # Re-run the mandatory pre-flight against the exact stashed bytes: the
    # Validate verdict is authoritative but the world may have moved (a
    # colliding session created since), so never commit on trust alone.
    report = analyze_rehydrate_set(db, files=files, user=user)
    if not report.ok:
        return _render(request, user, report=report, token=token)

    review_session = rehydrate_session(
        db,
        files=files,
        user=user,
        correlation_id=request_correlation_id(),
    )
    rehydrate_stash.delete(db, token=token)
    db.commit()
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}?rehydrated=1",
        status_code=303,
    )
