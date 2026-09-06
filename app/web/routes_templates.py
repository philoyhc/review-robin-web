"""Setup CSV template downloads — Segment 19E rungs 4 and 5.

One route per set, each serving generic roster templates as a zip. It is
deliberately **not session-scoped**: the two surfaces that offer it (the
Guide's "Create and set up a session" card and the lobby first-run card)
both render before any session exists, which is the point — an operator
can fill the templates in and use them with Quick Setup *while* creating
the session rather than after.

Authentication only, no authorization: the payload is CSV headers and
mock rows, identical for every operator and derived from constants
(`app.services.setup_templates`). There is no session to check a
permission against, and nothing here reads the database.

No audit event, for the same reason. The extract routes in
``routes_operator/_extracts.py`` write one because they export a
session's real roster; this exports nobody's data, and ``audit_events``
rows are session-scoped.

Spec: ``spec/csv_contracts.md``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.auth.identity import AuthenticatedUser, get_current_user
from app.services.setup_templates import build_zip, set_by_key

router = APIRouter()


def _zip_response(set_key: str) -> Response:
    """``Response`` rather than ``StreamingResponse``: both archives are
    a few kilobytes built in memory, so there is nothing to stream and a
    plain body lets Starlette set ``Content-Length``."""
    template_set = set_by_key(set_key)
    return Response(
        content=build_zip(template_set),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{template_set.zip_name}"'
            ),
        },
    )


@router.get("/templates/starter.zip")
def download_starter_templates(
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """The starter set — four roster files, one row each."""
    del user  # required for the auth gate; the payload is user-independent
    return _zip_response("starter")


@router.get("/templates/demo.zip")
def download_demo_session(
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """The demo set — a populated cohort that reaches ``validated``."""
    del user  # required for the auth gate; the payload is user-independent
    return _zip_response("demo")
