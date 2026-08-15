"""Rehydrate an extracted session — operator surface.

Segment 18P Group 2. Reached from the ``Rehydrate`` button in the
Sessions Lobby search-card row; rebuilds a session from a complete set
of extract CSV files (``docs/rehydrate.md``).

**PR G0** landed the UI scaffold; **PR G3 (this file)** wires the
mandatory pre-flight **Validate** action: the upload is analyzed
(:func:`session_rehydrate.analyze_rehydrate_set`), stashed under a token
(:mod:`rehydrate_stash`), and the page re-renders with the findings +
preview; the **Rehydrate** button enables only on a clean verdict,
carrying the stash token. The commit route + orchestrator land in **PR
H** (``POST …/rehydrate/commit`` doesn't exist yet).
"""
from __future__ import annotations

import io
import os
import zipfile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import rehydrate_stash
from app.services.session_rehydrate import (
    RehydrateReport,
    analyze_rehydrate_set,
    pack_file_set,
)
from app.web import breadcrumbs
from app.web.deps import get_or_create_user
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
