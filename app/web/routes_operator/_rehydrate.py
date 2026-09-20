"""Rehydrate an extracted session — operator surface.

Segment 18P Group 2. Reached from the ``Rehydrate`` button in the
Sessions Lobby Filter-card row; rebuilds a session from a complete set
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
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.services import rehydrate_stash
from app.services.extracts import stream_csv
from app.services.extracts.responses_import import serialize_dropped_responses
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
    outcome: dict[str, object] | None = None,
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_rehydrate.html",
        {
            "user": user,
            "breadcrumbs": breadcrumbs.operator_rehydrate_session(),
            "report": report,
            "token": token,
            "outcome": outcome,
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


def _require_rehydrate_enabled() -> None:
    """404 unless ``rehydrate_enabled`` is on (Segment 19N).

    Gated rather than deleted: the pipeline is wired and covered by
    tests, and the gap is in the unsettled cases, not the machinery —
    a response the regenerated rules cannot place is dropped with a
    warning nobody surfaces. A 404 rather than a disabled page because
    an operator who has never seen this feature should not be told it
    exists and is withheld.
    """
    if not settings.rehydrate_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get(
    "/sessions/rehydrate",
    response_class=HTMLResponse,
    dependencies=[Depends(_require_rehydrate_enabled)],
)
def rehydrate_page(
    request: Request,
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    """The rehydrate landing page — the empty form before any Validate."""
    return _render(request, user)


@router.post(
    "/sessions/rehydrate/validate",
    response_class=HTMLResponse,
    dependencies=[Depends(_require_rehydrate_enabled)],
)
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


@router.post(
    "/sessions/rehydrate/commit",
    response_class=HTMLResponse,
    dependencies=[Depends(_require_rehydrate_enabled)],
)
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

    result = rehydrate_session(
        db,
        files=files,
        user=user,
        correlation_id=request_correlation_id(),
    )
    rehydrate_stash.delete(db, token=token)

    if not result.dropped:
        db.commit()
        return RedirectResponse(
            url=f"/operator/sessions/{result.session.id}?rehydrated=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Rows were lost. A 303 cannot carry a download, and a count alone
    # cannot tell the operator *which* responses did not survive, so the
    # page stays put and hands them the file. The CSV rides the same
    # operator-scoped stash the Validate hand-off uses.
    csv_bytes = b"".join(stream_csv(serialize_dropped_responses(result.dropped)))
    dropped_token = rehydrate_stash.put(db, payload=csv_bytes, user=user)
    db.commit()
    return _render(
        request,
        user,
        outcome={
            "session_id": result.session.id,
            "session_name": result.session.name,
            "dropped_count": result.dropped_count,
            "dropped_token": dropped_token,
        },
    )


@router.get(
    "/sessions/rehydrate/dropped.csv",
    dependencies=[Depends(_require_rehydrate_enabled)],
)
def rehydrate_dropped_csv(
    token: str = "",
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """Serve the dropped-responses CSV a commit stashed.

    The stash is operator-scoped and TTL-bounded, so another operator's
    token reads as absent rather than as a refusal, and a link shared or
    bookmarked past the TTL simply expires."""
    payload = rehydrate_stash.get(db, token=token or "", user=user)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return Response(
        content=payload,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="rehydrate_dropped_responses.csv"'
            )
        },
    )
