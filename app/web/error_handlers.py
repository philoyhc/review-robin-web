"""Global error handling — Segment 14A PR 2.

Three exception handlers, registered via ``register_error_handlers``
from ``create_app``:

* ``StarletteHTTPException`` — every ``HTTPException`` a route raises
  (404 session-not-found, 403 unauthorized, the invalid-invitation
  404, …) renders the standalone ``error.html`` page instead of
  FastAPI's default JSON.
* ``RequestValidationError`` — a malformed query / path parameter
  renders the same page as a 400 rather than a JSON 422 body.
* ``Exception`` — any *unhandled* error (a reviewer-save or export
  failure, a latent bug) renders a friendly 500 page. The full
  traceback is logged to the structured application-log stream
  (PR 1) and never shown to the user.

The page is deliberately standalone — its own minimal inline CSS,
not ``base.html`` — so an error caused by missing request / auth
context can't cascade into a second failure while rendering the
error page itself.

The ``OperatorAllowlistDenied`` handler stays in ``app/main.py``:
that is a deliberate 303 redirect to ``/request-access``, not an
error page.
"""
from __future__ import annotations

import http
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.logging_config import get_logger

log = get_logger(__name__)

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Per-status headline + default body for the error page.
_ERROR_COPY: dict[int, tuple[str, str]] = {
    status.HTTP_400_BAD_REQUEST: (
        "Bad request",
        "The request couldn't be processed. Please check the link or "
        "form and try again.",
    ),
    # 422 — request-validation failures. Integer literal rather than
    # ``status.HTTP_422_*`` because the constant's name churned across
    # Starlette versions (ENTITY → CONTENT) and emits a deprecation
    # warning.
    422: (
        "Bad request",
        "The request couldn't be processed. Please check the link or "
        "form and try again.",
    ),
    status.HTTP_403_FORBIDDEN: (
        "Access denied",
        "You don't have permission to view this page.",
    ),
    status.HTTP_404_NOT_FOUND: (
        "Page not found",
        "The page you're looking for doesn't exist, or may have been "
        "removed.",
    ),
    status.HTTP_500_INTERNAL_SERVER_ERROR: (
        "Something went wrong",
        "An unexpected error occurred. The problem has been logged — "
        "please try again in a moment.",
    ),
}

_GENERIC = ("Something went wrong", "An unexpected error occurred.")


def _standard_phrase(status_code: int) -> str:
    """The stdlib reason phrase for ``status_code`` (``""`` if unknown).

    Starlette defaults a detail-less ``HTTPException``'s ``detail`` to
    this phrase; we use it to tell a route-supplied message apart from
    that default so the page only shows genuinely informative copy.
    """
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _render_error(
    request: Request, status_code: int, detail: str | None = None
) -> Response:
    headline, body = _ERROR_COPY.get(status_code, _GENERIC)
    message = body
    if detail and detail != _standard_phrase(status_code):
        message = detail
    return _templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status_code,
            "headline": headline,
            "message": message,
        },
        status_code=status_code,
    )


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    if exc.status_code >= 500:
        log.error(
            "http exception",
            extra={
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
            },
        )
    detail = exc.detail if isinstance(exc.detail, str) else None
    return _render_error(request, exc.status_code, detail)


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    return _render_error(request, 422)


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> Response:
    log.error(
        "unhandled exception",
        extra={"path": request.url.path, "method": request.method},
        exc_info=exc,
    )
    return _render_error(request, status.HTTP_500_INTERNAL_SERVER_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    """Wire the three handlers onto ``app``."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(
        RequestValidationError, _validation_exception_handler
    )
    app.add_exception_handler(Exception, _unhandled_exception_handler)
